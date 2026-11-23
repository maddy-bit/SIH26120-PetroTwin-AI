# PETRO-TWIN AI — five-minute local demonstration

## Before the demo

Choose one environment deliberately:

- **Simulation/demo mode:** built-in BW-DEMO wells and generated telemetry are available. Every output is synthetic/simulation-only.
- **Field mode:** no synthetic wells are created. Register an actual well and ingest permissioned measurements with canonical units, source metadata and VALID/SUSPECT quality status. If no data is loaded, the correct result is an explicit unavailable/blocked state.

For the authenticated Compose profile, set a unique JWT secret and create the first admin with scripts/manage_users.py. The default development profile has authentication disabled and must not be exposed to a shared/public network.

The Evidence Copilot requires PETROTWIN_AGENT_BASE_URL and PETROTWIN_AGENT_MODEL, plus an API key where the provider requires it. Without these, its investigation endpoint returns HTTP 503; do not imply an LLM response has been generated.

## Demonstration flow

1. **System health and sign-in:** show /health database readiness, required-auth status and the authenticated user/role.
2. **Field Data:** register a well, ingest CSV/JSON, inspect accepted/rejected counts, units, provenance and data quality. Use a supplied approved dataset only.
3. **Coupled Scenario Lab:** in simulation mode, vary steam mass, soak, production day, stroke and SPM. Show the returned CSS heat → cooling → viscosity → SRP trace and its explicit SIMULATION_ONLY / not-calibrated status.
4. **Optimization:** run the finite-grid review. Explain its implemented constraints, weights, fixed horizon and excluded engineering limits. It does not dispatch setpoints and is not a validated global optimum.
5. **Evidence Copilot:** ask a read-only evidence question. Show the retrieved source IDs/timestamps/units and stored tool trace. If no LLM provider is configured, show the service-disabled state instead of fabricating an answer.
6. **Field Models:** show measured-data candidate requirements, chronological/purged train-validation-test split, persistence baseline, model registry and explicit admin promotion. Without enough field measurements, the trainer must reject the attempt. Controlled fixture tests are not a trained field model.

## Claims to avoid

Do not call synthetic telemetry field data, do not claim real field calibration/validation, do not report unverified performance figures, do not present heuristic failure scores as calibrated probabilities, and do not describe any output as an operating setpoint.
