"""Field physics orchestration using repository physics engines only.

This service intentionally does not make missing inputs eligible by substituting
the constructor defaults in the underlying model classes.
"""
from datetime import datetime, timedelta, timezone
import math
from typing import Any

from physics.thermal_model import ThermalModel
from physics.viscosity_model import ViscosityModel
from physics.srp_model import SRPModel
from ml_service.services.model_provenance import source_model_version


PARAMETER_UNITS = {
    "walther_a": "dimensionless", "walther_b": "dimensionless", "api_gravity": "API",
    "native_density_kg_m3": "kg/m3", "native_temp_c": "°C", "steam_temp_c": "°C",
    "steam_quality": "fraction", "latent_heat_kj_kg": "kJ/kg", "water_cp_kj_kg_k": "kJ/kg/K",
    "formation_thickness_m": "m", "porosity": "fraction", "rock_density_kg_m3": "kg/m3",
    "rock_cp_kj_kg_k": "kJ/kg/K", "conduction_decay_rate": "1/day", "pump_depth_m": "m",
    "plunger_diameter_mm": "mm", "rod_weight_air_n": "N", "tubing_id_mm": "mm",
    "rod_outer_diameter_mm": "mm", "fluid_density_kg_m3": "kg/m3", "steel_density_kg_m3": "kg/m3",
}
PARAMETER_RANGES = {
    "walther_a": (-10, 20), "walther_b": (0, 10), "api_gravity": (0, 100),
    "native_density_kg_m3": (100, 2000), "native_temp_c": (-50, 500), "steam_temp_c": (0, 600),
    "steam_quality": (0, 1), "latent_heat_kj_kg": (0, 5000), "water_cp_kj_kg_k": (0, 20),
    "formation_thickness_m": (0, 2000), "porosity": (0, 1), "rock_density_kg_m3": (100, 10000),
    "rock_cp_kj_kg_k": (0, 20), "conduction_decay_rate": (0, 10), "pump_depth_m": (0, 20000),
    "plunger_diameter_mm": (0, 1000), "rod_weight_air_n": (0, 1e8), "tubing_id_mm": (0, 2000),
    "rod_outer_diameter_mm": (0, 500), "fluid_density_kg_m3": (0, 3000), "steel_density_kg_m3": (0, 30000),
}
PARAMETER_UNIT_ALIASES = {
    "native_temp_c": {"c": ("°C", 1.0), "degc": ("°C", 1.0)},
    "steam_temp_c": {"c": ("°C", 1.0), "degc": ("°C", 1.0)},
    "native_density_kg_m3": {"kg/m^3": ("kg/m3", 1.0)},
    "rock_density_kg_m3": {"kg/m^3": ("kg/m3", 1.0)},
    "fluid_density_kg_m3": {"kg/m^3": ("kg/m3", 1.0)},
    "steel_density_kg_m3": {"kg/m^3": ("kg/m3", 1.0)},
    "walther_a": {"1": ("dimensionless", 1.0)}, "walther_b": {"1": ("dimensionless", 1.0)},
    "steam_quality": {"%": ("fraction", 0.01)}, "porosity": {"%": ("fraction", 0.01)},
    "conduction_decay_rate": {"1/d": ("1/day", 1.0), "day^-1": ("1/day", 1.0)},
}
MEASUREMENT_UNITS = {
    "temperature_c": "°C", "bottomhole_pressure_bar": "bar", "steam_injected_tons": "metric_ton",
    "soak_days": "day", "stroke_length_m": "m", "spm": "stroke/min", "viscosity_cp": "cP",
}
MEASUREMENT_RANGES = {
    "temperature_c": (10, 350), "bottomhole_pressure_bar": (0, 200),
    "steam_injected_tons": (0, 10_000_000), "soak_days": (0, 365),
    "stroke_length_m": (0, 20), "spm": (0, 60), "viscosity_cp": (0.001, 10_000_000),
}
MODEL_INPUTS = {
    "viscosity": {"measurements": {"temperature_c", "bottomhole_pressure_bar"},
                  "configuration": {"walther_a", "walther_b", "native_density_kg_m3"}},
    "css_thermal": {"measurements": {"steam_injected_tons", "soak_days"},
                    "configuration": {"native_temp_c", "steam_temp_c", "steam_quality", "latent_heat_kj_kg", "water_cp_kj_kg_k", "formation_thickness_m", "porosity", "rock_density_kg_m3", "rock_cp_kj_kg_k", "conduction_decay_rate"}},
    "srp": {"measurements": {"stroke_length_m", "spm", "viscosity_cp"},
            "configuration": {"pump_depth_m", "plunger_diameter_mm", "rod_weight_air_n", "tubing_id_mm", "rod_outer_diameter_mm", "fluid_density_kg_m3", "steel_density_kg_m3"}},
}
MODEL_REFERENCES = {
    "viscosity": {"version": source_model_version(ViscosityModel), "equations": "physics/viscosity_model.py: Walther/ASTM D341 plus density temperature correction and pressure correction"},
    "css_thermal": {"version": source_model_version(ThermalModel), "equations": "physics/thermal_model.py: injected enthalpy and retained heat / heated volume estimate"},
    "srp": {"version": source_model_version(SRPModel), "equations": "physics/srp_model.py: rod kinematics, load, viscous drag, displacement and power estimates"},
}


def validate_configuration(parameters: dict[str, Any]) -> list[str]:
    errors = []
    allowed = {key for spec in MODEL_INPUTS.values() for key in spec["configuration"]} | {"api_gravity"}
    for key, item in parameters.items():
        if key not in allowed:
            errors.append(f"Unsupported parameter: {key}")
            continue
        value = item.value if hasattr(item, "value") else item.get("value") if isinstance(item, dict) else None
        unit = item.unit if hasattr(item, "unit") else item.get("unit") if isinstance(item, dict) else None
        if unit != PARAMETER_UNITS[key]:
            errors.append(f"{key} requires unit {PARAMETER_UNITS[key]}")
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f"{key} must be a finite number")
        else:
            low, high = PARAMETER_RANGES[key]
            if value <= low or value > high:
                errors.append(f"{key} must be > {low} and <= {high} {PARAMETER_UNITS[key]}")
        classification = item.classification if hasattr(item, "classification") else item.get("classification") if isinstance(item, dict) else None
        validation = item.validation_status if hasattr(item, "validation_status") else item.get("validation_status") if isinstance(item, dict) else None
        source = item.source if hasattr(item, "source") else item.get("source") if isinstance(item, dict) else None
        if classification == "ASSUMED" and validation == "VALIDATED":
            errors.append(f"Assumed parameter {key} cannot be marked validated")
        if not source or not str(source).strip():
            errors.append(f"{key} requires provenance source")
    def value(name: str):
        item = parameters.get(name)
        return item.value if hasattr(item, "value") else item.get("value") if isinstance(item, dict) else None
    relationships = [
        ("native_temp_c", "steam_temp_c", lambda native, steam: steam > native, "steam_temp_c must exceed native_temp_c"),
        ("rod_outer_diameter_mm", "tubing_id_mm", lambda rod, tubing: rod < tubing, "rod_outer_diameter_mm must be smaller than tubing_id_mm"),
        ("plunger_diameter_mm", "tubing_id_mm", lambda plunger, tubing: plunger < tubing, "plunger_diameter_mm must be smaller than tubing_id_mm"),
        ("fluid_density_kg_m3", "steel_density_kg_m3", lambda fluid, steel: fluid < steel, "fluid_density_kg_m3 must be less than steel_density_kg_m3"),
    ]
    for first, second, predicate, message in relationships:
        a, b = value(first), value(second)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not predicate(a, b):
            errors.append(message)
    return errors


def normalize_configuration(parameters: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Normalize only documented aliases; retain submitted value/unit provenance."""
    normalized = {}
    for key, raw in parameters.items():
        item = dict(raw)
        submitted_unit = item.get("unit")
        factor = 1.0
        if key in PARAMETER_UNIT_ALIASES:
            alias = str(submitted_unit).strip().lower()
            accepted = PARAMETER_UNIT_ALIASES[key]
            if alias in accepted:
                canonical_unit, factor = accepted[alias]
                item["source_value"] = item.get("value")
                item["source_unit"] = submitted_unit
                item["value"] = item["value"] * factor
                item["unit"] = canonical_unit
        normalized[key] = item
    return normalized


class FieldPhysicsExecutionService:
    max_measurement_age = timedelta(hours=24)

    def eligibility(self, snapshot: dict[str, Any], configuration: dict[str, Any] | None) -> dict[str, Any]:
        measurements = snapshot.get("measurements", {})
        parameters = (configuration or {}).get("parameters", {})
        params = {key: val.get("value") if isinstance(val, dict) else val for key, val in parameters.items()}
        config_errors = validate_configuration(parameters)
        try:
            now = datetime.now(timezone.utc)
            snapshot_time = datetime.fromisoformat(str(snapshot.get("created_at", "")).replace("Z", "+00:00"))
            stale_snapshot = snapshot_time.tzinfo is None or now - snapshot_time > self.max_measurement_age
        except (ValueError, TypeError):
            stale_snapshot = True
        report = {}
        for model, requirements in MODEL_INPUTS.items():
            required = requirements["measurements"]
            missing_measurements = sorted(name for name in required if name not in measurements)
            invalid_measurements, stale_measurements, bad_units = [], [], []
            for name in required - set(missing_measurements):
                item = measurements[name]
                if item.get("quality_status") != "VALID" or not isinstance(item.get("value"), (int, float)) or not math.isfinite(item.get("value", float("nan"))):
                    invalid_measurements.append(name)
                if item.get("unit") != MEASUREMENT_UNITS[name]:
                    bad_units.append(name)
                low, high = MEASUREMENT_RANGES[name]
                if isinstance(item.get("value"), (int, float)) and (item["value"] < low or item["value"] > high):
                    invalid_measurements.append(name)
                try:
                    measured_at = datetime.fromisoformat(str(item.get("measured_at", "")).replace("Z", "+00:00"))
                    if measured_at.tzinfo is None or now - measured_at > self.max_measurement_age:
                        stale_measurements.append(name)
                except (ValueError, TypeError):
                    stale_measurements.append(name)
            if stale_snapshot:
                stale_measurements.extend(name for name in required if name not in stale_measurements)
            missing_configuration = sorted(requirements["configuration"] - params.keys())
            invalid_configuration = sorted(key for key in requirements["configuration"] if key in params and any(err.startswith(f"{key} ") for err in config_errors))
            unvalidated_configuration = sorted(key for key in requirements["configuration"] if key in parameters and isinstance(parameters[key], dict) and parameters[key].get("validation_status") != "VALIDATED")
            assumed_configuration = sorted(key for key in requirements["configuration"] if key in parameters and isinstance(parameters[key], dict) and parameters[key].get("classification") == "ASSUMED")
            reasons = []
            if missing_measurements: reasons.append(f"Missing measurements: {', '.join(missing_measurements)}")
            if invalid_measurements: reasons.append(f"Invalid or non-VALID measurements: {', '.join(sorted(invalid_measurements))}")
            if bad_units: reasons.append(f"Non-canonical measurement units: {', '.join(sorted(bad_units))}")
            if stale_measurements: reasons.append(f"Stale snapshot or measurements (>24h): {', '.join(sorted(set(stale_measurements)))}")
            if missing_configuration: reasons.append(f"Missing configuration: {', '.join(missing_configuration)}")
            if invalid_configuration: reasons.append(f"Invalid configuration values or units: {', '.join(invalid_configuration)}")
            if unvalidated_configuration: reasons.append(f"Configuration not validated: {', '.join(unvalidated_configuration)}")
            if assumed_configuration: reasons.append(f"Assumed parameters cannot activate field execution: {', '.join(assumed_configuration)}")
            ready = not reasons
            report[model] = {
                "status": "ELIGIBLE" if ready else "BLOCKED", "required_inputs": {"measurements": sorted(required), "configuration": sorted(requirements["configuration"])},
                "available_inputs": {"measurements": sorted(required & measurements.keys()), "configuration": sorted(requirements["configuration"] & params.keys())},
                "missing_inputs": {"measurements": missing_measurements, "configuration": missing_configuration},
                "invalid_inputs": sorted(set(invalid_measurements + bad_units + invalid_configuration + assumed_configuration)),
                "stale_inputs": sorted(set(stale_measurements)), "unsupported_inputs": [],
                "configuration_requirements": {"status": "VALIDATED_EXPLICIT_NON_ASSUMED_PARAMETERS_REQUIRED"},
                "reasons": reasons,
                "model_version": MODEL_REFERENCES[model]["version"], "equations_reference": MODEL_REFERENCES[model]["equations"],
            }
        report["production_reservoir"] = {"status": "BLOCKED", "required_inputs": {"measurements": [], "configuration": []}, "available_inputs": {"measurements": [], "configuration": []}, "missing_inputs": {"measurements": [], "configuration": []}, "invalid_inputs": [], "stale_inputs": [], "unsupported_inputs": ["No independent field production/reservoir physics engine is implemented; the existing production forecaster is ML/hybrid and uses synthetic training artifacts."], "configuration_requirements": {}, "reasons": ["No eligible field production/reservoir physics implementation is available."], "model_version": None, "equations_reference": None}
        report["css_srp_interaction"] = {"status": "BLOCKED", "required_inputs": {"measurements": [], "configuration": []}, "available_inputs": {"measurements": [], "configuration": []}, "missing_inputs": {"measurements": [], "configuration": []}, "invalid_inputs": [], "stale_inputs": [], "unsupported_inputs": ["No separate validated coupled CSS-SRP model is implemented."], "configuration_requirements": {}, "reasons": ["The current SRP model accepts viscosity directly and is not coupled to the CSS thermal output."], "model_version": None, "equations_reference": None}
        return report

    def calibration_eligibility(self, well_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        requirements = {
            "viscosity": {"observations": ["temperature_c", "bottomhole_pressure_bar", "viscosity_cp"], "identifiability": ["crude-specific Walther parameters need independent viscosity measurements across temperatures and pressures"]},
            "css_thermal": {"observations": ["steam_injected_tons", "soak_days", "temperature_c"], "identifiability": ["measured reservoir temperature response and approved heat-loss assumptions are required"]},
            "srp": {"observations": ["stroke_length_m", "spm", "viscosity_cp", "oil_rate_bpd", "dynamometer loads"], "identifiability": ["measured load card and production observations with known pump geometry are required"]},
        }
        by_variable: dict[str, list[dict[str, Any]]] = {}
        rejected_quality: dict[str, int] = {}
        for row in records:
            if row.get("quality_status") == "VALID":
                by_variable.setdefault(row["variable"], []).append(row)
            else:
                rejected_quality[row["variable"]] = rejected_quality.get(row["variable"], 0) + 1
        models = {}
        for model, spec in requirements.items():
            missing = sorted(set(spec["observations"]) - by_variable.keys())
            observed = {name: len(by_variable.get(name, [])) for name in spec["observations"]}
            timestamps = [datetime.fromisoformat(row["measured_at"].replace("Z", "+00:00")) for name in spec["observations"] for row in by_variable.get(name, [])]
            coverage_days = (max(timestamps) - min(timestamps)).total_seconds() / 86400 if len(timestamps) > 1 else 0.0
            models[model] = {"status": "NOT_ASSESSED", "observed_counts": observed, "excluded_non_valid_counts": {key: rejected_quality[key] for key in spec["observations"] if key in rejected_quality}, "missing_observations": missing,
                             "temporal_coverage_days": round(coverage_days, 2), "minimum_sample_requirement": "NOT_SET_BY_DOMAIN_OWNER",
                             "data_quality_status": "VALID_ONLY_NON_VALID_RECORDS_EXCLUDED",
                             "required_identifiability": spec["identifiability"],
                             "reasons": ["No approved calibration protocol, sample threshold, or parameter identifiability review is configured."] + ([f"Missing observations: {', '.join(missing)}"] if missing else [])}
        return {"well_id": well_id, "status": "NOT_ASSESSED", "models": models,
                "activation": "NO_FITTED_PARAMETERS_CAN_BE_ACTIVATED_BY_THIS_ASSESSMENT", "protocol": "NOT_CONFIGURED"}

    def execute(self, snapshot: dict[str, Any], configuration: dict[str, Any] | None) -> dict[str, Any]:
        eligibility = self.eligibility(snapshot, configuration)
        params = {k: v.get("value") if isinstance(v, dict) else v for k, v in (configuration or {}).get("parameters", {}).items()}
        measurements = snapshot.get("measurements", {})
        results, failures = {}, {}
        for name, check in eligibility.items():
            if name not in MODEL_INPUTS or check["status"] != "ELIGIBLE":
                continue
            consumed_measurements = []
            try:
                if name == "viscosity":
                    # api_gravity is currently unused by the implemented
                    # Walther equation; pass None explicitly instead of a
                    # synthetic constructor default when it is not configured.
                    model = ViscosityModel(params["walther_a"], params["walther_b"], params.get("api_gravity"), params["native_density_kg_m3"])
                    consumed_measurements = [measurements[k] for k in ("temperature_c", "bottomhole_pressure_bar")]
                    outputs = {"viscosity_cp": {"value": model.calculate_viscosity(measurements["temperature_c"]["value"], measurements["bottomhole_pressure_bar"]["value"]), "unit": "cP"}}
                    config_keys = ["walther_a", "walther_b", "native_density_kg_m3"] + (["api_gravity"] if "api_gravity" in params else [])
                elif name == "css_thermal":
                    model = ThermalModel(**{key: params[key] for key in MODEL_INPUTS[name]["configuration"]})
                    consumed_measurements = [measurements[k] for k in ("steam_injected_tons", "soak_days")]
                    values = model.calculate_peak_temperature(measurements["steam_injected_tons"]["value"], measurements["soak_days"]["value"])
                    units = {"peak_temperature_c": "°C", "heated_radius_m": "m", "total_heat_injected_gj": "GJ", "heat_retained_post_soak_gj": "GJ"}
                    outputs = {key: {"value": value, "unit": units[key]} for key, value in values.items()}
                    config_keys = sorted(MODEL_INPUTS[name]["configuration"])
                else:
                    model = SRPModel(**{key: params[key] for key in MODEL_INPUTS[name]["configuration"]})
                    consumed_measurements = [measurements[k] for k in ("stroke_length_m", "spm", "viscosity_cp")]
                    values = model.evaluate_srp_performance(measurements["stroke_length_m"]["value"], measurements["spm"]["value"], measurements["viscosity_cp"]["value"])
                    units = {"stroke_length_m": "m", "spm": "stroke/min", "v_max_m_s": "m/s", "pprl_lbs": "lbf", "mprl_lbs": "lbf", "net_downstroke_force_lbs": "lbf", "viscous_drag_lbf": "lbf", "rod_floating_detected": "boolean", "rod_floating_risk": "dimensionless model score", "impact_loading_risk": "dimensionless model score", "theoretical_displacement_bpd": "bbl/day", "estimated_production_bpd": "bbl/day", "pump_efficiency_pct": "%", "electrical_power_kw": "kW", "kwh_per_barrel": "kWh/bbl", "gearbox_peak_torque_in_lbs": "in·lbf"}
                    outputs = {key: {"value": value, "unit": units[key]} for key, value in values.items()}
                    config_keys = sorted(MODEL_INPUTS[name]["configuration"])
                if not self._finite_output(outputs):
                    raise ValueError("Physics engine produced a non-finite output")
                results[name] = {"status": "EXECUTED", "model_version": MODEL_REFERENCES[name]["version"], "equations_reference": MODEL_REFERENCES[name]["equations"],
                                 "outputs": outputs, "inputs_consumed": {"measurements": consumed_measurements,
                                 "configuration": {key: configuration["parameters"][key] for key in config_keys},
                                 "configuration_id": configuration["configuration_id"], "configuration_version": configuration["config_version"]},
                                 "assumptions": self._assumptions(name), "limitations": ["Uncalibrated project physics estimate; not a field-validated result or operating instruction."],
                                 "validation_status": "NOT_VALIDATED_ON_HELD_OUT_FIELD_DATA"}
                eligibility[name]["status"] = "EXECUTED"
            except Exception as exc:
                failures[name] = f"{type(exc).__name__}: {str(exc)[:300]}"
                eligibility[name]["status"] = "FAILED"
                eligibility[name]["reasons"].append(failures[name])
        statuses = [eligibility[name]["status"] for name in MODEL_INPUTS]
        return {"snapshot_version": snapshot.get("state_version"), "configuration_id": (configuration or {}).get("configuration_id"),
                "configuration_version": (configuration or {}).get("config_version"),
                "execution_status": "COMPLETED" if results and not failures and all(s == "EXECUTED" for s in statuses) else "PARTIAL" if results else "UNAVAILABLE",
                "eligibility": eligibility, "model_results": results, "errors": failures,
                "calibration_status": "NOT_CALIBRATED", "validation_status": "NOT_VALIDATED_ON_HELD_OUT_FIELD_DATA"}

    @staticmethod
    def _assumptions(model: str) -> list[str]:
        assumptions = {
            "viscosity": ["Existing implementation clamps temperature to 10–350 °C, uses fixed density expansion and pressure coefficients, and uses Walther parameters supplied in this configuration. Constructor api_gravity is not used by the implemented calculation; Beggs-Robinson fallback is not implemented."],
            "css_thermal": ["Existing implementation uses fixed thermal efficiency, soak retention coefficient, target temperature rise, capped heated radius, and embedded oil density/heat capacity."],
            "srp": ["Existing implementation uses fixed rod-fluid drag approximations, valve geometry, pump fillage, motor efficiency, and empirical risk equations."],
        }
        return assumptions[model]

    @staticmethod
    def _finite_output(value: Any) -> bool:
        if isinstance(value, dict):
            return all(FieldPhysicsExecutionService._finite_output(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return all(FieldPhysicsExecutionService._finite_output(item) for item in value)
        if isinstance(value, float):
            return math.isfinite(value)
        return True
