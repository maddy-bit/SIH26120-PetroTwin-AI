# Benchmarking and Evaluation Protocol

## Current evidence status

No reproducible field benchmark has been completed for PETRO-TWIN AI. No field-derived forecast MAE/RMSE, thermal prediction error, rod-floating classification accuracy, net-oil uplift, SOR reduction, unsafe recommendation rate or operational time saving is claimed.

The repository contains synthetic model artifacts, simulation scenarios and controlled unit-test fixtures. They are useful for software regression and sensitivity checks; they are not independent field evidence. Any performance figures in older slides/notes without a versioned dataset, split manifest, model hash, configuration, run trace and evaluation script must be treated as **unverified and excluded from research claims**.

## Separate evaluation cohorts

Never pool these cohorts:

1. **Software fixtures:** deterministic input/output cases for API, physics, calibration, ML lifecycle, authentication and MCP protocol behavior.
2. **Synthetic simulation:** generated CSS/SRP scenarios used to test monotonicity, constraints, scenario sensitivity and optimizer behavior.
3. **Measured single-well development:** permissioned VALID observations used for leakage-safe model fitting and chronological holdout.
4. **Independent field evaluation:** held-out wells/cycles or later periods, approved by a domain owner and not used for feature design, model tuning or threshold selection.
5. **Industrial agent benchmark:** a fixed and versioned task suite with persisted inputs, tool traces, expected evidence and independent grading.

A result from one cohort must not be reported as a result from another.

## Model metrics and baselines

For production forecasting, report at minimum MAE, RMSE, bias, sample count, prediction horizon, well/cycle coverage and comparison against a persistence baseline. Use chronological splitting with target-time purging. Report both aggregate and per-well results; include units and confidence intervals only when their statistical assumptions are justified.

For thermal and viscosity models, report target definitions, sensor location, timestamp alignment, unit handling, calibration/validation periods, MAE/RMSE/bias and residual diagnostics. Do not use one temperature sensor to imply a reservoir-wide thermal field.

For SRP/failure analytics, define the event label, event adjudication source, class prevalence, lead time, precision, recall, F1, PR-AUC, calibration and false-alarm burden. A heuristic risk score is not a calibrated failure probability.

For optimization, compare feasible alternatives using the same validated operating envelope and model versions. Report constraint coverage, sensitivity, Pareto trade-offs and reproducibility; do not claim a global optimum or production improvement without a prospective/retrospective field study.

For an industrial investigation agent, evaluate task completion, evidence correctness, tool selection/call correctness, unsupported-claim rate, abstention when inputs are missing, trace reproducibility, latency/cost and human correction effort. Keep synthetic tasks and real operating cases separate. Human expert grading criteria and disagreements must be recorded.

## AssetOpsBench alignment

The PETRO-TWIN MCP-backed evidence agent provides read-only tools and persisted tool traces that can support an AssetOpsBench-style adapter. This repository has not yet run the official IBM AssetOpsBench task suite and has no official AOB score. An adapter, frozen scenario manifest, expected outcomes, evaluator, repeated runs and human-correction rubric remain necessary before claiming AOB evaluation.

## Reproducibility manifest

Every benchmark release should record:
- git commit and clean/dirty working-tree state;
- dataset ID, source/license/permissions, schema, quality policy and SHA-256 fingerprint;
- excluded record counts and reasons;
- well/cycle/group and time split manifest, including purge boundaries;
- model artifact and physics configuration hashes;
- optimizer constraints/objective weights or agent system prompt/tool schema/provider/model;
- random seeds and dependency/container versions;
- complete run outputs, logs and tool traces;
- metric implementation/version, denominators, uncertainty method and evaluator identity.

## Current conclusion

The project has a software verification suite and controlled simulation checks. It does **not** yet have verified real-world performance numbers. A field dataset, independent engineering validation and a reproducible evaluator are prerequisites for quantitative performance claims.
