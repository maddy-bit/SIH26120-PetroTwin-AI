# Operational data schema (version 1.0)

This schema stores operator/importer supplied operational records separately from the existing scalar measurement table. A configuration record describes equipment settings; it is not a measured value. Record quality is an explicit source assertion and does not replace independent sensor QA.

## CSS cycle

`cycle_number` is unique per well. Injection, soak, production restart, and post-soak observation timestamps must be ISO-8601 with timezone offsets. Supplied timestamps are normalized to UTC. Partial timestamps are accepted and the record is marked `INCOMPLETE`; any supplied event sequence that contradicts injection → soak → production → post-soak ordering is rejected. `COMPLETE` means the three phase boundaries exist, not that all scientific inputs or targets are sufficient.

Quantities are objects with `value` and canonical `unit`; optional per-quantity `quality_status` and `provenance` can refine record-level values. Accepted CSS quantities are injection mass (`metric_ton`), steam quality (`fraction`), pressure (`bar`), temperature (`°C`), enthalpy (`kJ/kg`), and supplied energy (`GJ`). Record-level `source` and non-empty `provenance` are required. Injection duration is computed from timestamps; if supplied it must agree.

`post_soak_observation_start` and `post_soak_observation_end` delimit the eligible target window. A `temperature_c` measurement becomes a CSS dataset target only after an explicit measurement association with relation `POST_SOAK_TEMPERATURE` or `TEMPERATURE_TARGET`, only if it falls within this window after production restart, and only when its source metadata explicitly says `measurement_context: RESERVOIR_TEMPERATURE` plus `sensor_reference` or `sensor_depth_m`. A timestamp match alone does not establish a reservoir-temperature target. Production outcomes need an explicit `PRODUCTION_OUTCOME` or `OIL_RATE_OUTCOME` association. No time-nearest association is inferred.

## SRP records

`record_type` is `CONFIGURATION`, `OPERATING_OBSERVATION`, or `INTERVENTION`. Supply either `valid_at` or `valid_from`; optional `valid_to` must not precede `valid_from`. `parameters` is a named map of values with explicit canonical units and quality/provenance. Supported fields cover pump/rod/tubing geometry, stroke and SPM, fluid level/pressure/density/viscosity, production rate, runtime/downtime, efficiency, and load extrema. SRP configuration and observation records remain distinct by `record_type`.

Optional dynamometer records are explicitly typed `DYNAMOMETER_CARD`; each has a timezone-aware measurement time, `load_unit: "N"`, at least two `{position_deg, load_n}` points, quality, and provenance. This schema validates and stores load-card evidence; it does not claim a validated load-card physics model.

## Events and relationships

Supported event types include CSS injection/soak/restart, SRP configuration change, pump replacement, workover, maintenance, shutdown/restart, production interruption, failure, and operator intervention. Events retain well, optional CSS cycle, event time range, external ID, source, provenance, quality, and metadata. Duplicate external IDs and duplicate fingerprints are rejected by persistence. Measurements link through `POST /api/v1/operational-measurement-links`; cross-well and ambiguous multi-cycle associations are rejected. Links preserve original measurement IDs.

Regime labels are stored only when explicitly supplied under `metadata.operating_regime_labels`. No classifier invents a regime.

## Import

JSON uses `POST /api/v1/operational-data/import/json` with:

```json
{
  "schema_version": "1.0",
  "record_type": "css_cycle",
  "records": []
}
```

Operational CSV uses `POST /api/v1/operational-data/import/csv?record_type=...`, `Content-Type: text/csv`, and exactly two columns: `schema_version,record_json`. Each `record_json` cell contains one JSON object. CSV imports accept up to 10 MiB. Rows are validated and persisted independently; the response reports accepted IDs, duplicate count, rejected row numbers/reasons, and this partial-commit behavior. Re-importing an identical row is idempotently reported as a duplicate.

## Operational datasets and readiness

`POST /api/v1/wells/{well_id}/operational-datasets` supports `css_cycle`, `srp`, `css_srp_joint`, `event_aligned`, and `regime_aware` datasets. Rows preserve source records, exact associated measurement IDs/provenance, cycle/event grouping, chronology, exclusions, and a SHA-256 fingerprint. A chronological grouped partition is emitted only when at least two groups exist; otherwise the dataset explicitly reports insufficient groups for a split. Joint rows require an SRP record explicitly carrying the corresponding `metadata.cycle_id`. Regime datasets include only explicitly labeled records.

These are data-readiness datasets, not calibration outputs. CSS and SRP optimizer adapters remain unavailable. “Data linkage ready for domain review” does not mean parameters are identifiable, a model is validated, or an intervention is safe.

## Example only — never field data

The following is a schema illustration only. It is not an observation and must not be uploaded or cited as field evidence:

```json
{
  "well_id": "EXAMPLE_ONLY",
  "cycle_number": 1,
  "injection_start": "2025-01-01T00:00:00Z",
  "injection_end": "2025-01-01T12:00:00Z",
  "soak_start": "2025-01-01T12:00:00Z",
  "soak_end": "2025-01-03T12:00:00Z",
  "production_restart": "2025-01-03T12:00:00Z",
  "injection_mass_tons": {"value": 0, "unit": "metric_ton"},
  "source": "EXAMPLE_ONLY",
  "provenance": {"example": true}
}
```
