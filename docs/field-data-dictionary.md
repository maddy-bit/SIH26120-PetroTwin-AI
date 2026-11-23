# Field measurement dictionary and calculation support

## Ingestion contract

CSV headers are `well_id,measured_at,variable,value,unit`; optional `external_id`, `quality_status` (`VALID` or `SUSPECT`), and `metadata_json` preserve source record identity, explicit quality, and sensor context. JSON uses the corresponding `metadata` object. For CSS temperature targets, explicit `measurement_context: RESERVOIR_TEMPERATURE` and `sensor_reference` or `sensor_depth_m` are required in measurement metadata. If quality is omitted, ingestion marks a record `VALID` after schema, unit, range, and timestamp checks; this is not independent sensor QA. Timestamps must include a timezone and are stored normalized to UTC. Unsupported columns, unknown/ambiguous units, non-finite values, out-of-range values, and future timestamps beyond five minutes are rejected with row-level reasons. Historical records are not marked suspect solely due to age; snapshots and physics execution enforce their separate 24-hour operational freshness limit. Reingestion of the same well/source/time/type is idempotent.

## Supported measurements

| Variable | Canonical unit | Accepted units |
|---|---|---|
| `oil_rate_bpd`, `water_rate_bpd` | bbl/day | bbl/day, bbl/d |
| `gas_rate_m3_day` | m3/day | m3/day, m³/day |
| `temperature_c` | °C | C, °C |
| `bottomhole_pressure_bar`, `wellhead_pressure_bar`, `injection_pressure_bar` | bar | bar, kPa, psi |
| `steam_injected_tons` | metric_ton | metric_ton, tonne |
| `days_in_production`, `soak_days` | day | day, days |
| `spm` | stroke/min | SPM, stroke/min |
| `stroke_length_m` | m | m |
| `vfd_frequency_hz` | Hz | Hz |
| `viscosity_cp` | cP | cP |

kPa converts at 0.01 bar/kPa; psi at 0.0689475729 bar/psi. Original submitted value/unit are not currently separate database columns; canonical value/unit are stored and the ingestion provenance identifies the contract/source. Source record IDs are stored as `external_id`.

## Field state and support matrix

`POST /api/v1/wells/{well_id}/twin-state?window_hours=168` persists a versioned snapshot. It selects the latest `VALID` observation per type inside the window and freshness cutoff (24 hours), returns measurement IDs, stale/suspect/missing types, and reports calibration/training status. It does not interpolate or fill missing measurements. Completeness is intentionally unscored.

| Calculation | Minimum observed inputs | Current field support |
|---|---|---|
| Viscosity estimate | temperature, bottomhole pressure | Runs only with explicit validated Walther/crude configuration; remains uncalibrated |
| SRP mechanics | stroke length, SPM, measured fluid viscosity | Runs only with explicit validated pump/rod/fluid configuration; remains uncalibrated |
| CSS thermal response | steam volume, soak duration | Runs only with explicit validated thermal configuration; embedded model assumptions remain |
| Production/reservoir physics | N/A | Blocked: no independent field production/reservoir physics engine exists |
| CSS–SRP interaction | N/A | Blocked: no coupled engine; SRP does not consume CSS outputs |
| Production forecast | chronological production and predictor features | Unavailable in field mode; existing artifacts are synthetic/unvalidated |
| Calibration/training | governed field dataset and versioned protocol | Viscosity has a controlled calibration/temporal validation workflow; no real field validation or field ML training has occurred |

Physics input availability is not evidence that a model is calibrated. Physics outputs do not report uncertainty; calibration can report a local covariance approximation only under stated mathematical assumptions.

## Field physics execution inputs

The execution service consumes the persisted snapshot and explicit versioned well configuration. It does not substitute generic model constructor defaults.

| Model | Measured snapshot inputs | Required explicit configuration |
|---|---|---|
| Viscosity | `temperature_c`, `bottomhole_pressure_bar` | `walther_a`, `walther_b`, `native_density_kg_m3`; `api_gravity` is optional metadata and is not read by the implemented equation |
| CSS thermal | `steam_injected_tons`, `soak_days` | `native_temp_c`, `steam_temp_c`, `steam_quality`, `latent_heat_kj_kg`, `water_cp_kj_kg_k`, `formation_thickness_m`, `porosity`, `rock_density_kg_m3`, `rock_cp_kj_kg_k`, `conduction_decay_rate` |
| SRP | `stroke_length_m`, `spm`, `viscosity_cp` | `pump_depth_m`, `plunger_diameter_mm`, `rod_weight_air_n`, `tubing_id_mm`, `rod_outer_diameter_mm`, `fluid_density_kg_m3`, `steel_density_kg_m3` |

Configuration units are listed in each parameter suffix or the model field contract. Supported aliases normalize `C`/`degC` to `°C`, `kg/m^3` to `kg/m3`, `1` to `dimensionless`, `%` to `fraction` for steam quality/porosity, and `1/d`/`day^-1` to `1/day`. The stored configuration retains submitted `source_value` and `source_unit`. Other unit strings are rejected. Each value also records source, classification (`MEASURED`, `OPERATOR_CONFIGURED`, `DERIVED`, or `ASSUMED`), validation status, and its configuration version. At execution time, every required parameter must be `VALIDATED`; assumed parameters cannot activate a model. Finite/range and cross-parameter checks include steam temperature above native temperature and pump geometry compatibility.

The service reuses `physics/viscosity_model.py`, `physics/thermal_model.py`, and `physics/srp_model.py`. It records their fixed internal assumptions: viscosity temperature clamp/density and pressure corrections; CSS retention, heat-efficiency, bulk heat-capacity constants; and SRP valve/drag/fillage/power approximations. Results remain simplified, uncalibrated project estimates. Production/reservoir physics is blocked because there is no independent field physics engine. A separate CSS–SRP interaction model is blocked; SRP does not consume CSS outputs. Measurements and snapshots are checked for `VALID` quality, canonical units, supported value ranges, and maximum 24-hour age at execution time.

Operational cycles, events, SRP configuration/observation records, dynamometer cards, and explicit links to scalar measurements use the versioned migration-6 contract in `operational-data-schema.md`. These records are separate from scalar measurement ingestion; cycle timestamps or configured equipment values are not silently converted into measured observations. Regime labels must be explicit.
