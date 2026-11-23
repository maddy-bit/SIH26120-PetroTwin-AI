# PETRO-TWIN AI — Integration and Verification Status

**Updated:** 2026-11-23
**Canonical runtime:** React 19 / TypeScript → FastAPI / Python 3.12 → PostgreSQL 16 (Compose) or SQLite (local development). Spring Boot remains legacy/dormant source and is not in the active frontend request path.

This checkpoint supersedes older notes in this file that stated MCP, authentication, and Docker/PostgreSQL were unavailable.

## Component status

| Component | Current implementation | Status / boundary |
|---|---|---|
| Frontend ↔ Backend | React API client, FastAPI contracts, request errors, AuthGate, field data and Field Models screens | **Implemented and locally verified** |
| Field ingestion & persistence | Validated CSV/JSON ingestion, canonical units, quality/provenance/rejection records, repository migrations, SQLite/PostgreSQL | **Implemented; manual ingestion only** |
| Digital Twin Physics | Thermal, viscosity and SRP project models with explicit CSS → cooling → viscosity → SRP calculation path | **Partially implemented; simplified physics** |
| Calibration | Provenance-aware datasets, quality exclusions, identifiability, temporal validation, candidate lifecycle; Walther viscosity fit adapter | **Framework implemented; CSS thermal/SRP fitting unavailable** |
| ML | Separate measured-data Ridge production trainer; chronological 60/20/20 split; persistence baseline; model registry; SHA-256 artifacts; admin promotion | **Code/tests implemented; no real field-data training run** |
| CSS–SRP coupling | Shared model is used by scenario evaluation and the optimizer and returns stage inputs/outputs | **Simulation only; not field-calibrated or scientifically established** |
| Optimization | Candidate grid, configured constraints, weighted ranking and nondominated filtering; shares coupled physics calculation | **Functional simplified finite-grid method; not a validated field optimum** |
| Agents | Evidence-first LLM AgentRuntime, MCP stdio client, read-only evidence retrieval, tool allowlist, persisted traces | **Runtime/tests implemented; external model provider not configured** |
| MCP | Official Python MCP SDK 2.3.0; read-only tools/resources/prompt; actual stdio protocol test | **Implemented and protocol-tested** |
| Authentication / RBAC | scrypt passwords, HS256 signed tokens, DB-backed revocable sessions, viewer/engineer/operator/admin permissions, audit, first-admin CLI | **Implemented and tested; local edge protections added; public release controls still outstanding** |
| PostgreSQL | Compose PostgreSQL 16; migrations through schema version 9; isolated authenticated stack verified | **Locally verified** |
| Docker | Hardened authenticated Compose stack; non-root users, read-only root filesystems, dropped capabilities, resource/PID limits, private API/DB network, Nginx CSP/rate limits, digest-pinned base images, persistent DB/model artifact volumes | **Latest source image rebuild and local smoke checks completed 2026-11-23; public release blockers remain** |
| Automated tests | Unified Python suite, rerun after purged chronological ML split and HTTP-denial audit logging | **80 passed, 0 failed** |
| Browser E2E | Chrome / Playwright end-to-end workflows | **7 passed, 0 failed** |
| Frontend production build | TypeScript + Vite; workspace-level lazy loading | **Passed; largest chart chunk 338 kB (99 kB gzip), main entry 251 kB (78 kB gzip)** |
| Deployment | Authenticated, hardened local Compose profile on loopback | **Locally verified; no cloud release, TLS edge, managed secrets or backup/restore drill established** |
| Field validation | Independent measured-well evidence and domain review | **Not established — no real field dataset supplied** |

## Verification evidence from this device

| Check | Result |
|---|---|
| `.venv\Scripts\python.exe scripts\test_all.py` | **80 tests passed**, exit code 0 |
| `npm run test:e2e -- --reporter=list` (from `frontend`) | **7 tests passed**, exit code 0 |
| `npm run build` (from `frontend`) | TypeScript and Vite build passed, exit code 0 |
| `npm audit --audit-level=high` | **0 vulnerabilities** across the full npm dependency tree |
| `pip-audit -r docker/requirements-prod.lock` | **No known vulnerabilities** in the 48 pinned Python runtime packages |
| `git diff --check` | Passed |
| Python `py_compile` for changed auth/API/persistence/agent/MCP/physics/ML modules | Passed |
| Authenticated hardened Compose profile | Latest source rebuilt; frontend, FastAPI and PostgreSQL all healthy; API only internal to Compose network |
| Compose service status | Latest source stack active and healthy; isolated project/volumes do not modify the older verification or CityAI stacks |
| FastAPI `/health` | UP; database READY; auth_required true |
| Frontend HTTP | 200 |
| PostgreSQL migration level | **9** |
| Authentication/RBAC smoke check | Login 200; identity 200; viewer write denied 403; logout 200; revoked token denied 401; unauthenticated API 401 |
| Production Compose configuration | Validated with a process-scoped test JWT secret and isolated test database |

The 2026-11-23 hardened Compose stack was rebuilt from the latest working tree and is bound to 127.0.0.1:3011. Login, RBAC denial, logout/revocation, rate limiting, Nginx headers, read-only container filesystems, non-root UIDs, migration level 9 and PostgreSQL restart persistence were checked. The temporary test account and persistence probe were removed. This is still a workstation-local release candidate, not a public cloud deployment. The workstation-generated JWT/database credentials in the ignored .env.production.local file are local-only and must not be reused elsewhere.

## Integration details

### Authentication and roles

Required-auth mode is enabled by `docker-compose.production.yml`; it refuses to start without `PETROTWIN_JWT_SECRET` of at least 32 bytes. API routes are protected in this mode. The login and health endpoints are public. No default account exists; create the first administrator with `scripts/manage_users.py`. Roles: viewer (read), engineer (analysis), operator (field ingestion), admin (user management, approvals, policy and model promotion). User/session events are persisted in `auth_audit_events`.

### Agent and MCP path

`React Copilot → FastAPI → AgentRuntime → MCP client (stdio) → PETRO-TWIN read-only MCP tools → shared repository`, with evidence passed to a configured OpenAI-compatible chat-completions provider. The agent retrieves configuration, quality, measurements, CSS, SRP, event and source evidence. Tool schemas are filtered and each call is checked against a read-only allowlist. Runs are persisted in `agent_runs`.

The model provider is not configured on this machine. Therefore the provider API invocation and answer quality are not yet verified here; the service reports disabled and returns HTTP 503 rather than inventing an answer. This is a PETRO-TWIN MCP-backed agent, not an official IBM AssetOpsBench benchmark run or score.

### Measured-data ML lifecycle

The measured-data trainer is separate from the synthetic/demo model pipeline. It requires a registered non-demo well, VALID measurements with the expected units, time-safe features, and future oil-rate targets. It performs purged chronological train/validation/test splits (future labels cannot cross into the next split), validates against a persistence baseline, records source/measurement IDs and a dataset fingerprint, hashes the artifact, and creates a review candidate. It does not auto-promote. An admin must review and promote the candidate; inference verifies artifact integrity and requires fresh VALID features.

The four ML lifecycle tests use controlled test fixtures. They validate code behavior, not the engineering performance of a real field model. No production field model is currently trained or active.

## Remaining work that requires external inputs or environment

1. Supply real, permissioned well measurements, signal/unit dictionary, CSS cycle linkage, equipment configuration and SRP/dynamometer data. Then execute field calibration and independent validation.
2. Supply a secured OpenAI-compatible model endpoint/model and provider secret to test the live LLM investigation workflow.
3. Complete public-edge HTTPS/TLS termination and HSTS, trusted network ingress, managed-secret storage/rotation, automated off-host backups and tested restores, centralized monitoring/alerts, image scanning/update policy, and an independent security review before public production exposure. Local Nginx rate limits/CSP and container resource limits are implemented; they do not replace the missing public-edge controls. MFA and external OIDC/SSO are not implemented.
4. Configure and verify a real cloud/production deployment, DNS, certificates, operational alerting and rollback. Local Compose is not cloud deployment.
5. Add and validate SCADA/historian/OPC-UA/MQTT integration only when the asset owner supplies authorized endpoints, credentials and signal contracts.
6. Obtain petroleum/mechanical engineering review of the simplified thermal/viscosity/SRP formulations and optimizer operating envelopes. The current CSS–SRP coupling does not solve multiphase reservoir flow, wellbore heat transfer or rod-string wave dynamics. The optimizer does not validate fracture pressure, gearbox torque or API allowable stress.

## Operational commands

Local development (simulation/demo only; authentication disabled; do not expose):
```powershell
docker compose up -d --build --wait
```

Authenticated hardened local workstation profile:
```powershell
docker compose --env-file .env.production.local -f docker-compose.yml -f docker-compose.production.yml -p petrotwin-prod-84ee578 up -d --build --wait
```

Provision the initial administrator interactively; there is no default account:
```powershell
docker compose --env-file .env.production.local -f docker-compose.yml -f docker-compose.production.yml -p petrotwin-prod-84ee578 run --rm ml-service python scripts/manage_users.py create --username <admin-username> --role admin
```

Run verification:
```powershell
.\.venv\Scripts\python.exe scripts\test_all.py
cd frontend
npm ci
npm run build
npm run test:e2e
npm run lint
```

## Working-tree note

The previous application integration was pushed as commit 84ee578. This hardening checkpoint is a separate scoped changeset. The unrelated pre-existing untracked learning guide and audit-progress file are intentionally excluded from it.


The measured-data training split uses purging at the target timestamp: samples are excluded from the earlier split when their future target would occur on/after the following split's origin boundary. The full 80-test suite passed after this change. HTTP 401/403 authorization denials now generate persisted audit events with path, method, IP, reason and correlation ID.
