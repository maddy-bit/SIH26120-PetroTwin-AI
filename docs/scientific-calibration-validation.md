# Scientific calibration and temporal validation

## Evidence levels

The implementation distinguishes algorithm checks on controlled fixtures from calibration of persisted observations, chronological validation, domain review, and operational approval. No real field dataset was present in this implementation session. Test fixtures are identified as controlled test data. A completed optimizer run is not field validation; validation passes only against an explicit, versioned, operator/research-defined policy. Authentication/RBAC is absent, so candidate approval and configuration activation are disabled.

## Model audit

| Model | Equations actually executed | Configurable and fixed values | Identifiability and data requirements | Current limitations |
|---|---|---|---|---|
| Viscosity | `physics/viscosity_model.py`: temperature is clamped to 10–350 °C; `T_K=T_C+273.15`; `rho_g_cm3=(rho0/1000)*(1-0.0007*(T_C-47))`, clamped 0.75–1.05; `z=clamp(A-B*log10(T_K),-1,2.5)`; `nu_cSt=max(1,10^(10^z)-0.7)`; `mu_cP=nu*rho`; when pressure >55 bar, multiply by `exp(0.0025*(P-55))`; result rounded to 0.01 cP. | Field configuration: Walther `A`, `B`, and native density `rho0`. API gravity is accepted as optional metadata but the current equation does not read it. Fixed: reference temperature 47 °C, expansion coefficient, density and exponent clamps, 55 bar reference, pressure coefficient, output rounding. | `viscosity_cp` target paired to `temperature_c` and `bottomhole_pressure_bar`; no input reuse, nearest timestamp within explicit tolerance. Local central finite-difference Jacobian of log output, matrix rank/condition and maximum sensitivity-column correlation. Calibratable: selected subset of A, B, native density only when selected parameters are potentially identifiable and operator bounds are supplied. | Model docstring describes a Beggs–Robinson fallback that is not implemented. Local identifiability is not global uniqueness. Output rounding makes tiny optimizer differences unusable, so a documented wider finite-difference step is used. No real lab observations were available here. |
| CSS thermal | `physics/thermal_model.py`: injected heat `M*1000*(Cp_water*(T_steam-T_native)+quality*latent_heat)`; retained heat multiplies fixed efficiency 0.72 and `exp(-0.012*soak_days)`; bulk heat capacity includes rock configuration and fixed oil density 945 kg/m³ and oil Cp 2.1 kJ/kg/K; estimated radius uses fixed target ΔT factor 0.75, minimum heated volume/radius guard and 45 m cap; peak is clipped between native+15 °C and steam−25 °C. | Ten well configuration values for native/steam temperatures, steam quality/latent/sensible heat, thickness, porosity, rock density/Cp, and conduction decay. Fixed constants listed in the equation description remain assumptions. | Required field inputs: cycle mass and soak duration, injection conditions, and a measured temperature explicitly linked to the same cycle inside its post-soak observation window. Migration 6 now represents cycles and associations. The schema still does not establish sensor depth/reference or that the reading is the modeled reservoir peak. | Cycle-aware dataset rows are possible only with explicit links and window timestamps. CSS calibration remains disabled: no fit adapter or CSS parameter sensitivity assessment is implemented, and sensor context is not sufficient to interpret a temperature target. |
| SRP | `physics/srp_model.py`: crank kinematics; buoyant rod and fluid loads; Couette/valve drag; polished-rod loads; displacement/fillage; power; empirical floating-risk logistic score. | Seven explicit pump/rod/fluid geometry values. Fixed: 30 mm valve port, 1.2 m plunger length, valve factor 0.65, default fillage 0.88, sinker weight factor 0.30, motor efficiency 0.82, and empirical risk coefficients. | Existing measured target can be oil rate paired with stroke, SPM, and viscosity. Oil rate alone cannot separate pump depth, plunger area, rod weight, density, fillage and omitted lift/condition effects. Dynamometer load observations are not supported by the measurement schema. | Dataset inspection is supported; parameter fitting is blocked. No CSS outputs are consumed by SRP, so no coupled calibration/validation claim is made. |
| Production/reservoir | No independent field physics engine is implemented. | N/A | N/A | The existing production forecaster is a synthetic-trained ML/hybrid path and is not used by this calibration service. |

The API-gravity input is unused by the implemented viscosity equation and is not required for field execution or fitted. `native_density_kg_m3` is a configurable input and may be assessed/fitted only from the selected viscosity data and explicit bounds. Other physical configuration values stay fixed during each fit.

## Dataset construction

`POST /api/v1/wells/{well_id}/calibration-datasets` takes model, explicit timezone-aware period, pairing tolerance, and role. It reads only persisted measurements. It filters non-`VALID`, noncanonical, nonfinite, and out-of-model-range records; deduplicates same-variable/same-timestamp rows deterministically; pairs each target to nearest inputs within the requested interval; and never reuses an input measurement. Every row preserves measurement IDs, source IDs, timestamps, and ingestion provenance, including original units/values where recorded. Dataset metadata includes excluded record IDs/reasons, input variation, temporal coverage, pairing policy and SHA-256 fingerprint.

Historical data are allowed for calibration/held-out periods based on their ingestion quality flag. Operational snapshot/execution freshness remains 24 hours. Ingestion currently assigns `VALID` after schema, unit, range and timestamp checks; it does not include sensor-health flags, so `VALID` is not independent sensor QA. Operating regime detection reports unavailable because there are no regime labels. CSS datasets intentionally contain no linked observations unless the schema is extended with cycle semantics.

## Identifiability and fit

The viscosity assessment computes a central finite-difference sensitivity matrix of log predicted cP against selected parameters. It reports observation count, temperature span, matrix rank, condition number, maximum absolute sensitivity-column correlation, and per-parameter evidence. The 0.995 column-correlation and 1e8 condition diagnostics are numerical screening rules, not petroleum acceptance thresholds. Data must exceed the free parameter count and span temperature; weak or insufficient parameters cannot be fitted. A model can still be structurally misspecified when numerical identifiability passes.

The only optimizer is bounded SciPy trust-region reflective least squares with a fixed linear loss, explicit per-parameter bounds, log residuals, and a finite-difference step chosen to exceed the model’s 0.01 cP output rounding. Optimizer/library versions, initial/final values, convergence, bounds, residuals and local Jacobian covariance (only when full rank with positive degrees of freedom) are stored. The covariance is labeled a local Gaussian approximation, not a field confidence interval. No stochastic optimizer or random split is used.

## Temporal validation and policy

Calibration and validation are separate time windows. Validation must start after the calibration end plus the requested gap; shared target measurement IDs are rejected. Validation reports calibrated physics, original physics, and a last-calibration-observation persistence baseline. Supported metrics are MAE, RMSE, prediction-minus-observation bias, mean absolute relative error for nonzero viscosity, and R² only when at least two observations have nonzero target variance. Time-series predictions, residuals, target IDs, and all metric outputs are persisted.

There is no default acceptance threshold. A policy must be explicitly set at `/api/v1/models/viscosity/validation-policy`, with an owner, name, minimum validation count, metric thresholds and an automatically versioned policy version. `VALIDATION_PASSED` means only that this candidate met that configured policy on its held-out period; it does not assert independent field validation or operational safety.

## Candidate lifecycle and security boundary

Candidates are persisted separately from active well configuration. The supported transitions are `DRAFT → CALIBRATION_COMPLETED → VALIDATION_PENDING → VALIDATION_PASSED → APPROVAL_PENDING`; optimizer nonconvergence is `CALIBRATION_FAILED`, validation can fail or remain pending, and a candidate may be rejected with a recorded reason. Candidate rejection is explicitly an unprotected development action. Approval returns HTTP 403 because the application has no authenticated identity/RBAC/audit authority. Activation is disabled; active configuration history therefore returns no active candidate. A candidate’s fitted values remain `UNVALIDATED` and never modify the well’s physical configuration.

## APIs

- `POST /api/v1/wells/{well_id}/calibration-datasets`
- `GET /api/v1/calibration-datasets/{dataset_id}`
- `POST /api/v1/calibration-datasets/{dataset_id}/identifiability`
- `POST /api/v1/wells/{well_id}/calibrations`
- `GET /api/v1/calibrations/{calibration_id}`
- `PUT|GET /api/v1/models/{model_id}/validation-policy`
- `POST /api/v1/calibration-candidates/{candidate_id}/validate`
- `GET /api/v1/validation-runs/{validation_id}`
- `GET /api/v1/calibration-candidates/{candidate_id}` and `GET /api/v1/wells/{well_id}/calibration-candidates`
- `GET /api/v1/calibration-candidates/{candidate_id}/comparison`
- `POST /api/v1/calibration-candidates/{candidate_id}/reject`
- `POST /api/v1/calibration-candidates/{candidate_id}/approve` (disabled with HTTP 403)
- `GET /api/v1/wells/{well_id}/active-calibration-history` (activation disabled)

Persistence uses schema migration 5 for calibration and schema migration 6 for operational events, CSS cycles, SRP records, and measurement associations. The new operational records and datasets survive repository reopen/restart tests.

## Claims and limitations

- **Algorithm verified by controlled tests:** yes, deterministic test fixture only.
- **Calibration executed:** yes, in a controlled persisted API test; this is not real field evidence.
- **Convergence achieved:** yes for the controlled viscosity fixture only.
- **Chronological validation performed:** yes in a controlled fixture/API test against an explicit test-only policy.
- **Validation policy passed:** controlled fixture only; thresholds were test-only and deliberately permissive.
- **Real field calibration or validation:** none in this phase.
- **Operational approval/activation:** disabled.

Genuine use requires provenance-verified field viscosity observations over sufficiently varied temperatures and pressures, independently measured viscosity targets, a reviewed sensor-quality protocol, domain-approved parameter bounds, and an untouched later validation period. CSS additionally needs complete cycle records, mass/quality/pressure/temperature inputs, soak and restart boundaries, cycle-linked post-soak temperature and production outcomes, and sensor location/reference. SRP needs valid time-versioned pump configuration, synchronized operating observations, production/runtime/downtime outcomes, and load-card evidence when testing load-dependent parameters. A coupled assessment needs repeated joint cycle-level CSS and SRP records with explicit cycle associations and enough operating variation to investigate interaction effects. None of these operational records alone provides a calibration adapter or proves identifiability.
