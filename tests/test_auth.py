import tempfile
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from ml_service.auth import AuthenticationError, AuthenticationService
from ml_service.persistence import AnalysisRepository
from ml_service import main


class TestAuthenticationService(unittest.TestCase):
    def test_password_hash_login_session_revocation_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = AnalysisRepository(f"sqlite:///{Path(directory) / 'auth.sqlite3'}")
            repository.initialize()
            service = AuthenticationService(repository, "unit-test-secret-with-at-least-32-bytes", 15)
            user = service.create_user("Engineer.User", "Long-strong-password-123!", "engineer")
            self.assertEqual(user["role"], "engineer")
            self.assertNotIn("password_hash", user)
            self.assertNotIn("password_hash", repository.list_auth_users()[0])
            login = service.login("engineer.user", "Long-strong-password-123!")
            authenticated = service.authenticate(login["access_token"])
            self.assertEqual(authenticated["user_id"], user["user_id"])
            self.assertEqual(authenticated["role"], "engineer")
            with self.assertRaises(AuthenticationError):
                service.login("engineer.user", "incorrect-password")
            service.logout(login["access_token"])
            with self.assertRaises(AuthenticationError):
                service.authenticate(login["access_token"])
            events = repository.list_auth_audit_events()
            self.assertEqual([event["action"] for event in events].count("login"), 2)
            self.assertTrue(any(event["outcome"] == "denied" for event in events))

    def test_last_admin_cannot_be_demoted_or_disabled_and_updates_revoke_sessions(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = AnalysisRepository(f"sqlite:///{Path(directory) / 'rbac.sqlite3'}")
            repository.initialize()
            service = AuthenticationService(repository, "unit-test-secret-with-at-least-32-bytes", 15)
            admin = service.create_user("First.Admin", "Another-strong-password-987!", "admin")
            with self.assertRaisesRegex(ValueError, "last active administrator"):
                service.update_user("first.admin", role="viewer")
            with self.assertRaisesRegex(ValueError, "last active administrator"):
                service.update_user("first.admin", is_active=False)
            second_admin = service.create_user("Second.Admin", "Another-strong-password-988!", "admin")
            login = service.login("first.admin", "Another-strong-password-987!")
            service.update_user("first.admin", role="engineer")
            with self.assertRaises(AuthenticationError):
                service.authenticate(login["access_token"])
            self.assertEqual(repository.get_auth_user_by_id(admin["user_id"])["role"], "engineer")
            self.assertEqual(repository.get_auth_user_by_id(second_admin["user_id"])["role"], "admin")


class TestAuthenticationMiddleware(unittest.TestCase):
    def setUp(self):
        self.previous_service = main.auth_service
        self.previous_mode = main.config.auth_mode
        self.secret = "integration-test-secret-at-least-32-bytes"
        self.service = AuthenticationService(main.repository, self.secret, 15)
        suffix = uuid.uuid4().hex[:10]
        self.users = {}
        for role in ("viewer", "engineer", "operator", "admin"):
            self.users[role] = self.service.create_user(
                f"rbac-{role}-{suffix}", f"Strong-test-password-{role}-1!", role
            )
        main.auth_service = self.service
        main.config.auth_mode = "required"
        self.client = TestClient(main.app)

    def tearDown(self):
        main.auth_service = self.previous_service
        main.config.auth_mode = self.previous_mode

    def token_for(self, role):
        username = self.users[role]["username"]
        password = f"Strong-test-password-{role}-1!"
        return self.service.login(username, password)["access_token"]

    def test_auth_required_health_public_and_viewer_read_access(self):
        self.assertEqual(self.client.get("/api/wells").status_code, 401)
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["auth_required"])
        response = self.client.get("/api/wells", headers={"Authorization": f"Bearer {self.token_for('viewer')}"})
        self.assertEqual(response.status_code, 200)
        denial_events = [
            event for event in main.repository.list_auth_audit_events(100)
            if event["action"] == "http_access_denied" and event["resource"] == "/api/wells"
        ]
        self.assertTrue(any(
            event["details"].get("reason") == "missing_bearer_token"
            for event in denial_events
        ))

    def test_role_boundaries_for_ingestion_physics_and_admin(self):
        viewer = {"Authorization": f"Bearer {self.token_for('viewer')}"}
        engineer = {"Authorization": f"Bearer {self.token_for('engineer')}"}
        operator = {"Authorization": f"Bearer {self.token_for('operator')}"}
        admin = {"Authorization": f"Bearer {self.token_for('admin')}"}

        payload = {"well_id": f"RBAC-TEST-{uuid.uuid4().hex[:8]}", "name": "RBAC test well"}
        self.assertEqual(self.client.post("/api/v1/wells", json=payload, headers=viewer).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/wells", json=payload, headers=engineer).status_code, 403)
        self.assertEqual(self.client.post("/api/v1/wells", json=payload, headers=operator).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/users", headers=viewer).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/auth/users", headers=admin).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/auth/audit-events", headers=admin).status_code, 200)

    def test_logout_revokes_bearer_token(self):
        token = self.token_for("engineer")
        headers = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/wells", headers=headers).status_code, 401)

    def test_cors_preflight_is_not_blocked_by_bearer_auth(self):
        response = self.client.options(
            "/api/v1/wells",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("authorization", response.headers.get("access-control-allow-headers", "").lower())


if __name__ == "__main__":
    unittest.main()
