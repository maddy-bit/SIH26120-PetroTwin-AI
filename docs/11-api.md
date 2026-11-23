# PETRO-TWIN API (implemented contract)

FastAPI is the only active application API. Interactive documentation is available at `/docs` in local development and disabled when `PETROTWIN_AUTH_MODE=required`. The built-in demo wells are synthetic and appear only in simulation mode; field mode uses registered well records. Requests validate bounds and reject unknown well IDs.

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/health` | Liveness plus database readiness and simulation mode |
| `GET` | `/models` | Model availability and synthetic-data caveats |
| `GET` | `/api/wells` | Registered wells; built-in demo wells appear only in simulation mode |
| `GET` | `/api/wells/{well_id}` | Stored well configuration |
| `GET` | `/api/wells/{well_id}/state` | Generated current simulation state |
| `GET` | `/api/wells/{well_id}/telemetry` | Generated telemetry frame |
| `GET` | `/api/wells/{well_id}/production?days=60` | Generated history for charting |
| `GET` | `/api/wells/{well_id}/time-machine/{day}` | Synthetic state projection for a cycle day (0–180) |
| `GET` | `/api/wells/{well_id}/css` | CSS history from deterministic supervisor |
| `GET` | `/api/wells/{well_id}/srp` | SRP history from deterministic supervisor |
| `GET` | `/api/wells/{well_id}/srp/dyno-card` | Generated dynamometer card |
| `GET` | `/api/wells/{well_id}/analysis-runs` | Saved user-triggered forecast/optimization runs |
| `POST` | `/predict/production` | Point estimates and uncalibrated heuristic ranges; saved as an analysis run |
| `POST` | `/predict/failure` | Modeled risk outputs and heuristic contributions; not persisted on polling |
| `POST` | `/predict/viscosity` | Simplified viscosity calculation |
| `POST` | `/predict/temperature` | Simplified temperature projection |
| `POST` | `/detect/anomaly` | Synthetic-baseline/threshold anomaly result |
| `POST` | `/simulate/css` | CSS what-if calculation and cooling curve |
| `POST` | `/simulate/srp` | SRP calculation and card points |
| `POST` | `/simulate/scenario` | Simplified scenario evaluation for a selected configured well |
| `POST` | `/optimize/joint` | Finite grid search; recommendation saved and run ID returned |
| `POST` | `/api/copilot/query` | Keyword-routed deterministic response |
| `WS` | `/ws/telemetry/{well_id}` | Generated synthetic telemetry stream |

Pydantic request models enforce numeric ranges and reject unknown fields. Unknown well IDs return HTTP 404; invalid request bodies return 422. CORS origins are configured with `CORS_ORIGINS`. When `PETROTWIN_AUTH_MODE=required`, protected HTTP/WebSocket routes require a valid bearer session and role-specific permissions; health and login are public. The hardened Compose profile adds Nginx CSP/security headers and login/API rate limits, plus non-root/read-only/resource-constrained containers. Public TLS/ingress, managed secrets, off-host backups, monitoring and independent security review remain deployment responsibilities. No operating setpoint dispatch exists.

## Scenario input semantics

`POST /simulate/scenario` accepts `well_id`, `steam_volume`, `soak_time`, `production_cutoff`, `stroke_length`, and `spm`. Steam volume and soak time feed the thermal calculation; stroke and SPM feed the SRP calculation. The selected well's current cycle day is used for its thermal-decay estimate. `production_cutoff` is the estimated production horizon in days and scales estimated cycle oil and SOR; it does not change the instantaneous production-rate estimate. The response includes estimated injected/retained heat, heated radius, and estimated cycle oil so these assumptions are inspectable.

Injection pressure is currently unsupported because the thermal model uses fixed steam properties; it is not accepted by this request. VFD frequency is derived from SPM using the project's fixed conversion factor and is not an independent input. Because request models forbid extra fields, sending either unsupported value returns HTTP 422. These outputs are simplified simulation estimates, not field-calibrated forecasts.

The legacy Spring Boot API/schema is not in the active UI path. Older endpoints, STOMP topics, approval routes, calibrated confidence intervals, and event-stream claims in prior docs are not implemented by the current FastAPI contract.

## Field measurements and traceable state

In field mode, use `POST /api/v1/wells` to register a well, then `POST /api/v1/measurements` or `POST /api/v1/measurements/csv?source_id=...` to ingest supported measurements. CSV headers: `well_id,measured_at,variable,value,unit`, with optional `external_id`. Responses contain an ingestion batch ID, accepted/duplicate counts, and rejected row reasons. The raw submitted value/unit and source record ID are recorded in each normalized measurement's provenance JSON; database columns retain the normalized value/unit.

`GET /api/v1/wells/{well_id}/measurements?days=90&variable=oil_rate_bpd&quality_status=VALID` supports per-well time/type/quality filtering. `GET /api/v1/wells/{well_id}/data-quality?window_days=30` returns observed counts, time coverage, stale types, suspect count, and an explicit data-readiness state. `POST /api/v1/wells/{well_id}/twin-state?window_hours=168` constructs and persists a versioned snapshot. It selects fresh, valid observations, includes source measurement references, and reports missing inputs and physics/calibration availability. It does not interpolate, invent values, calculate an unvalidated completeness score, or produce uncertainty estimates.

No real field calibration or validation has been performed. A controlled calibration/temporal-validation framework is described below and in `scientific-calibration-validation.md`; the candidate outputs are not enabled for field decisions. Authentication and role checks are enforced when `PETROTWIN_AUTH_MODE=required`. Local development can explicitly run with authentication disabled; do not expose that mode to shared/public networks.

## Versioned physics execution

| Method | Path | Behavior |
|---|---|---|
| `PUT` | `/api/v1/wells/{well_id}/physical-configuration` | Validate and persist a new well configuration version. Each parameter requires `value`, canonical `unit`, `source`, `classification`, and `validation_status`. |
| `GET` | `/api/v1/wells/{well_id}/physical-configuration` | Retrieve the latest persisted configuration. |
| `GET` | `/api/v1/wells/{well_id}/physics-eligibility?snapshot_id=...` | Evaluate model input eligibility for a specific persisted snapshot and latest configuration. |
| `POST` | `/api/v1/wells/{well_id}/physics-runs` | Execute eligible existing models for `{ "snapshot_id": "...", "configuration_version": 1 }`. Configuration version is optional; when given it must match the current version. |
| `GET` | `/api/v1/physics-runs/{run_id}` | Retrieve persisted execution details, consumed inputs, configuration version, outputs, assumptions, errors, and validation limitations. |
| `GET` | `/api/v1/wells/{well_id}/physics-runs?limit=50` | List persisted runs for the well. |
| `GET` | `/api/v1/physics-runs/{run_id}/comparisons` | Compare directly compatible single-snapshot outputs with measurements when present. This is informational, not calibration/validation. |
| `GET` | `/api/v1/wells/{well_id}/calibration-eligibility?days=365` | Read-only observation count and coverage screening; it never fits or activates parameters. |

Configuration versions and execution runs use database schema migration 4. Eligible models require fresh (`<=24h`) `VALID` measurements with canonical units and every required explicit configuration parameter validated and non-assumed. Physics output statuses distinguish `EXECUTED`, `BLOCKED`, and `FAILED`; the eligibility endpoint reports `ELIGIBLE` or `BLOCKED` before execution. Independent models can execute partially. Each run snapshots the configuration ID/version and actual measurement provenance it consumed.

Current supported executions are viscosity, CSS thermal response, and SRP mechanics. Production/reservoir physics and a coupled CSS–SRP model return blocked reasons because no supported field implementations exist. Existing model outputs remain simplified and uncalibrated. Calibration eligibility is `NOT_ASSESSED` until domain owners approve sample, temporal coverage, identifiability, and quality thresholds. The `validation_status` field is operator-supplied metadata; it is not independent evidence of field validation. In required-auth mode the user/approval actions are role-gated and written to the security audit table.

## Scientific calibration and chronological validation

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/wells/{well_id}/calibration-datasets` | Build and persist a period-scoped dataset from persisted measurements with target/input timestamp pairing, exclusions, source IDs, and SHA-256 fingerprint. |
| `GET` | `/api/v1/calibration-datasets/{dataset_id}` | Retrieve exact dataset rows, provenance, filters, and fingerprint. |
| `POST` | `/api/v1/calibration-datasets/{dataset_id}/identifiability` | Finite-difference/SVD sensitivity assessment for selected model parameters. Optional body: `{ "parameter_names": ["walther_a", "walther_b"] }`. |
| `POST` | `/api/v1/wells/{well_id}/calibrations` | Execute bounded viscosity calibration only. Requires dataset ID, selected identifiable parameters, and explicit bounds. Persists a separate candidate. |
| `GET` | `/api/v1/calibrations/{calibration_id}` | Retrieve fit diagnostics, metrics, residuals, identifiability, and candidate reference. |
| `PUT` / `GET` | `/api/v1/models/{model_id}/validation-policy` | Save/retrieve explicitly owned, versioned model-specific metric thresholds and minimum validation count. No default acceptance limits are supplied. |
| `POST` | `/api/v1/calibration-candidates/{candidate_id}/validate` | Evaluate a later chronological period after an explicit temporal gap; compares calibrated/original physics with a persistence baseline. |
| `GET` | `/api/v1/validation-runs/{validation_id}` | Retrieve held-out metrics, predictions, residual series, policy checks, and provenance. |
| `GET` | `/api/v1/calibration-candidates/{candidate_id}` | Retrieve candidate configuration and lifecycle audit events. |
| `GET` | `/api/v1/calibration-candidates/{candidate_id}/comparison` | Retrieve latest and prior persisted temporal comparisons with predictions, residuals, metrics, and candidate parameter changes. |
| `GET` | `/api/v1/wells/{well_id}/calibration-candidates` | List candidate configurations for a well. |
| `POST` | `/api/v1/calibration-candidates/{candidate_id}/reject` | Record a rejection reason; admin-only in required-auth mode. |
| `POST` | `/api/v1/calibration-candidates/{candidate_id}/approve` | Record an admin-authorized approval with audit event in required-auth mode. |
| `GET` | `/api/v1/wells/{well_id}/active-calibration-history` | Reports activation disabled and no active candidate. |

These records use database schema migration 5. Only viscosity has a calibration optimizer adapter. Cycle-linked CSS observations are included only with explicit post-soak measurement links, but CSS fitting remains disabled because there is no CSS sensitivity/fitting adapter and sensor context is not represented. SRP readiness records are structured, but SRP fitting remains disabled because existing oil-rate physics cannot separate pump, fluid, fillage, and load effects. No random split is used. Model-specific equations, numerical identifiability diagnostics, and scientific limits are documented in `scientific-calibration-validation.md`. A policy pass on a controlled fixture is not field validation.

## Petroleum operational records

Database migration 6 adds versioned operational records. Full JSON fields, units, validation, and provenance rules are specified in `operational-data-schema.md`.

| Method | Path | Behavior |
|---|---|---|
| `POST` / `GET` | `/api/v1/wells/{well_id}/css-cycles` | Create and list cycle records; partial phase histories are explicitly `INCOMPLETE`. |
| `GET` / `PUT` / `DELETE` | `/api/v1/css-cycles/{cycle_id}` | Inspect, update, and archive a CSS cycle. Delete is a soft archive; source evidence remains stored. |
| `POST` / `GET` | `/api/v1/wells/{well_id}/operational-events` | Create/list intervention, operating, and CSS phase events. |
| `GET` / `PUT` / `DELETE` | `/api/v1/operational-events/{event_id}` | Retrieve, edit, or soft-archive an event. |
| `POST` / `GET` | `/api/v1/wells/{well_id}/srp-records` | Store/list time-valid SRP configuration separately from operating observations; typed dynamometer cards are supported. |
| `GET` / `PUT` / `DELETE` | `/api/v1/srp-records/{record_id}` | Retrieve, edit, or soft-archive an SRP record. |
| `POST` | `/api/v1/operational-measurement-links` | Explicitly associate a same-well measurement to a cycle/event/SRP record; cycle ambiguity is rejected. |
| `POST` | `/api/v1/operational-data/import/json` | Schema-versioned JSON batches; each accepted row commits independently and rejected rows are reported. |
| `POST` | `/api/v1/operational-data/import/csv?record_type=...` | CSV envelope with `schema_version,record_json` columns. |
| `GET` | `/api/v1/wells/{well_id}/operational-timeline` | Chronologically list persisted operational records and measurement links. Regime inference is unavailable; only explicit labels are reported. |
| `GET` | `/api/v1/wells/{well_id}/operational-calibration-readiness` | Report CSS, SRP, and joint-data blockers. Data linkage is not calibration readiness or validation. |
| `POST` | `/api/v1/wells/{well_id}/operational-datasets` | Persist cycle, SRP, joint, event-aligned, or explicitly regime-labeled datasets with provenance, fingerprint, exclusions, and chronological grouped split when enough groups exist. |

Migration 6 persists operational events, CSS cycles, SRP records, and measurement associations across restarts. No CSS/SRP/coupled calibration adapter was added. See `operational-data-schema.md` for exact accepted fields, units, and example-only schema.


## Current integrated API additions (2026-11-23)

The detailed route list above describes the domain/measurement/physics/calibration/operational-data APIs. The following APIs were added during the integration work described in `integration-status.md`:

### Authentication

| Method | Path | Permission |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Public |
| `GET` | `/api/v1/auth/me` | Authenticated |
| `POST` | `/api/v1/auth/logout` | Authenticated; revokes current session |
| `GET` | `/api/v1/auth/users` | Admin |
| `POST` | `/api/v1/auth/users` | Admin |
| `PATCH` | `/api/v1/auth/users/{username}` | Admin |
| `GET` | `/api/v1/auth/audit-events` | Admin |

In `PETROTWIN_AUTH_MODE=required`, all application HTTP API routes and the telemetry WebSocket require a signed database-backed bearer session and role authorization. The health route and login are public. See `security-authentication.md` for bootstrap and role policy.

### Agent and MCP

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/v1/agent/status` | Authenticated |
| `POST` | `/api/v1/agent/investigate` | Engineer/admin |
| `GET` | `/api/v1/agent/runs?well_id=...` | Authenticated |

The investigation runtime uses the official read-only MCP server over stdio and a configured OpenAI-compatible chat-completions provider. Seven evidence tools are called before synthesis. The API returns HTTP 503 when the provider is not configured. Persisted run traces use `agent_runs`. This is not an official IBM AssetOpsBench score or a production autonomous controller.

### Measured-data model lifecycle

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/v1/models/production?well_id=...` | Authenticated |
| `POST` | `/api/v1/models/production/train` | Engineer/admin; field mode only |
| `POST` | `/api/v1/models/{model_id}/promote` | Admin with explicit review acknowledgement |
| `GET` | `/api/v1/models/production/predict?well_id=...&horizon_days=...` | Authenticated; promoted model, field mode and fresh VALID features required |

Training consumes VALID measured records from one non-demo well, builds time-safe features and future targets, uses a purged chronological train/validation/test split, compares with a persistence baseline, hashes the artifact and registers a candidate. Promotion is explicit; no model is activated automatically. A chronological holdout is not independent field validation.

### Coupled CSS–SRP simulation

The `POST /simulate/scenario` route and `POST /optimize/joint` candidate calculations now use the same `CoupledCssSrpModel`. Both expose the CSS heat/soak → cooling → viscosity → SRP mechanics trace. This model is explicitly `SIMULATION_ONLY`, `field_eligible=false` and `NOT_CALIBRATED_ON_FIELD_DATA`. It is distinct from the versioned field-physics execution API, which still blocks unvalidated field model runs.

### Compatibility notes

- `POST /api/copilot/query` remains a deterministic legacy route. The React Evidence Copilot uses `POST /api/v1/agent/investigate`.
- `GET /docs` and `/openapi.json` are disabled in required-auth mode; use the local authenticated API contract and docs rather than exposing schema publicly.
- No route dispatches well operating setpoints or connects to SCADA/historian control systems.
