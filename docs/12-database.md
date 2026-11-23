# PETRO-TWIN AI — Actual Database Schema and Persistence

This document describes the **implemented** repository schema. It supersedes older design sketches in this file that referred to TimescaleDB hypertables, telemetry tables, recommendation tables and a separate audit_logs table. Those objects are not created by the active migrations.

## Database engines and repository boundary

The active application uses one repository implementation with two supported engines:
- **SQLite** for local development and isolated unit/integration tests.
- **PostgreSQL 16** for the Docker Compose runtime.

FastAPI, physics services, the calibration pipeline, ML registry and MCP server share the repository boundary. Spring Boot/Flyway is legacy/dormant and is not the active application database path.

The PostgreSQL connection is configured through `DATABASE_URL`. Docker Compose provisions PostgreSQL 16 and waits for `pg_isready` before starting FastAPI. PostgreSQL data uses a named volume. Field-model files are stored separately in a named artifact volume.

## Versioned migrations

The repository creates `schema_migrations(version, applied_at)` and currently applies versions 1–9.

| Version | Tables / purpose |
|---:|---|
| 1 | `wells`, `analysis_runs` — well configuration and saved analysis payloads |
| 2 | `data_sources`, `measurements`, `ingestion_rejections` — normalized measurements, source identity, quality and rejected-row provenance |
| 3 | `twin_state_snapshots` — persisted digital-twin state snapshots |
| 4 | `well_physical_configurations`, `physics_execution_runs` — versioned physical configuration and physics run payloads |
| 5 | `calibration_datasets`, `calibration_runs`, `calibration_candidates`, `validation_runs`, `validation_policies`, `calibration_candidate_events` — calibration lifecycle and validation records |
| 6 | `css_cycles`, `operational_events`, `srp_operational_records`, `operational_measurement_links` — registered CSS/SRP operational evidence linked to measurement records |
| 7 | `auth_users`, `auth_sessions`, `auth_audit_events` — accounts, revocable sessions and security audit |
| 8 | `agent_runs` — saved evidence-agent responses and MCP traces |
| 9 | `model_registry` — measured-data model lifecycle, validation metrics and artifact checksums |

The migrations use portable repository SQL and JSON text payloads where the domain records are schema-versioned. Do not assume TimescaleDB extensions, hypertables or a high-frequency telemetry schema are installed.

## Key entities

### Wells and measurements

- `wells` stores a well ID and JSON configuration.
- `data_sources` stores a source ID, source type, display name, configured timestamp and latest ingestion timestamp.
- `measurements` stores one variable/value/unit/time/quality observation for a well and source, plus optional external ID and provenance JSON. A uniqueness constraint prevents duplicate observations for the same well/source/time/variable.
- `ingestion_rejections` retains rejected input rows and their reasons.

The application currently supports validated manual CSV/JSON ingestion. No production historian, SCADA, MQTT or OPC-UA connector is configured.

### Calibration and operational evidence

Calibration tables store dataset fingerprints and payloads, calibration runs/candidates, validation policy versions and validation events. Operational records store CSS cycle, operational event and SRP record payloads with stable fingerprints; `operational_measurement_links` associates an operational entity with measured records.

### Authentication and audit

- `auth_users` stores normalized username, salted scrypt password hash, role, active state and timestamps.
- `auth_sessions` stores issued/expiry/revocation times. JWTs are signed but a database session must still be active.
- `auth_audit_events` stores login/logout, account-management, agent/model actions and HTTP access-denial events with correlation ID, IP and JSON details.

Passwords are never stored in plaintext. No default admin account is seeded.

### Agent runs and model registry

`agent_runs` stores question, result, model identifier, actor, status and full MCP tool trace.

`model_registry` stores the well/horizon/model family, lifecycle status, feature schema, dataset fingerprint, sample/split counts, metrics, artifact path and SHA-256. The serialized sklearn model is stored as a separate file under `PETROTWIN_FIELD_MODEL_ARTIFACT_DIR`, mounted to a Compose named volume. Inference and promotion verify artifact integrity before use.

## Retention, backups and operational controls

The current repository implements persistent storage but does not define a managed backup schedule, point-in-time recovery policy, retention policy, archival tier, cross-region replication or verified RPO/RTO. Configure and test those at the deployment environment before public production operation.

No TimescaleDB or external telemetry-store claim is made. High-rate historian ingestion and retention/partitioning strategy require a separately designed and load-tested extension.
