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
| Authentication / RBAC | scrypt passwords, HS256 signed tokens, DB-backed revocable sessions, viewer/engineer/operator/admin permissions, audit, first-admin CLI | **Implemented and tested; deployment hardening still required** |
| PostgreSQL | Compose PostgreSQL 16; migrations through schema version 9; isolated authenticated stack verified | **Locally verified** |
| Docker | Multi-service Compose stack; authenticated production override; persistent DB/model artifact volumes | **Prior source snapshot built and started; latest source image rebuild is awaiting the device approval prompt** |
| Automated tests | Unified Python suite, rerun after purged chronological ML split and HTTP-denial audit logging | **80 passed, 0 failed** |
| Browser E2E | Chrome / Playwright end-to-end workflows | **7 passed, 0 failed** |
| Frontend production build | TypeScript + Vite | **Passed; chunk-size advisory remains** |
| Deployment | Authenticated production-oriented local Compose deployment | **Local stack only; no cloud release established** |
| Field validation | Independent measured-well evidence and domain review | **Not established — no real field dataset supplied** |

## Verification evidence from this device

| Check | Result |
|---|---|
| `.venv\Scripts\python.exe scripts\test_all.py` | **80 tests passed**, exit code 0 |
| `npm run test:e2e -- --reporter=list` (from `frontend`) | **7 tests passed**, exit code 0 |
| `npm run build` (from `frontend`) | TypeScript and Vite build passed, exit code 0 |
| `git diff --check` | Passed |
| Python `py_compile` for changed auth/API/persistence/agent/MCP/physics/ML modules | Passed |
| `docker compose ... up -d --build --wait` using authenticated production overlay | Completed successfully for the previous source snapshot; rebuild after final audit/purge edits is awaiting device approval |
| Compose service status | Frontend/FastAPI/PostgreSQL were healthy during the earlier authenticated-stack test; that isolated test stack has since been stopped without deleting its named volumes |
| FastAPI `/health` | UP; database READY; auth_required true |
| Frontend HTTP | 200 |
| PostgreSQL migration level | **9** |
| Authentication smoke check | Admin login, `/auth/me`, admin user list and logout exercised; unauthenticated API returned 401 |
| Production Compose configuration | Validated with a process-scoped test JWT secret and isolated test database |

The production-oriented Compose stack used for this check was a local verification environment, not a public deployment. The stack was built before the final HTTP-denial audit and purged-split code refinements; the latest source passed the 80-test suite, but the rebuild request was stopped at the device approval gate. Its JWT secret and test database must not be reused for a real installation.

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
3. Complete TLS/HTTPS termination, edge rate limiting, CSP/XSS hardening, managed-secret storage, backup/restore drills, monitoring, resource limits and an independent security review before public production exposure. MFA and external OIDC/SSO are not implemented.
4. Configure and verify a real cloud/production deployment, DNS, certificates, operational alerting and rollback. Local Compose is not cloud deployment.
5. Add and validate SCADA/historian/OPC-UA/MQTT integration only when the asset owner supplies authorized endpoints, credentials and signal contracts.
6. Obtain petroleum/mechanical engineering review of the simplified thermal/viscosity/SRP formulations and optimizer operating envelopes. The current CSS–SRP coupling does not solve multiphase reservoir flow, wellbore heat transfer or rod-string wave dynamics. The optimizer does not validate fracture pressure, gearbox torque or API allowable stress.

## Operational commands

Local development (simulation/demo only; do not expose):
```powershell
docker compose up -d --build --wait
```

Authenticated local/production-oriented Compose profile:
```powershell
$env:PETROTWIN_JWT_SECRET = (python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.production.yml run --rm ml-service python scripts/manage_users.py create --username <admin-username> --role admin
```

Run verification:
```powershell
.\.venv\Scripts\python.exe scripts\test_all.py
cd frontend
npm ci
npm run build
npm run test:e2e
```

## Working-tree note

The repository contained substantial pre-existing user modifications and untracked files before this work. Those files were not reset or cleaned. The changes in this checkpoint remain local and have not been pushed as a broad repository commit, because doing so would risk bundling or overwriting the pre-existing work. Review and commit a scoped changeset after inspecting the working tree.


The measured-data training split uses purging at the target timestamp: samples are excluded from the earlier split when their future target would occur on/after the following split's origin boundary. The full 80-test suite passed after this change. HTTP 401/403 authorization denials now generate persisted audit events with path, method, IP, reason and correlation ID.
