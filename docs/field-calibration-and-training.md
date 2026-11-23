# Field calibration, training, and validation

## Calibration status

The scientific calibration framework builds versioned, provenance-backed datasets from VALID measurements, records excluded rows, supports temporal separation of calibration and validation sets, assesses parameter identifiability, saves candidate configurations, and evaluates explicit versioned validation policies.

Current model-by-model capability:
- **Viscosity:** supported Walther-style fitting adapter for `walther_a`, `walther_b`, and native density, subject to identifiability and validated source configuration.
- **CSS thermal:** candidate data assembly exists, but no fitting adapter is enabled. Temperature must be linked to the injection cycle and post-soak thermal state before parameters can be identified.
- **SRP:** no fitting adapter is enabled. Oil rate alone does not identify geometry/fluid/mechanical parameters; measured dynamometer-card and equipment configuration data are not yet sufficient.

No actual field calibration or external field validation has been performed in this workspace. Controlled fixtures verify algorithm behavior only.

## Measured-data production ML workflow

The new `FieldProductionTrainingService` is separate from `ml_service/train_models.py`. The latter still creates synthetic physics-generated artifacts and must not be described as field training.

The measured-data trainer:
1. Reads a single selected well and date window from the repository.
2. Uses only records whose quality flag is `VALID`; source data that is missing, suspect, non-finite, outside the supported time age, or unit-incompatible is excluded.
3. Builds as-of feature vectors for temperature, bottomhole pressure, SPM, stroke length and current oil rate. Feature measurements must be at or before the origin timestamp and within the declared maximum age.
4. Pairs each origin with a future oil-rate observation near the configured 1-, 7- or 30-day horizon. Targets must occur strictly after the feature timestamp. Target and input measurement identifiers, source IDs and actual horizon are retained for traceability.
5. Sorts observations by origin time and uses chronological 60/20/20 train/validation/test splits. Ridge regularization is chosen using validation MAE; the chosen pipeline is refit on pre-test history only. The final test period is untouched during parameter selection.
6. Compares test MAE against a persistence baseline (the current oil rate). A candidate is eligible for review only if it improves persistence MAE by at least 5% and has the minimum test sample count.
7. Creates a dataset fingerprint, model artifact, SHA-256 digest and registry record. Artifacts are stored under `PETROTWIN_FIELD_MODEL_ARTIFACT_DIR`, which is a named persistent volume in Compose.
8. Leaves the model in `CANDIDATE_REVIEW_REQUIRED` state. It does not replace the synthetic forecaster or activate automatically. An administrator must verify the artifact, review the evidence and explicitly promote it. Promoting a new model retires the previous active artifact for the same well/horizon.
9. The field prediction endpoint loads only an admin-promoted artifact, verifies its SHA-256 and registry metadata, and requires fresh VALID measurements for all features. It returns the source measurement IDs and model/dataset identifiers.

## API

- `POST /api/v1/models/production/train` — train a candidate from a well/date range. Requires engineer/admin in required-auth mode. Body:
  ```json
  {
    "well_id": "FIELD-001",
    "horizon_days": 7,
    "start_at": "2026-01-01T00:00:00Z",
    "end_at": "2026-09-01T00:00:00Z",
    "min_samples": 30,
    "max_feature_age_hours": 72
  }
  ```
- `GET /api/v1/models/production?well_id=FIELD-001` — list model candidates, registry status and holdout metrics.
- `POST /api/v1/models/{model_id}/promote` — admin-only, requires acknowledgement `I_HAVE_REVIEWED_FIELD_MODEL_EVIDENCE`.
- `GET /api/v1/models/production/predict?well_id=FIELD-001&horizon_days=7` — field-only inference using the current promoted model.

Supported forecast horizons are 1, 7 and 30 days. Training requires at least 30 paired examples, including at least 18 training, 6 validation and 6 test examples. If evidence is insufficient or a model fails to beat the persistence baseline, training fails or registers a non-promotable rejection status; it does not fabricate fallback records.

## Verification and external dependencies

The unit tests use controlled time-series fixtures and prove chronological split ordering, no future feature use, valid-data filters, baseline gating, artifact hashing, registry promotion and staleness checks. These fixtures are not real well data and do not establish field performance.

Remaining external work:
- obtain a licensed, quality-reviewed time-series dataset with units, well configuration, source metadata and operating/event labels;
- complete independent well/cycle holdout and engineering review;
- establish accepted MAE/RMSE/bias limits and operating envelopes with the asset owner;
- add drift monitoring, recalibration triggers, rollback and service-level monitoring;
- obtain measured CSS cycle linkage and dynamometer-card/mechanical signals before enabling CSS/SRP calibration adapters.

Chronological validation is an internal model-development check, not a substitute for independent domain validation or operator acceptance. No model in this repository is currently field-validated.


**Leakage control:** chronological split boundaries are purged by target timestamp. Training examples whose future oil-rate label would fall on or after the next validation/test origin boundary are excluded from the corresponding earlier split. The persisted metrics record the number of purged examples and confirm boundary compliance. This reduces temporal label leakage; it does not remove all temporal correlation or establish cross-well/field generalization.
