# PETRO-TWIN AI: Deployment and runtime configuration

## Active container topology

The supported Compose stack has three services:

| Service | Internal port | Role |
|---|---:|---|
| frontend | 3000 | React production bundle served by Nginx; proxies API paths to FastAPI |
| ml-service | 8000 | FastAPI, physics, ML, calibration, optimizer, agent and MCP stdio server |
| postgres | 5432 | PostgreSQL 16 persistent application database |

Spring Boot is legacy/dormant and is not started by the active Compose file. There is no MQTT broker, Prometheus, Grafana or TimescaleDB service in the current Compose configuration.

## Local demonstration mode

Copy `.env.example` to `.env`, set PostgreSQL credentials, then run:

```powershell
docker compose up --build --wait
```

The default configuration is intended for local development. It sets `PETROTWIN_AUTH_MODE=disabled`; do not expose it to a shared/public network. The PostgreSQL database and field-model artifact directory are persistent named volumes. Stop services with `docker compose down`; do not use `down -v` unless intentionally deleting the named volumes.

## Authenticated production-oriented Compose profile

Generate a unique signing secret and inject it from a protected secret store:

```powershell
$env:PETROTWIN_JWT_SECRET = (python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --wait
```

Set `PETROTWIN_AGENT_BASE_URL`, `PETROTWIN_AGENT_MODEL`, and `PETROTWIN_AGENT_API_KEY` only when an OpenAI-compatible model provider is available. The agent fails closed with HTTP 503 otherwise. Do not store API credentials in Git.

Provision the first administrator interactively after the database starts:

```powershell
docker compose -f docker-compose.yml -f docker-compose.production.yml run --rm ml-service python scripts/manage_users.py create --username <admin-username> --role admin
```

The CLI prompts twice for a password; no default account is created. The frontend then displays a sign-in screen. Passwords use scrypt, signed access tokens are short-lived and database-backed sessions can be revoked.

## Deployment hardening still required

The production override enables application authentication/RBAC; it does not create a complete hardened public deployment by itself. Configure HTTPS/TLS termination, restrictive network ingress, edge rate limiting, CSP, secure secret management, database and artifact backups, restore drills, monitoring/alerts, resource limits and a security review in the actual hosting environment. No cloud deployment is claimed by the repository configuration alone.
