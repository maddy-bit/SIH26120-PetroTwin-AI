"""Reproducible field-data calibration and chronological validation services.

Only the repository viscosity model currently has an implemented fit adapter.
CSS event linkage and SRP parameter identifiability are explicitly blocked.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any

import numpy as np
import scipy
from scipy.optimize import least_squares

from ml_service.services.data_ingestion import BOUNDS
from ml_service.services.physics_execution import MEASUREMENT_RANGES, MEASUREMENT_UNITS, PARAMETER_UNITS, validate_configuration
from ml_service.services.model_provenance import source_model_version
from physics.viscosity_model import ViscosityModel
from physics.thermal_model import ThermalModel
from physics.srp_model import SRPModel


TARGETS = {
    "viscosity": {"target": "viscosity_cp", "inputs": ["temperature_c", "bottomhole_pressure_bar"], "target_unit": "cP", "input_tolerance_minutes": 15},
    "srp": {"target": "oil_rate_bpd", "inputs": ["stroke_length_m", "spm", "viscosity_cp"], "target_unit": "bbl/day", "input_tolerance_minutes": 15},
    "css_thermal": {"target": "temperature_c", "inputs": ["steam_injected_tons", "soak_days"], "target_unit": "°C", "input_tolerance_minutes": 15},
}
CALIBRATABLE_PARAMETERS = {"viscosity": ["walther_a", "walther_b", "native_density_kg_m3"], "srp": [], "css_thermal": []}
MODEL_VERSIONS = {"viscosity": source_model_version(ViscosityModel), "css_thermal": source_model_version(ThermalModel), "srp": source_model_version(SRPModel)}
PARAMETER_LIMITS = {"walther_a": (-10.0, 20.0), "walther_b": (0.0, 10.0), "native_density_kg_m3": (100.0, 2000.0)}


def _dt(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _metrics(observed: list[float], predicted: list[float]) -> dict[str, Any]:
    y = np.asarray(observed, dtype=float); p = np.asarray(predicted, dtype=float)
    if len(y) == 0 or len(y) != len(p) or not np.isfinite(y).all() or not np.isfinite(p).all():
        return {"count": int(len(y)), "mae": None, "rmse": None, "bias": None, "mean_absolute_relative_error": None, "r2": None}
    residual = p - y
    r2 = None
    if len(y) >= 2 and float(np.sum((y - np.mean(y)) ** 2)) > 0:
        r2 = float(1.0 - np.sum(residual ** 2) / np.sum((y - np.mean(y)) ** 2))
    return {"count": int(len(y)), "mae": float(np.mean(np.abs(residual))),
            "rmse": float(np.sqrt(np.mean(residual ** 2))), "bias": float(np.mean(residual)),
            "mean_absolute_relative_error": float(np.mean(np.abs(residual) / np.abs(y))) if np.all(y != 0) else None,
            "r2": r2,
            "residuals": [float(x) for x in residual],
            "residual_summary": {"mean": float(np.mean(residual)), "std_population": float(np.std(residual)),
                                 "min": float(np.min(residual)), "max": float(np.max(residual))}}


class ScientificCalibrationService:
    def __init__(self, repository):
        self.repository = repository

    def build_dataset(self, well_id: str, model_id: str, start: datetime, end: datetime,
                      tolerance_minutes: int = 15, dataset_role: str = "CALIBRATION") -> dict[str, Any]:
        if model_id not in TARGETS:
            raise ValueError(f"Unsupported calibration model: {model_id}")
        start, end = _dt(start), _dt(end)
        if end <= start:
            raise ValueError("end_at must be after start_at")
        if not 0 <= tolerance_minutes <= 1440:
            raise ValueError("tolerance_minutes must be between 0 and 1440")
        records = self.repository.query_measurements(well_id, start_at=start.isoformat(), end_at=end.isoformat(), limit=10000)
        usable: dict[str, list[dict[str, Any]]] = {}
        excluded: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        relevant = {TARGETS[model_id]["target"], *TARGETS[model_id]["inputs"]}
        for row in sorted(records, key=lambda r: (r["variable"], r["measured_at"], 0 if r.get("quality_status") == "VALID" else 1, r["measurement_id"])):
            if row["variable"] not in relevant:
                continue
            key = (row["variable"], row["measured_at"])
            if key in seen:
                excluded.append({"measurement_id": row["measurement_id"], "reason": "duplicate_variable_timestamp"})
                continue
            seen.add(key)
            if row.get("quality_status") != "VALID":
                excluded.append({"measurement_id": row["measurement_id"], "reason": "quality_not_valid"}); continue
            expected = MEASUREMENT_UNITS.get(row["variable"], TARGETS[model_id]["target_unit"])
            if row.get("unit") != expected:
                excluded.append({"measurement_id": row["measurement_id"], "reason": f"unsupported_unit:{row.get('unit')}"}); continue
            value = row.get("value")
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                excluded.append({"measurement_id": row["measurement_id"], "reason": "non_finite_value"}); continue
            bounds = MEASUREMENT_RANGES.get(row["variable"]) or BOUNDS.get(row["variable"])
            if bounds and not bounds[0] <= value <= bounds[1]:
                excluded.append({"measurement_id": row["measurement_id"], "reason": "outside_supported_model_range"}); continue
            if row["variable"] in {"viscosity_cp", "oil_rate_bpd"} and value <= 0:
                excluded.append({"measurement_id": row["measurement_id"], "reason": "target_must_be_positive"}); continue
            usable.setdefault(row["variable"], []).append(row)

        observations = []
        target_type = TARGETS[model_id]["target"]
        target_rows = usable.get(target_type, [])
        if model_id == "css_thermal":
            rows_by_id = {row["measurement_id"]: row for row in target_rows}
            css_cycles = self.repository.list_css_cycles(well_id) if hasattr(self.repository, "list_css_cycles") else []
            cycles = [cycle for cycle in css_cycles
                      if cycle.get("status") == "COMPLETE" and not cycle.get("archived_at")
                      and cycle.get("injection_start") and start <= _dt(cycle["injection_start"]) <= end]
            links = self.repository.list_measurement_links(well_id=well_id) if hasattr(self.repository, "list_measurement_links") else []
            linked_temperature_ids = set()
            for cycle in cycles:
                cycle_id = cycle["cycle_id"]
                mass = cycle.get("quantities", {}).get("injection_mass_tons")
                soak_start, soak_end = cycle.get("soak_start"), cycle.get("soak_end")
                if not mass or mass.get("quality_status","VALID")!="VALID" or not soak_start or not soak_end or cycle.get("quality_status") != "VALID":
                    excluded.append({"record_id": cycle_id, "reason": "cycle_missing_valid_mass_soak_or_quality"}); continue
                soak_days = (_dt(soak_end) - _dt(soak_start)).total_seconds() / 86400
                if soak_days <= 0:
                    excluded.append({"record_id": cycle_id, "reason": "nonpositive_soak_duration"}); continue
                if not cycle.get("post_soak_observation_start") or not cycle.get("post_soak_observation_end"):
                    excluded.append({"record_id": cycle_id, "reason": "post_soak_observation_window_not_recorded"}); continue
                cycle_links = [item for item in links if item["entity_type"] == "css_cycle" and item["entity_id"] == cycle_id and item["relation"] in {"POST_SOAK_TEMPERATURE", "TEMPERATURE_TARGET"}]
                for link in cycle_links:
                    target = rows_by_id.get(link["measurement_id"])
                    if target is None: continue
                    target_time = _dt(target["measured_at"])
                    if not (_dt(cycle["production_restart"]) <= target_time and _dt(cycle["post_soak_observation_start"]) <= target_time <= _dt(cycle["post_soak_observation_end"])):
                        excluded.append({"measurement_id": target["measurement_id"], "reason": "linked_temperature_outside_post_soak_observation_window"}); continue
                    sensor_context=target.get("provenance",{}).get("source_metadata",{})
                    has_sensor_reference=bool(sensor_context.get("sensor_reference")) or isinstance(sensor_context.get("sensor_depth_m"),(int,float))
                    if sensor_context.get("measurement_context")!="RESERVOIR_TEMPERATURE" or not has_sensor_reference:
                        excluded.append({"measurement_id":target["measurement_id"],"reason":"temperature_target_missing_explicit_reservoir_context_or_sensor_reference"}); continue
                    linked_temperature_ids.add(target["measurement_id"])
                    observations.append({"observed_at": target_time.isoformat(), "cycle_id": cycle_id,
                        "target": {"variable": target_type, "value": target["value"], "unit": target["unit"], "measurement_id": target["measurement_id"], "source_id": target["source_id"], "provenance": target["provenance"]},
                        "inputs": {"steam_injected_tons": {"value": mass["value"], "unit": mass["unit"], "cycle_id": cycle_id, "provenance": mass.get("provenance", cycle.get("provenance", {}))},
                                   "soak_days": {"value": soak_days, "unit": "day", "cycle_id": cycle_id, "provenance": cycle.get("provenance", {})}},
                        "cycle_conditions": {name: item for name, item in cycle.get("quantities", {}).items() if item is not None},
                        "cycle_provenance": cycle.get("provenance", {}),"sensor_context":sensor_context})
            for target in target_rows:
                if target["measurement_id"] not in linked_temperature_ids:
                    excluded.append({"measurement_id": target["measurement_id"], "reason": "temperature_not_linked_to_css_cycle_and_post_soak_window"})
            target_rows = []
        tolerance = tolerance_minutes * 60
        used_inputs: set[str] = set()
        for target in target_rows:
            target_time = _dt(target["measured_at"])
            selected = {}; failed = False
            for input_type in TARGETS[model_id]["inputs"]:
                candidates = [row for row in usable.get(input_type, []) if row["measurement_id"] not in used_inputs]
                candidates = [row for row in candidates if abs((_dt(row["measured_at"]) - target_time).total_seconds()) <= tolerance]
                if not candidates:
                    excluded.append({"measurement_id": target["measurement_id"], "reason": f"missing_contemporaneous_input:{input_type}"})
                    failed = True; break
                selected[input_type] = min(candidates, key=lambda row: (abs((_dt(row["measured_at"]) - target_time).total_seconds()), row["measurement_id"]))
            if failed:
                continue
            used_inputs.update(row["measurement_id"] for row in selected.values())
            observations.append({"observed_at": target_time.isoformat(), "target": {"variable": target_type, "value": target["value"], "unit": target["unit"], "measurement_id": target["measurement_id"], "source_id": target["source_id"], "provenance": target["provenance"]},
                                 "inputs": {name: {"value": row["value"], "unit": row["unit"], "measurement_id": row["measurement_id"], "measured_at": row["measured_at"], "source_id": row["source_id"], "provenance": row["provenance"]} for name, row in selected.items()}})
        observations.sort(key=lambda item: (item["observed_at"], item["target"]["measurement_id"]))
        missing_measurement_types = sorted(name for name in relevant if not usable.get(name))
        if model_id == "css_thermal":
            missing_measurement_types = sorted(name for name in ["temperature_c"] if not usable.get(name))
        dates = [_dt(row["observed_at"]) for row in observations]
        coverage_days = (dates[-1] - dates[0]).total_seconds() / 86400 if len(dates) >= 2 else 0.0
        current_configuration = self.repository.get_physical_configuration(well_id)
        varying_inputs = {}
        for name in TARGETS[model_id]["inputs"]:
            vals = [row["inputs"][name]["value"] for row in observations]
            varying_inputs[name] = {"min": min(vals) if vals else None, "max": max(vals) if vals else None,
                                    "range": max(vals) - min(vals) if vals else None, "unique_values": len(set(vals))}
        payload = {"well_id": well_id, "model_id": model_id, "model_version": MODEL_VERSIONS[model_id],
                   "physical_configuration_reference": ({"configuration_id": current_configuration["configuration_id"], "configuration_version": current_configuration["config_version"]} if current_configuration else None),
                   "dataset_role": dataset_role, "period": {"start_at": start.isoformat(), "end_at": end.isoformat()},
                   "pairing": {"method": "nearest_timestamp_without_input_reuse", "max_delta_minutes": tolerance_minutes,
                               "freshness": "historical calibration accepts old observations if quality is VALID; timestamp pairing bound applies"},
                   "target": target_type, "target_unit": TARGETS[model_id]["target_unit"], "input_types": TARGETS[model_id]["inputs"],
                   "observations": observations, "observation_count": len(observations), "temporal_coverage_days": coverage_days,
                   "missing_measurement_types": missing_measurement_types,
                   "dataset_quality_status": "NO_COMPATIBLE_OBSERVATIONS" if not observations else "PAIRED_OBSERVATIONS_AVAILABLE_REVIEW_REQUIRED",
                   "input_variation": varying_inputs, "excluded_records": excluded,
                   "regime_assessment": ({"status": "EXPLICIT_LABELS_ONLY", "labels": sorted({label for row in observations for label in next((cycle.get("metadata",{}).get("operating_regime_labels",[]) for cycle in self.repository.list_css_cycles(well_id) if cycle.get("cycle_id")==row.get("cycle_id")),[])})} if model_id == "css_thermal" else {"status": "UNAVAILABLE", "reason": "No operating-regime labels are present on the measured observations."}),
                   "calibration_capability": "SUPPORTED" if model_id == "viscosity" else "BLOCKED_NOT_IDENTIFIABLE_OR_TARGET_NOT_LINKED"}
        fingerprint_input = json.dumps({key: payload[key] for key in ("well_id", "model_id", "model_version", "dataset_role", "period", "pairing", "observations", "excluded_records", "missing_measurement_types", "input_variation", "dataset_quality_status")}, sort_keys=True, separators=(",", ":"))
        payload["fingerprint"] = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()
        return self.repository.save_calibration_dataset(payload)

    @staticmethod
    def _predict_viscosity(observation: dict[str, Any], values: dict[str, float], fixed: dict[str, float]) -> float:
        model = ViscosityModel(values.get("walther_a", fixed["walther_a"]), values.get("walther_b", fixed["walther_b"]), fixed.get("api_gravity"), values.get("native_density_kg_m3", fixed["native_density_kg_m3"]))
        return model.calculate_viscosity(observation["inputs"]["temperature_c"]["value"], observation["inputs"]["bottomhole_pressure_bar"]["value"])

    def assess_identifiability(self, dataset: dict[str, Any], configuration: dict[str, Any], parameter_names: list[str] | None = None) -> dict[str, Any]:
        model_id = dataset["model_id"]
        if model_id != "viscosity":
            parameter_names = {
                "css_thermal": ["native_temp_c", "steam_temp_c", "steam_quality", "latent_heat_kj_kg", "water_cp_kj_kg_k", "formation_thickness_m", "porosity", "rock_density_kg_m3", "rock_cp_kj_kg_k", "conduction_decay_rate"],
                "srp": ["pump_depth_m", "plunger_diameter_mm", "rod_weight_air_n", "tubing_id_mm", "rod_outer_diameter_mm", "fluid_density_kg_m3", "steel_density_kg_m3"],
            }.get(model_id, [])
            params = {name: {"classification": "NOT_IDENTIFIABLE", "evidence": "The available target is not sufficiently linked to model inputs or is confounded with multiple unobserved parameters."} for name in parameter_names}
            reason = ("Cycle linkage and post-soak windows are now required for CSS observations, but no CSS parameter sensitivity/calibration adapter has been scientifically implemented; parameter identifiability is not established." if model_id == "css_thermal" else "SRP oil-rate alone cannot identify coupled pump, fluid, and fillage effects; dynamometer and operating data improve readiness but do not supply a validated fitting adapter.")
            return {"dataset_id": dataset["dataset_id"], "model_id": model_id, "status": "NOT_IDENTIFIABLE", "parameters": params,
                    "method": "model-specific structural assessment", "reason": reason}
        observations = dataset["observations"]
        base_params = configuration.get("parameters", {})
        required_config = {"walther_a", "walther_b", "native_density_kg_m3"}
        missing_config = sorted(required_config - base_params.keys())
        if missing_config:
            return {"dataset_id": dataset["dataset_id"], "model_id": model_id, "status": "INSUFFICIENT_DATA", "parameters": {}, "reason": f"Missing viscosity configuration parameters: {', '.join(missing_config)}"}
        config_errors = validate_configuration(base_params)
        not_validated = sorted(name for name in required_config if base_params[name].get("validation_status") != "VALIDATED" or base_params[name].get("classification") == "ASSUMED")
        if config_errors or not_validated:
            return {"dataset_id": dataset["dataset_id"], "model_id": model_id, "status": "INSUFFICIENT_DATA", "parameters": {},
                    "reason": "Source parameters must be valid, explicitly validated, and non-assumed.", "configuration_errors": config_errors,
                    "unvalidated_parameters": not_validated}
        fixed = {name: base_params[name]["value"] for name in ("walther_a", "walther_b", "native_density_kg_m3") if name in base_params}
        if "api_gravity" in base_params:
            fixed["api_gravity"] = base_params["api_gravity"]["value"]
        requested = parameter_names if parameter_names is not None else CALIBRATABLE_PARAMETERS["viscosity"]
        if any(name not in CALIBRATABLE_PARAMETERS["viscosity"] for name in requested):
            return {"dataset_id": dataset["dataset_id"], "model_id": model_id, "status": "NOT_IDENTIFIABLE", "parameters": {}, "reason": "One or more selected parameters have no calibration adapter."}
        names = [name for name in requested if name in fixed]
        n, p = len(observations), len(names)
        if p == 0:
            return {"dataset_id": dataset["dataset_id"], "model_id": model_id, "status": "INSUFFICIENT_DATA", "parameters": {}, "reason": "No complete viscosity parameter configuration was supplied."}
        matrix = np.zeros((n, p), dtype=float)
        for j, name in enumerate(names):
            scale = max(1.0, abs(fixed[name])); step = 1e-5 * scale
            plus = dict(fixed); minus = dict(fixed); plus[name] += step; minus[name] -= step
            for i, obs in enumerate(observations):
                yp = max(1e-12, self._predict_viscosity(obs, plus, fixed)); ym = max(1e-12, self._predict_viscosity(obs, minus, fixed))
                matrix[i, j] = (math.log(yp) - math.log(ym)) / (2 * step)
        if n and p:
            singular = np.linalg.svd(matrix, compute_uv=False)
            rank = int(np.linalg.matrix_rank(matrix))
            condition = float(singular[0] / singular[-1]) if len(singular) >= p and singular[-1] > 0 else math.inf
        else:
            singular = np.array([]); rank = 0; condition = math.inf
        temps = [obs["inputs"]["temperature_c"]["value"] for obs in observations]
        temperature_range = max(temps) - min(temps) if temps else 0.0
        correlation = None
        if n >= 2 and p >= 2 and all(np.std(matrix[:, j]) > 0 for j in range(p)):
            correlation_matrix = np.corrcoef(matrix.T)
            correlation = float(np.max(np.abs(correlation_matrix[np.triu_indices(p, k=1)])))
        per_parameter = {}
        for j, name in enumerate(names):
            col_norm = float(np.linalg.norm(matrix[:, j])) if n else 0.0
            if n <= p or temperature_range <= 1e-6:
                label = "INSUFFICIENT_DATA"
                evidence = f"{n} paired observations for {p} free parameters; temperature span {temperature_range:.6g} °C."
            elif col_norm <= 1e-10:
                label = "NOT_IDENTIFIABLE"; evidence = "Finite-difference predictions are locally insensitive to this parameter."
            elif rank < p or condition > 1e8 or (correlation is not None and correlation >= 0.995):
                label = "WEAKLY_IDENTIFIABLE"; evidence = f"Sensitivity matrix rank {rank}/{p}, condition number {condition:.6g}, column correlation {correlation}."
            else:
                label = "POTENTIALLY_IDENTIFIABLE"; evidence = f"Finite-difference sensitivity is nonzero; matrix rank {rank}/{p}, condition number {condition:.6g}; requires held-out temporal validation."
            per_parameter[name] = {"classification": label, "finite_difference_sensitivity_norm": col_norm, "evidence": evidence}
        return {"dataset_id": dataset["dataset_id"], "fingerprint": dataset["fingerprint"], "model_id": model_id,
                "method": "central finite-difference Jacobian of log viscosity with respect to Walther A/B and native density; SVD rank and condition plus maximum sensitivity-column correlation",
                "observation_count": n, "free_parameter_count": p, "sensitivity_matrix_rank": rank,
                "sensitivity_condition_number": condition if math.isfinite(condition) else None,
                "numerical_condition_warning_threshold": 1e8, "sensitivity_column_correlation": correlation,
                "temperature_span_c": temperature_range, "parameters": per_parameter,
                "excluded_parameters": {**({name: {"classification": "FIXED_FOR_THIS_ASSESSMENT", "reason": "This parameter was not selected for this local sensitivity calculation."} for name in CALIBRATABLE_PARAMETERS["viscosity"] if name not in names}),
                                         "api_gravity": {"classification": "NOT_IDENTIFIABLE", "reason": "The current ViscosityModel.calculate_viscosity equation does not read api_gravity; it cannot be calibrated from this output."}},
                "status": "POTENTIALLY_IDENTIFIABLE" if per_parameter and all(v["classification"] == "POTENTIALLY_IDENTIFIABLE" for v in per_parameter.values()) else "INSUFFICIENT_DATA_OR_WEAK_IDENTIFIABILITY",
                "limitations": ["Local sensitivity is not proof of global uniqueness or scientific validity.", "Condition threshold is a numerical diagnostic, not a petroleum acceptance criterion."]}

    def calibrate(self, dataset: dict[str, Any], configuration: dict[str, Any], selected_parameters: list[str], bounds: dict[str, dict[str, float]]) -> dict[str, Any]:
        if dataset["model_id"] != "viscosity" or dataset["calibration_capability"] != "SUPPORTED":
            raise ValueError("Calibration is blocked: no identifiable fitting adapter exists for this model.")
        if configuration.get("config_version") is None:
            raise ValueError("A persisted source configuration version is required.")
        if not selected_parameters or len(set(selected_parameters)) != len(selected_parameters):
            raise ValueError("Select at least one unique calibratable parameter.")
        if any(name not in CALIBRATABLE_PARAMETERS["viscosity"] for name in selected_parameters):
            raise ValueError("Only Walther A, Walther B, and native density have calibration adapters.")
        ident = self.assess_identifiability(dataset, configuration, selected_parameters)
        for name in selected_parameters:
            item = ident["parameters"].get(name)
            if item is None or item["classification"] not in {"POTENTIALLY_IDENTIFIABLE", "IDENTIFIABLE"}:
                raise ValueError(f"Parameter {name} is not eligible: {item['classification'] if item else 'not assessed'}")
            if name not in bounds or set(bounds[name]) != {"lower", "upper", "unit"}:
                raise ValueError(f"Explicit lower, upper, and canonical unit are required for {name}.")
            if bounds[name]["unit"] != PARAMETER_UNITS[name]:
                raise ValueError(f"Bounds for {name} require unit {PARAMETER_UNITS[name]}.")
            lower, upper = float(bounds[name]["lower"]), float(bounds[name]["upper"])
            absolute_low, absolute_high = PARAMETER_LIMITS[name]
            original = configuration["parameters"][name]["value"]
            if not all(math.isfinite(x) for x in (lower, upper)) or not absolute_low < lower < upper <= absolute_high or not lower <= original <= upper:
                raise ValueError(f"Bounds for {name} must be finite, inside model limits, ordered, and contain the original value.")
        if len(dataset["observations"]) <= len(selected_parameters):
            raise ValueError("Insufficient observations: residual degrees of freedom must be positive.")
        params = configuration["parameters"]
        config_errors = validate_configuration(params)
        required_config = {"walther_a", "walther_b", "native_density_kg_m3"}
        if required_config - params.keys() or config_errors:
            raise ValueError("Source configuration is incomplete or invalid: " + "; ".join(config_errors))
        if any(params[name].get("validation_status") != "VALIDATED" or params[name].get("classification") == "ASSUMED" for name in required_config):
            raise ValueError("Source viscosity configuration must be explicitly validated and non-assumed.")
        fixed = {name: params[name]["value"] for name in ("walther_a", "walther_b", "native_density_kg_m3")}
        if "api_gravity" in params:
            fixed["api_gravity"] = params["api_gravity"]["value"]
        initial = np.asarray([fixed[name] for name in selected_parameters], dtype=float)
        lower = np.asarray([bounds[name]["lower"] for name in selected_parameters], dtype=float)
        upper = np.asarray([bounds[name]["upper"] for name in selected_parameters], dtype=float)
        observations = dataset["observations"]
        observed = np.asarray([row["target"]["value"] for row in observations], dtype=float)
        def residual(vector):
            trial = dict(fixed); trial.update(dict(zip(selected_parameters, vector)))
            predicted = np.asarray([self._predict_viscosity(row, trial, fixed) for row in observations], dtype=float)
            if not np.isfinite(predicted).all() or np.any(predicted <= 0):
                raise ValueError("Model produced invalid viscosity during calibration")
            return np.log(predicted) - np.log(observed)
        def rounded_model_jacobian(vector):
            # The existing physics API rounds viscosity to 0.01 cP. SciPy's
            # default tiny finite difference can therefore see a zero slope.
            # Use explicit, documented central perturbations above the output
            # quantization floor while still calling the same physics model.
            jacobian = np.empty((len(observations), len(vector)), dtype=float)
            for j, value in enumerate(vector):
                step = max(5e-3 * max(1.0, abs(float(value))), 1e-3)
                lo, hi = max(lower[j], value - step), min(upper[j], value + step)
                if hi <= lo:
                    jacobian[:, j] = 0.0
                    continue
                plus, minus = vector.copy(), vector.copy()
                plus[j], minus[j] = hi, lo
                jacobian[:, j] = (residual(plus) - residual(minus)) / (hi - lo)
            return jacobian
        result = least_squares(residual, initial, jac=rounded_model_jacobian, bounds=(lower, upper), method="trf", loss="linear", x_scale="jac", max_nfev=1000)
        final_values = dict(zip(selected_parameters, [float(x) for x in result.x]))
        final = dict(fixed); final.update(final_values)
        calibrated_prediction = [self._predict_viscosity(row, final, fixed) for row in observations]
        original_prediction = [self._predict_viscosity(row, fixed, fixed) for row in observations]
        median_baseline = float(np.median(observed))
        dof = len(observed) - len(result.x)
        uncertainty = {"status": "NOT_ESTIMATED", "reason": "Local covariance requires a full-rank Jacobian and positive residual degrees of freedom."}
        if dof > 0 and np.linalg.matrix_rank(result.jac) == len(result.x):
            try:
                covariance = np.linalg.inv(result.jac.T @ result.jac) * (float(np.sum(result.fun ** 2)) / dof)
                uncertainty = {"status": "LOCAL_GAUSSIAN_APPROXIMATION", "standard_errors": {name: float(math.sqrt(max(0.0, covariance[i, i]))) for i, name in enumerate(selected_parameters)},
                               "assumption": "Locally linear residuals with independent homoscedastic errors; not a field confidence interval."}
            except np.linalg.LinAlgError:
                pass
        candidate_parameters = {key: dict(value) for key, value in params.items()}
        for name, value in final_values.items():
            candidate_parameters[name] = {**candidate_parameters[name], "value": value, "classification": "DERIVED", "source": "scientific calibration candidate", "validation_status": "UNVALIDATED"}
        return {"status": "CALIBRATION_COMPLETED" if result.success else "CALIBRATION_FAILED", "model_id": "viscosity", "model_version": MODEL_VERSIONS["viscosity"],
                "dataset_id": dataset["dataset_id"], "dataset_fingerprint": dataset["fingerprint"], "well_id": dataset["well_id"],
                "original_configuration_id": configuration["configuration_id"], "original_configuration_version": configuration["config_version"],
                "candidate_parameters": final_values, "candidate_parameter_units": {name: PARAMETER_UNITS[name] for name in final_values},
                "candidate_configuration_parameters": candidate_parameters,
                "selected_parameters": selected_parameters, "bounds": bounds, "objective": "mean squared log-relative error (optimized as log residual least squares)",
                "optimizer": {"method": "scipy.optimize.least_squares", "algorithm": "trust-region reflective", "scipy_version": scipy.__version__, "numpy_version": np.__version__, "loss": "linear", "jacobian": "central finite difference; 0.5% relative parameter perturbation to exceed 0.01 cP rounding", "max_nfev": 1000},
                "initial_values": {name: float(fixed[name]) for name in selected_parameters}, "final_objective": float(np.mean(result.fun ** 2)),
                "original_configuration_parameters": {key: dict(value) for key, value in params.items()},
                "convergence": {"success": bool(result.success), "status_code": int(result.status), "message": str(result.message), "iterations": int(result.nfev), "optimality": float(result.optimality), "active_bounds": [selected_parameters[i] for i, code in enumerate(result.active_mask) if code != 0]},
                "calibration_metrics": _metrics(observed.tolist(), calibrated_prediction), "uncalibrated_metrics": _metrics(observed.tolist(), original_prediction),
                "baseline_metrics": _metrics(observed.tolist(), [median_baseline] * len(observed)),
                "residuals": {"convention": "prediction_minus_observation", "calibrated": [float(p-y) for y, p in zip(observed, calibrated_prediction)], "uncalibrated": [float(p-y) for y, p in zip(observed, original_prediction)]},
                "identifiability": ident, "uncertainty": uncertainty, "lifecycle_status": "VALIDATION_PENDING" if result.success else "CALIBRATION_FAILED",
                "limitations": ["In-sample calibration metrics are not validation evidence.", "Candidate is stored separately and never replaces active well configuration.", "Only measured viscosity observations were used; no synthetic examples were included."]}

    def validate_candidate(self, candidate: dict[str, Any], calibration: dict[str, Any], validation_dataset: dict[str, Any], gap_hours: float) -> dict[str, Any]:
        if candidate["model_id"] != "viscosity" or validation_dataset["model_id"] != candidate["model_id"]:
            raise ValueError("Candidate and validation dataset must use the same supported model.")
        cal_dataset = self.repository.get_calibration_dataset(calibration["dataset_id"])
        if cal_dataset is None:
            raise ValueError("Calibration dataset not found.")
        cal_end = _dt(cal_dataset["period"]["end_at"]); val_start = _dt(validation_dataset["period"]["start_at"])
        if val_start < cal_end or (val_start - cal_end).total_seconds() < gap_hours * 3600:
            raise ValueError("Validation period must start after the calibration period and configured temporal gap.")
        cal_ids = {row["target"]["measurement_id"] for row in cal_dataset["observations"]}
        val_ids = {row["target"]["measurement_id"] for row in validation_dataset["observations"]}
        if cal_ids & val_ids:
            raise ValueError("Temporal leakage detected: calibration and validation target measurement IDs overlap.")
        config = candidate["candidate_configuration_parameters"]
        fixed = {name: config[name]["value"] for name in ("walther_a", "walther_b", "native_density_kg_m3")}
        if "api_gravity" in config:
            fixed["api_gravity"] = config["api_gravity"]["value"]
        original = {name: value["value"] for name, value in candidate["original_configuration_parameters"].items()}
        rows = validation_dataset["observations"]
        observed = [float(row["target"]["value"]) for row in rows]
        calibrated = [self._predict_viscosity(row, fixed, fixed) for row in rows]
        uncalibrated = [self._predict_viscosity(row, original, original) for row in rows]
        train_rows = cal_dataset["observations"]
        persistence_value = float(train_rows[-1]["target"]["value"]) if train_rows else None
        baseline = [persistence_value] * len(observed) if persistence_value is not None else []
        policy = self.repository.get_validation_policy("viscosity")
        metrics = {"calibrated": _metrics(observed, calibrated), "uncalibrated": _metrics(observed, uncalibrated),
                   "persistence_baseline": _metrics(observed, baseline)}
        if policy is None:
            status = "VALIDATION_COMPLETED_POLICY_NOT_CONFIGURED"
            policy_check = {"status": "NOT_EVALUATED", "reason": "No explicit versioned operator/research validation policy exists."}
        elif len(rows) < policy["minimum_validation_observations"]:
            status = "INSUFFICIENT_VALIDATION_DATA"
            policy_check = {"status": "NOT_PASSED", "minimum_observations": policy["minimum_validation_observations"], "actual_observations": len(rows), "criteria": []}
        else:
            checks = []
            metric_aliases = {"mae": "mae", "rmse": "rmse", "max_abs_bias": "bias", "mean_absolute_relative_error": "mean_absolute_relative_error"}
            for metric_name, limit in policy["thresholds"].items():
                value = metrics["calibrated"].get(metric_aliases[metric_name])
                passed = value is not None and (abs(value) <= limit if metric_name == "max_abs_bias" else value <= limit)
                checks.append({"metric": metric_name, "value": value, "maximum": limit, "passed": passed})
            all_passed = bool(checks) and all(item["passed"] for item in checks)
            status = "VALIDATION_PASSED" if all_passed else "VALIDATION_FAILED"
            policy_check = {"status": "PASSED" if all_passed else "FAILED", "policy_id": policy["policy_name"], "policy_version": policy["policy_version"], "owner": policy["owner"], "criteria": checks}
        residuals = {name: result.get("residuals", []) for name, result in metrics.items()}
        series = [{"observed_at": row["observed_at"], "measurement_id": row["target"]["measurement_id"],
                   "observed_value": observed[i], "calibrated_prediction": calibrated[i],
                   "uncalibrated_prediction": uncalibrated[i], "persistence_baseline": baseline[i] if baseline else None,
                   "calibrated_residual": calibrated[i] - observed[i], "uncalibrated_residual": uncalibrated[i] - observed[i], "unit": "cP"}
                  for i, row in enumerate(rows)]
        return {"status": status, "candidate_id": candidate["candidate_id"], "model_id": candidate["model_id"], "model_version": candidate["model_version"],
                "calibration_period": cal_dataset["period"], "validation_period": validation_dataset["period"], "temporal_gap_hours": gap_hours,
                "calibration_dataset_fingerprint": cal_dataset["fingerprint"], "validation_dataset_fingerprint": validation_dataset["fingerprint"],
                "calibration_observation_count": len(cal_dataset["observations"]), "validation_observation_count": len(rows),
                "validation_dates": {"start": rows[0]["observed_at"] if rows else None, "end": rows[-1]["observed_at"] if rows else None},
                "metrics": metrics, "policy": policy_check, "residuals": residuals, "series": series,
                "improvement_vs_uncalibrated_mae": (metrics["uncalibrated"]["mae"] - metrics["calibrated"]["mae"]) if metrics["calibrated"]["mae"] is not None and metrics["uncalibrated"]["mae"] is not None else None,
                "measurement_provenance": [row["target"]["measurement_id"] for row in rows],
                "field_validation_claim": "NOT_ESTABLISHED_WITHOUT_INDEPENDENT_DOMAIN_REVIEW_AND_REAL_FIELD_EVIDENCE"}
