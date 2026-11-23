# Authentication, roles, and production startup

PETRO-TWIN supports two explicit API security modes:

- `PETROTWIN_AUTH_MODE=disabled`: isolated local development and test mode. Do not expose this mode to a shared network. User creation/listing/administration APIs return 503 in this mode; use the CLI.
- `PETROTWIN_AUTH_MODE=required`: production-oriented mode. All application API routes (including legacy prediction, optimizer, agent and WebSocket routes) require a signed bearer token. Liveness/readiness and login remain public. Interactive API documentation is disabled.

## Roles

| Role | Read data | Ingest field data | Run physics/calibration/analysis | Manage users, policies and approvals |
| --- | --- | --- | --- | --- |
| viewer | Yes | No | No | No |
| engineer | Yes | No | Yes | No |
| operator | Yes | Yes | No | No |
| admin | Yes | Yes | Yes | Yes |

CSS cycle, operational event and SRP operational record writes are operator/admin-only. Calibration approval/rejection, validation-policy changes, user provisioning and the authentication audit-event API are admin-only. The last active admin cannot be demoted or disabled.

## First-admin provisioning

Never ship a default account. Use the same persistent database and signing secret as the deployed API.

1. Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Store the generated value as `PETROTWIN_JWT_SECRET` in a protected environment/secret manager. It must be at least 32 bytes. Do not commit the value.
3. Set `PETROTWIN_AUTH_MODE=required` and deploy with the production override:

```powershell
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml up -d --build --wait
```

4. Provision the first admin through an interactive prompt (the password is not stored in the command line or file):

```powershell
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml run --rm ml-service python scripts/manage_users.py create --username <your-admin-username> --role admin
```

5. Sign in using the UI. Create additional accounts through authenticated `POST /api/v1/auth/users`. Use `GET /api/v1/auth/audit-events` for the security audit trail.

The CLI can also list accounts without returning password hashes:

```powershell
docker compose --env-file .env -f docker-compose.yml -f docker-compose.production.yml run --rm ml-service python scripts/manage_users.py list
```

## Session and password controls

Passwords are stored as salted scrypt hashes (never plaintext). Access tokens are HMAC-SHA256 signed JWTs with a configurable 5–60 minute lifetime, backed by persisted sessions. Logout revokes the session; disabling/changing a user also revokes that user's current sessions. Keep the signing secret stable across restarts and rotate it through a planned session invalidation event.

The browser stores the access token in session storage, attaches it to API requests, and clears it after an unauthorized response. TLS termination, rate limiting at the edge, managed secret storage, backup/restore security, security scanning, and external identity-provider integration still need environment-specific setup and verification before production exposure.
