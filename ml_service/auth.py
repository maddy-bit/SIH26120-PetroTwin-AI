"""Production-oriented password, JWT session, and RBAC primitives for PETRO-TWIN."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ml_service.persistence import AnalysisRepository

ROLES = {"viewer", "engineer", "operator", "admin"}
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._@-]{3,80}$")
ISSUER = "petro-twin"


class AuthenticationError(Exception):
    def __init__(self, message: str = "Invalid or expired credentials", status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationService:
    """Issues short-lived signed tokens backed by revocable database sessions."""

    def __init__(self, repository: AnalysisRepository, secret: str, token_ttl_minutes: int = 15):
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("PETROTWIN_JWT_SECRET must contain at least 32 bytes")
        if not 5 <= token_ttl_minutes <= 60:
            raise ValueError("Access token TTL must be between 5 and 60 minutes")
        self.repository = repository
        self._secret = secret.encode("utf-8")
        self.token_ttl_minutes = token_ttl_minutes

    @staticmethod
    def hash_password(password: str) -> str:
        if len(password) < 12 or len(password) > 256:
            raise ValueError("Password must contain between 12 and 256 characters")
        salt = secrets.token_bytes(16)
        derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
        return "scrypt$16384$8$1$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(derived).decode()

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt_text, digest_text = encoded.split("$")
            if algorithm != "scrypt":
                return False
            salt = base64.urlsafe_b64decode(salt_text.encode())
            expected = base64.urlsafe_b64decode(digest_text.encode())
            actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError, MemoryError):
            return False

    @staticmethod
    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        return {key: user[key] for key in ("user_id", "username", "role", "is_active", "created_at", "updated_at") if key in user}

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _encode_token(self, claims: dict[str, Any]) -> str:
        header = self._b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        payload = self._b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
        signed = f"{header}.{payload}".encode("ascii")
        signature = hmac.new(self._secret, signed, hashlib.sha256).digest()
        return f"{header}.{payload}.{self._b64encode(signature)}"

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            header_text, payload_text, signature_text = token.split(".")
            header = json.loads(self._b64decode(header_text))
            claims = json.loads(self._b64decode(payload_text))
            if header != {"alg": "HS256", "typ": "JWT"}:
                raise ValueError("Unsupported JWT header")
            signed = f"{header_text}.{payload_text}".encode("ascii")
            expected = hmac.new(self._secret, signed, hashlib.sha256).digest()
            if not hmac.compare_digest(expected, self._b64decode(signature_text)):
                raise ValueError("Bad signature")
            now = int(time.time())
            if claims.get("iss") != ISSUER or int(claims.get("exp", 0)) <= now:
                raise ValueError("Token expired or wrong issuer")
            if not claims.get("sub") or not claims.get("sid"):
                raise ValueError("Required claims missing")
            return claims
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise AuthenticationError() from exc

    def _audit(self, action: str, outcome: str, *, user_id: str | None = None,
               ip_address: str | None = None, correlation_id: str | None = None,
               resource: str = "authentication", details: dict[str, Any] | None = None) -> None:
        self.repository.write_auth_audit_event({
            "event_id": str(uuid.uuid4()), "user_id": user_id, "action": action,
            "resource": resource, "outcome": outcome, "ip_address": ip_address,
            "correlation_id": correlation_id, "created_at": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        })

    def create_user(self, username: str, password: str, role: str, *,
                    actor_user_id: str | None = None) -> dict[str, Any]:
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("Username must be 3-80 characters using letters, digits, dot, underscore, @ or hyphen")
        normalized = username.casefold()
        if role not in ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(ROLES))}")
        password_hash = self.hash_password(password)
        now = datetime.now(timezone.utc).isoformat()
        user = {
            "user_id": str(uuid.uuid4()), "username": username, "username_normalized": normalized,
            "password_hash": password_hash, "role": role, "is_active": True,
            "created_at": now, "updated_at": now,
        }
        self.repository.create_auth_user(user)
        self._audit("user_created", "success", user_id=actor_user_id, resource=f"user:{normalized}",
                    details={"assigned_role": role})
        return self.public_user(user)

    def login(self, username: str, password: str, *, ip_address: str | None = None,
              correlation_id: str | None = None) -> dict[str, Any]:
        normalized = username.casefold().strip()
        user = self.repository.get_auth_user_by_username(normalized)
        if not user or not self.verify_password(password, user["password_hash"]) or not user["is_active"]:
            self._audit("login", "denied", user_id=user["user_id"] if user else None,
                        ip_address=ip_address, correlation_id=correlation_id,
                        details={"reason": "invalid_credentials_or_inactive"})
            raise AuthenticationError()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.token_ttl_minutes)
        session_id = str(uuid.uuid4())
        self.repository.create_auth_session({
            "session_id": session_id, "user_id": user["user_id"],
            "issued_at": now.isoformat(), "expires_at": expires.isoformat(),
        })
        token = self._encode_token({
            "iss": ISSUER, "sub": user["user_id"], "sid": session_id,
            "iat": int(now.timestamp()), "exp": int(expires.timestamp()),
        })
        self._audit("login", "success", user_id=user["user_id"], ip_address=ip_address,
                    correlation_id=correlation_id)
        return {"access_token": token, "token_type": "bearer", "expires_at": expires.isoformat(),
                "user": self.public_user(user)}

    def authenticate(self, token: str) -> dict[str, Any]:
        claims = self._decode_token(token)
        session = self.repository.get_auth_session(claims["sid"])
        user = self.repository.get_auth_user_by_id(claims["sub"])
        now = datetime.now(timezone.utc)
        if (not session or session["user_id"] != claims["sub"] or session["revoked_at"]
                or datetime.fromisoformat(session["expires_at"]) <= now
                or not user or not user["is_active"]):
            raise AuthenticationError()
        return {**self.public_user(user), "session_id": session["session_id"]}

    def logout(self, token: str, *, ip_address: str | None = None,
               correlation_id: str | None = None) -> None:
        claims = self._decode_token(token)
        self.repository.revoke_auth_session(claims["sid"], datetime.now(timezone.utc).isoformat())
        self._audit("logout", "success", user_id=claims["sub"], ip_address=ip_address,
                    correlation_id=correlation_id)

    def update_user(self, username: str, *, role: str | None = None,
                    is_active: bool | None = None, password: str | None = None,
                    actor_user_id: str | None = None) -> dict[str, Any]:
        user = self.repository.get_auth_user_by_username(username.casefold())
        if not user:
            raise KeyError("User not found")
        if role is not None and role not in ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(ROLES))}")
        users = self.repository.list_auth_users()
        active_admins = [item for item in users if item["role"] == "admin" and item["is_active"]]
        removing_admin = user["role"] == "admin" and user["is_active"] and (role not in (None, "admin") or is_active is False)
        if removing_admin and len(active_admins) <= 1:
            raise ValueError("The last active administrator cannot be demoted or deactivated")
        password_hash = self.hash_password(password) if password is not None else None
        self.repository.update_auth_user(user["user_id"], role=role, is_active=is_active, password_hash=password_hash)
        self.repository.revoke_user_sessions(user["user_id"], datetime.now(timezone.utc).isoformat())
        updated = self.repository.get_auth_user_by_id(user["user_id"])
        self._audit("user_updated", "success", user_id=actor_user_id, resource=f"user:{user['username_normalized']}",
                    details={"role_changed": role is not None, "active_changed": is_active is not None,
                             "password_reset": password is not None})
        return self.public_user(updated)
