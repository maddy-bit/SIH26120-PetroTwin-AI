# Current limitations and external dependencies

This document describes the implementation currently present in the repository as of 2026-11-23. It separates locally verified software behavior from work requiring field evidence or an external deployment environment.

## Integrated components

- **Frontend ↔ Backend:** React routes API workflows through the shared FastAPI client. The AuthGate validates backend health/session and attaches the signed bearer token when auth is required.
- **Field ingestion/persistence:** CSV/JSON measurements are validated, unit-normalized, quality-checked, duplicate-aware and stored with source/provenance/rejection metadata. PostgreSQL in Compose and SQLite locally share the repository interface and versioned migrations.
- **Digital twin physics:** existing thermal, viscosity and SRP models are connected by an explicit CSS → thermal cooling → viscosity → SRP coupling model. Scenario and optimization candidates expose the stage-level input/output chain.
- **Calibration:** versioned measurement datasets, data pairing, identifiability, candidate fitting, temporal separation, policy checks and candidate lifecycle are implemented. The viscosity model is the only enabled fitting adapter.
- **ML:** synthetic demo artifacts remain unvalidated. A separate measured-data training pipeline now creates candidate models from VALID records, uses chronological splits, compares against persistence, records dataset/artifact provenance, and requires explicit admin promotion.
- **Optimization:** finite-grid search, weighted ranking, nondominated filtering and the coupled simulation model are connected. It is not NSGA-II/SLSQP and does not evaluate every theoretical engineering constraint.
- **Agents/MCP:** an LLM-backed evidence investigation runtime is connected to the read-only MCP server. It requires a configured OpenAI-compatible provider and fails closed if no provider is configured. The old deterministic simulation supervisor remains for legacy demo actions.
- **Security:** required-auth mode adds signed sessions, scrypt password hashes, viewer/engineer/operator/admin roles, request-level authorization, user management and audit events. The production Compose override requires a JWT secret. Local dev may run explicitly without auth.
- **Database/artifacts:** schema migrations cover auth, agent runs and model registry in addition to domain/calibration data. PostgreSQL data and measured model artifacts use Compose named volumes.

## Remaining limitations

### Field data and engineering
- No live SCADA/historian/MQTT/OPC-UA adapter, credentials, signal dictionary or operator dataset is configured. Manual CSV/JSON ingestion is the current field-data boundary.
- No real field calibration, out-of-sample field validation, or asset-owner acceptance has been performed.
- Thermal, viscosity, wellbore and SRP calculations remain simplified project models requiring independent petroleum/mechanical engineering review.
- The CSS–SRP coupling is **simulation only**, reports `field_eligible=false` and `NOT_CALIBRATED_ON_FIELD_DATA`. It does not solve multiphase reservoir flow, wellbore heat transfer, rod-string wave dynamics or dynamometer-card inversion.
- CSS thermal and SRP parameter fitting are blocked until cycle-linked temperature and adequate mechanical/dynamometer data are available.
- The field ML trainer requires an adequate time series. It cannot be executed meaningfully on the currently empty/no-field-data dataset. A chronological holdout is not independent field validation.
- Failure-risk outputs remain heuristic/not probability-calibrated; forecast intervals remain uncalibrated.
- The optimizer checks only its coded constraints. Formation fracture pressure, gearbox torque and API allowable stress are explicitly not evaluated. No setpoint dispatch is implemented.

### Agent and security
- The LLM agent needs an externally configured OpenAI-compatible endpoint/model and provider key. No live provider credential is configured in the current environment.
- The MCP agent can only read the application's registered evidence; no write/action tools are exposed. This is not a full autonomous operator or official IBM AssetOpsBench benchmark integration.
- Application authentication/RBAC and local Nginx CSP/security headers and login/API rate limits are implemented. Public HTTPS/TLS termination and HSTS, trusted ingress, managed secret storage/rotation, off-host backups/restore, monitoring and external security testing remain prerequisites before public exposure.
- No external OIDC/SSO integration or MFA exists. Browser bearer tokens use session storage; CSP reduces exposure but does not replace secure frontend code review and XSS testing.
- User-supplied role/configuration metadata does not by itself constitute independent asset-owner authorization.

### Deployment and operations
- The authenticated hardened Compose profile has been built and smoke-tested locally; this is not a public production release.
- No cloud deployment, DNS/TLS, centralized monitoring, alerting, backup schedule or disaster-recovery RPO/RTO has been established.
- Spring Boot remains legacy/dormant source and is not in the canonical runtime.
- Model registry candidate lifecycle does not yet include automated drift monitoring, scheduled retraining or statistical rollback policy.
- Inference and agent timeouts, concurrency limits, resource quotas and provider billing limits require deployment-specific operational tuning.

## Verification record

The local authenticated hardening run completed on 2026-11-23: 80 Python tests and 7 browser E2E tests passed, the TypeScript/Vite production build passed, and the latest hardened Compose stack reached healthy status. Nginx headers/rate limits, login/RBAC/revocation, private API binding, non-root/read-only containers, migration 9 and PostgreSQL restart persistence were checked. Lint had 23 warnings and zero errors. This evidence does not establish a secure public production deployment.

No real field dataset or external field-validation report is present. Therefore field validation remains **NOT ESTABLISHED**.
