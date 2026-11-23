# PETRO-TWIN AI: Deployment and runtime configuration

## Active container topology

The canonical Compose stack has three services:

| Service | Internal port | Exposure |
|---|---:|---|
| frontend | 3000 | Host-published on loopback only |
| ml-service | 8000 | Internal Compose network only |
| postgres | 5432 | Internal Compose network only |

React is served by Nginx; Nginx reverse-proxies API and WebSocket requests to FastAPI. Spring Boot is legacy/dormant and is not part of this runtime.

## Local development profile

Copy `.env.example` to `.env`, set a strong PostgreSQL password, and run:

```powershell
docker compose up -d --build --wait
```

This profile disables authentication for isolated development only. Never expose it to a shared or public network.

## Authenticated, hardened Compose profile

The production-oriented override is fail-closed: it requires a unique JWT secret and explicit CORS origins, forces field mode and required authentication, removes host-published API access, and applies container hardening. On Windows PowerShell:

```powershell
$bytes = New-Object byte[] 48
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$env:PETROTWIN_JWT_SECRET = [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
$env:CORS_ORIGINS = 'https://your-real-frontend-domain.example'
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --wait
```

The secret above is process-scoped. In a real deployment, inject it from the platform's secret manager; do not commit it, paste it into logs, or rely on a developer workstation environment for production.

For the isolated local verification stack created during the 2026-11-23 hardening run, the protected ignored file `.env.production.local` contains separate generated credentials and binds only to `127.0.0.1:3011`. Start/update that same stack with:

```powershell
docker compose --env-file .env.production.local -f docker-compose.yml -f docker-compose.production.yml -p petrotwin-prod-84ee578 up -d --build --wait
docker compose --env-file .env.production.local -f docker-compose.yml -f docker-compose.production.yml -p petrotwin-prod-84ee578 ps
```

Open the local interface at [http://127.0.0.1:3011](http://127.0.0.1:3011). FastAPI and PostgreSQL are not published on host ports for this profile.

### First administrator

There is no default account. Create the initial administrator interactively after the database is healthy:

```powershell
docker compose --env-file .env.production.local -f docker-compose.yml -f docker-compose.production.yml -p petrotwin-prod-84ee578 run --rm ml-service python scripts/manage_users.py create --username <admin-username> --role admin
```

The CLI prompts for the password. Do not put a password on the command line. The isolated verification stack intentionally has no administrator until the owner provisions one.

## Container hardening included

- Python and Nginx run as non-root UIDs; application containers use read-only root filesystems and bounded tmpfs write areas.
- Containers drop Linux capabilities, enable no-new-privileges, and have process, CPU and memory limits.
- Python numerical libraries are limited to two worker threads.
- Nginx applies restrictive response headers, a Content Security Policy, request/connection limits, login/API rate limits and request-size/time limits.
- API and database ports are internal-only; the UI is loopback-bound in the local profile.
- Docker base images are pinned by digest; the backend runtime dependency lock pins direct and transitive Python packages; Compose logs rotate; database and field-model artifacts use separate persistent named volumes.
- PostgreSQL persistence was verified across a container restart. This is not a substitute for backups.

## Release blockers before public production

The hardened local Compose profile is not a complete public production deployment. Before external access, configure and verify:

1. HTTPS/TLS termination, HSTS at the TLS edge, trusted ingress/network policy and real frontend CORS origins.
2. A managed secret store and rotation/recovery process; replace the workstation-only `.env.production.local`.
3. Automated encrypted PostgreSQL and model-artifact backups, off-host retention, and tested restore/runbook procedures.
4. Centralized monitoring, alerting, log collection, vulnerability scanning, image update cadence and incident response.
5. A named cloud environment, DNS, certificates, deployment pipeline, health-gated rollout and rollback.
6. Independent security review, external identity/MFA/SSO if required by the operator.

The former Render blueprint is archived as `render.legacy.yaml` and is intentionally not an active deployment manifest. It does not implement this authenticated topology. No cloud release is established by the local Compose test.

## Scientific and integration boundaries

The agent remains unavailable until an approved OpenAI-compatible provider URL, model and secret are configured. No live model-provider invocation was verified.

No real, permissioned field dataset was provided. CSS/SRP formulations remain simplified and the finite-grid optimizer is not an independently validated field optimum. No operating setpoint may be treated as an instruction to a live asset. Obtain petroleum/mechanical engineering review and independent validation using measured data before operational use.

## Verification commands

```powershell
.\.venv\Scripts\python.exe scripts\test_all.py
Push-Location frontend
npm ci
npm run build
npm run test:e2e
npm run lint
Pop-Location
```

The 2026-11-23 hardening verification recorded 80 Python tests and 7 browser E2E tests passing. Lint completed with warnings (not zero-warning). See [integration status](integration-status.md) for the evidence and remaining limitations.
