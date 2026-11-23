"""Build traceable, measurement-backed snapshots without filling missing inputs."""

from datetime import datetime, timedelta, timezone
from typing import Any

from ml_service.persistence import AnalysisRepository


PHYSICS_INPUTS = {
    "viscosity": {"temperature_c", "bottomhole_pressure_bar"},
    "srp_mechanics": {"stroke_length_m", "spm"},
    "css_thermal_response": {"steam_injected_tons", "soak_days"},
}


class FieldTwinStateService:
    def __init__(self, repository: AnalysisRepository, max_age_hours: int = 24):
        self.repository = repository
        self.max_age_hours = max_age_hours

    def build_snapshot(self, well_id: str, window_hours: int = 168) -> dict[str, Any]:
        if window_hours < 1 or window_hours > 24 * 365:
            raise ValueError("window_hours must be between 1 and 8760")
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=window_hours)
        records = self.repository.query_measurements(
            well_id, start_at=start.isoformat(), end_at=now.isoformat(), limit=10000,
        )
        freshness_cutoff = now - timedelta(hours=self.max_age_hours)
        latest_valid: dict[str, dict[str, Any]] = {}
        for record in records:
            measured_at = datetime.fromisoformat(record["measured_at"].replace("Z", "+00:00"))
            if record["quality_status"] == "VALID" and measured_at >= freshness_cutoff:
                latest_valid.setdefault(record["variable"], record)

        observed_types = sorted({record["variable"] for record in records})
        stale_types = sorted({record["variable"] for record in records
                              if datetime.fromisoformat(record["measured_at"].replace("Z", "+00:00")) < freshness_cutoff})
        invalid_types = sorted({record["variable"] for record in records if record["quality_status"] != "VALID"})
        physics = {}
        for name, requirements in PHYSICS_INPUTS.items():
            missing = sorted(requirements - latest_valid.keys())
            physics[name] = {"status": "INPUTS_AVAILABLE_UNVALIDATED" if not missing else "UNAVAILABLE",
                             "missing_inputs": missing,
                             "field_calibration": "NOT_ESTABLISHED"}

        state = {
            "status": "AVAILABLE_MEASUREMENTS" if latest_valid else "INCOMPLETE",
            "data_mode": "MEASURED",
            "measurements": latest_valid,
            "measurement_references": sorted({r["measurement_id"] for r in latest_valid.values()}),
            "observed_measurement_types": observed_types,
            "missing_measurement_types": sorted(set(PHYSICS_INPUTS["viscosity"] | PHYSICS_INPUTS["srp_mechanics"] | PHYSICS_INPUTS["css_thermal_response"]) - latest_valid.keys()),
            "stale_measurement_types": stale_types,
            "suspect_measurement_types": invalid_types,
            "measurement_count_in_window": len(records),
            "fresh_measurement_count": len(latest_valid),
            "state_completeness": "NOT_SCORED_NO_VALIDATED_COMPLETENESS_METHOD",
            "uncertainty": "NOT_ESTIMATED_NO_VALIDATED_METHOD",
            "physics_availability": physics,
            "calibration": {"status": "NOT_CALIBRATED", "reason": "No field calibration workflow or validated parameter set is configured."},
            "model_training": {"status": "NOT_ELIGIBLE", "reason": "No field training eligibility/evaluation pipeline is configured."},
        }
        return self.repository.save_twin_snapshot(well_id, start.isoformat(), now.isoformat(), state)
