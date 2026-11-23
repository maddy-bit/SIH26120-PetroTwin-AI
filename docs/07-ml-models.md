# PETRO-TWIN AI — Current Machine-Learning Architecture

This document distinguishes the existing synthetic/demo predictors from the separate measured-data training lifecycle added for field evidence. The equations and architecture sketches in earlier sections are conceptual design, not proof that all listed algorithms or physics features are implemented.

## Current model families

### 1. Production forecasting

The existing demo forecaster is a physics-baseline plus synthetic-trained residual model. Its output ranges are heuristic and are not calibrated confidence or conformal prediction intervals. Synthetic artifacts are restricted to simulation/demo use and must not be interpreted as field-trained models.

A separate measured-data trainer is implemented in `ml_service/services/field_ml_training.py`:
- Model: scikit-learn StandardScaler + Ridge regression.
- Forecast horizons: 1, 7 and 30 days.
- Inputs: latest VALID temperature, bottomhole pressure, SPM, stroke length and current oil rate measured at or before each forecast-origin time.
- Target: a future VALID oil-rate measurement near the configured forecast horizon.
- Units are checked and features must fall within a maximum age.
- All input and target measurement IDs, source IDs, target times and dataset fingerprints are retained.
- Split: chronological 60/20/20 with target-time purging so a training/validation target cannot cross the next split boundary.
- Hyperparameter: Ridge alpha selected using validation MAE, followed by refitting on pre-test history.
- Baseline: persistence/current oil rate.
- Candidate gate: at least 5% test-MAE improvement over persistence, subject to minimum sample requirements.
- Lifecycle: candidate review required; no automatic promotion. Admin approval, artifact hash verification and fresh VALID inputs are required for field inference.

The training API rejects built-in synthetic BW-DEMO wells and is disabled in simulation mode. The model registry and artifacts are separate from synthetic demo model files. No real field training run has been completed because no permissioned field dataset has been supplied.

### 2. Failure intelligence

The existing failure-risk outputs combine simplified physics scores, synthetic-trained model artifacts and rule-based heuristics. They are not calibrated failure probabilities. There is no independently validated survival model or demonstrated event-prediction lead time.

The UI contribution display is a hand-coded/heuristic attribution, not SHAP or TreeSHAP.

### 3. Sensor anomaly detection

The anomaly path uses the implementation and threshold policy documented in its code/configuration. It is not a verified live 60-second SCADA detector: no historian, continuous field stream, deployment monitor or external event-label dataset is connected.

## Physics/ML boundary

The CSS–SRP coupled model is a shared **simulation-only** chain:
CSS heat/soak → peak thermal state → production cooling → viscosity → SRP load/drag/risk.

It composes existing simplified project models and exposes intermediate values. It is not a validated reservoir/wellbore/rod-string simulator, does not establish field calibration, and does not make operating setpoint recommendations.

## APIs for the measured-data lifecycle

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/models/production?well_id=...` | List candidate/active field model registry entries |
| POST | `/api/v1/models/production/train` | Train a measured-data candidate in field mode |
| POST | `/api/v1/models/{model_id}/promote` | Admin-only explicit promotion after artifact verification |
| GET | `/api/v1/models/production/predict?well_id=...&horizon_days=...` | Use promoted model only, with fresh VALID measurements |

## Evidence and limitations

The trainer's automated tests use deterministic controlled time-series fixtures. They test the code path, split logic, artifact integrity and model lifecycle. They do not establish production forecast accuracy.

A chronological holdout from one well is not independent cross-well validation. Before any field forecast claim, obtain permissioned synchronized well measurements and equipment/context data; evaluate on later unseen periods and/or separate wells; report MAE, RMSE, bias, coverage, baseline comparison and uncertainty by well/cycle; and obtain petroleum-engineering review.

The older synthetic benchmark values in historical slides or documents without a versioned dataset manifest, held-out split, artifact hash and reproducible evaluation run are unverified and must not be used as measured performance claims.
