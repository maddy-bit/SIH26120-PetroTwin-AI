# Verification, Testing and Quality Assurance

**Last verified locally:** 2026-11-23

## Test layers

| Layer | Coverage |
|---|---|
| Physics unit tests | Monotonic viscosity response, simplified thermal cooling, SRP load/drag response, dynamometer curve shape |
| Coupling tests | CSS heat/soak → production cooling → viscosity → SRP response; input bounds and finite-number checks |
| Data/persistence tests | Schema migrations, repository round trips, quality filters, provenance, restart persistence |
| Calibration tests | Pairing, exclusions, identifiability, bounded fit, chronological validation and baseline comparison |
| Measured-data ML | As-of feature construction, future targets, purged chronological splits, baseline gate, artifact hash, explicit model promotion and fresh-input requirements |
| Agent/MCP | Real stdio MCP protocol, read-only tool allowlist, evidence trace persistence, malicious write-tool rejection, provider-disabled fail-closed behavior |
| Authentication/RBAC | Password hashing, JWT expiry/signature, revocable sessions, role boundaries, last-admin protection, CORS preflight and 401/403 audit records |
| API integration | Request validation, route behavior, health/database readiness, auth requirements and errors |
| Browser E2E | Critical frontend navigation and workflow behavior, including Field Models availability and simulation-mode restrictions |
| Container integration | Authenticated Compose build/start, service health, PostgreSQL schema migration, live admin sign-in and logout |

## Latest local verification

| Command | Result |
|---|---|
| `.venv\\Scripts\\python.exe scripts\\test_all.py` | **80 passed, 0 failed** |
| `npm run build` in `frontend` | Passed; bundle-size warning is advisory |
| `npm run test:e2e -- --reporter=list` in `frontend` | **7 passed, 0 failed** |
| Python `py_compile` over changed backend modules | Passed |
| `git diff --check` | Passed |
| Authenticated local Docker Compose (earlier build) | Frontend, FastAPI and PostgreSQL healthy; DB migration version 9 |

The Python suite uses controlled fixtures. It validates implementation behavior, not real-well accuracy. The browser tests use the local development/demo UI. The Compose checks were performed before the final small purged-split and access-denial-audit changes; the latest source passed the full Python suite, but a final Compose image rebuild is awaiting the Desktop Commander approval panel.

## Reproduce

From the repository root:

```powershell
pip install -r requirements.txt
.\\.venv\\Scripts\\python.exe scripts\\test_all.py
```

Frontend:

```powershell
cd frontend
npm ci
npm run build
npm run test:e2e
```

Authenticated Compose:

```powershell
$env:PETROTWIN_JWT_SECRET = (python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --wait
```

## What these tests do not establish

- A passing test suite does not validate reservoir, wellbore or rod-string physics against an independent field dataset.
- Synthetic/controlled fixture accuracy is not field forecast accuracy.
- A chronological ML holdout from one well is not independent cross-well validation.
- A successful MCP test is not an official AssetOpsBench benchmark score or validation of external LLM reasoning.
- A local authenticated Compose stack is not a cloud production deployment or security certification.
- No live SCADA/historian, telemetry feed, operating control or setpoint dispatch is tested.
