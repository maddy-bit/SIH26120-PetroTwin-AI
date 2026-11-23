"""Algorithm fixtures are controlled tests, not observed field-data evidence."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from ml_service.services.scientific_calibration import ScientificCalibrationService
from physics.viscosity_model import ViscosityModel


class ControlledMeasurementFixture:
    """Deterministic mathematical measurements generated only for unit tests."""
    def __init__(self, truth=(8.8, 3.3), temperatures=None, start_day=0, suspect_at=None):
        self.rows = []
        truth_model = ViscosityModel(truth[0], truth[1], 18.2, 945)
        temps = temperatures or [35, 45, 55, 65, 75, 85, 95, 105, 120, 140]
        origin = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=start_day)
        for index, temp in enumerate(temps):
            timestamp = (origin + timedelta(days=index * 3)).isoformat()
            quality = "SUSPECT" if suspect_at == index else "VALID"
            values = [("temperature_c", temp, "°C"),
                      ("bottomhole_pressure_bar", 55 + (index % 4) * 3, "bar"),
                      ("viscosity_cp", truth_model.calculate_viscosity(temp, 55 + (index % 4) * 3), "cP")]
            for variable, value, unit in values:
                self.rows.append({"measurement_id": f"fixture-{start_day}-{index}-{variable}", "well_id": "CONTROLLED-TEST-ONLY",
                                  "source_id": "controlled-algorithm-fixture", "measured_at": timestamp,
                                  "variable": variable, "value": value, "unit": unit,
                                  "quality_status": quality, "provenance": {"source_type": "CONTROLLED_TEST_FIXTURE"}})

    def query_measurements(self, well_id, *, start_at=None, end_at=None, limit=10000, **kwargs):
        start = datetime.fromisoformat(start_at.replace("Z", "+00:00")) if start_at else None
        end = datetime.fromisoformat(end_at.replace("Z", "+00:00")) if end_at else None
        return [copy.deepcopy(row) for row in self.rows if (start is None or datetime.fromisoformat(row["measured_at"]) >= start)
                and (end is None or datetime.fromisoformat(row["measured_at"]) <= end)][:limit]

    def get_physical_configuration(self, well_id):
        return {"configuration_id": "controlled-config", "config_version": 1, "well_id": well_id,
                "parameters": {
                    "walther_a": {"value": 9.2, "unit": "dimensionless", "source": "fixture", "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"},
                    "walther_b": {"value": 3.55, "unit": "dimensionless", "source": "fixture", "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"},
                    "api_gravity": {"value": 18.2, "unit": "API", "source": "fixture", "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"},
                    "native_density_kg_m3": {"value": 945, "unit": "kg/m3", "source": "fixture", "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"},
                }}

    def get_physical_configuration_by_id(self, config_id):
        return self.get_physical_configuration("CONTROLLED-TEST-ONLY")

    def save_calibration_dataset(self, payload):
        return {"dataset_id": f"dataset-{len(payload['observations'])}-{payload['fingerprint'][:8]}", **payload}

    def get_calibration_dataset(self, dataset_id):
        return self.datasets.get(dataset_id) if hasattr(self, "datasets") else None

    def get_validation_policy(self, model_id):
        return getattr(self, "policy", None)


class TestScientificCalibration(unittest.TestCase):
    def setUp(self):
        self.fixture = ControlledMeasurementFixture()
        self.service = ScientificCalibrationService(self.fixture)
        self.start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        self.end = datetime(2025, 3, 1, tzinfo=timezone.utc)

    def make_dataset(self, fixture=None, start=None, end=None, role="CALIBRATION"):
        repo = fixture or self.fixture
        return ScientificCalibrationService(repo).build_dataset("CONTROLLED-TEST-ONLY", "viscosity",
            start or self.start, end or self.end, 15, role)

    def test_dataset_is_reproducible_traceable_and_contains_only_valid_pairs(self):
        first = self.make_dataset()
        second = self.make_dataset()
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["observation_count"], 10)
        self.assertEqual(first["observations"][0]["target"]["provenance"]["source_type"], "CONTROLLED_TEST_FIXTURE")
        self.assertEqual(first["observations"][0]["inputs"]["temperature_c"]["unit"], "°C")
        self.assertEqual(first["pairing"]["method"], "nearest_timestamp_without_input_reuse")

    def test_quality_exclusion_and_duplicate_measurements_are_reported(self):
        fixture = ControlledMeasurementFixture(suspect_at=0)
        fixture.rows.append({**fixture.rows[3], "measurement_id": "duplicate-input", "source_id": "second-source"})
        dataset = self.make_dataset(fixture=fixture)
        self.assertEqual(dataset["observation_count"], 9)
        reasons = [item["reason"] for item in dataset["excluded_records"]]
        self.assertIn("quality_not_valid", reasons)
        self.assertIn("duplicate_variable_timestamp", reasons)

    def test_identifiability_uses_sensitivity_and_blocks_no_temperature_variation(self):
        dataset = self.make_dataset()
        assessment = self.service.assess_identifiability(dataset, self.fixture.get_physical_configuration("CONTROLLED-TEST-ONLY"))
        self.assertIn("finite-difference Jacobian of log viscosity", assessment["method"])
        self.assertGreaterEqual(assessment["sensitivity_matrix_rank"], 2)
        self.assertIn(assessment["parameters"]["walther_a"]["classification"], {"POTENTIALLY_IDENTIFIABLE", "WEAKLY_IDENTIFIABLE"})
        self.assertEqual(assessment["excluded_parameters"]["api_gravity"]["classification"], "NOT_IDENTIFIABLE")
        constant_fixture = ControlledMeasurementFixture(temperatures=[70] * 8)
        constant_service = ScientificCalibrationService(constant_fixture)
        constant_data = constant_service.build_dataset("CONTROLLED-TEST-ONLY", "viscosity", self.start, self.end)
        constant = constant_service.assess_identifiability(constant_data, constant_fixture.get_physical_configuration("CONTROLLED-TEST-ONLY"))
        self.assertEqual(constant["parameters"]["walther_a"]["classification"], "INSUFFICIENT_DATA")

    def test_calibration_respects_bounds_and_improves_controlled_in_sample_fit(self):
        dataset = self.make_dataset()
        configuration = self.fixture.get_physical_configuration("CONTROLLED-TEST-ONLY")
        result = self.service.calibrate(dataset, configuration, ["walther_a", "walther_b"],
            {"walther_a": {"lower": 8.0, "upper": 10.0, "unit": "dimensionless"}, "walther_b": {"lower": 3.0, "upper": 4.0, "unit": "dimensionless"}})
        self.assertEqual(result["status"], "CALIBRATION_COMPLETED")
        self.assertLess(result["calibration_metrics"]["mae"], result["uncalibrated_metrics"]["mae"])
        self.assertLessEqual(result["candidate_parameters"]["walther_a"], 10.0)
        self.assertEqual(result["lifecycle_status"], "VALIDATION_PENDING")
        self.assertEqual(result["candidate_configuration_parameters"]["walther_a"]["validation_status"], "UNVALIDATED")
        repeated = self.service.calibrate(dataset, configuration, ["walther_a", "walther_b"],
            {"walther_a": {"lower": 8.0, "upper": 10.0, "unit": "dimensionless"}, "walther_b": {"lower": 3.0, "upper": 4.0, "unit": "dimensionless"}})
        self.assertEqual(repeated["candidate_parameters"], result["candidate_parameters"])
        self.assertEqual(repeated["final_objective"], result["final_objective"])
        with self.assertRaisesRegex(ValueError, "Bounds for walther_a"):
            self.service.calibrate(dataset, configuration, ["walther_a"], {"walther_a": {"lower": 10.0, "upper": 11.0, "unit": "dimensionless"}})

    def test_optimizer_nonconvergence_is_reported_without_candidate_ready_status(self):
        dataset = self.make_dataset()
        configuration = self.fixture.get_physical_configuration("CONTROLLED-TEST-ONLY")
        failed_optimizer = SimpleNamespace(success=False, status=0, message="evaluation limit", nfev=1000,
            optimality=1.0, active_mask=np.array([0, 0]), x=np.array([9.2, 3.55]),
            fun=np.ones(10), jac=np.ones((10, 2)))
        with patch("ml_service.services.scientific_calibration.least_squares", return_value=failed_optimizer):
            result = self.service.calibrate(dataset, configuration, ["walther_a", "walther_b"],
                {"walther_a": {"lower": 8.0, "upper": 10.0, "unit": "dimensionless"},
                 "walther_b": {"lower": 3.0, "upper": 4.0, "unit": "dimensionless"}})
        self.assertEqual(result["status"], "CALIBRATION_FAILED")
        self.assertEqual(result["lifecycle_status"], "CALIBRATION_FAILED")

    def test_chronological_validation_uses_baseline_metrics_and_rejects_overlap(self):
        cal_fixture = ControlledMeasurementFixture(start_day=0)
        service = ScientificCalibrationService(cal_fixture)
        cal = service.build_dataset("CONTROLLED-TEST-ONLY", "viscosity", self.start, datetime(2025, 2, 5, tzinfo=timezone.utc))
        configuration = cal_fixture.get_physical_configuration("CONTROLLED-TEST-ONLY")
        fit = service.calibrate(cal, configuration, ["walther_a", "walther_b"],
            {"walther_a": {"lower": 8.0, "upper": 10.0, "unit": "dimensionless"}, "walther_b": {"lower": 3.0, "upper": 4.0, "unit": "dimensionless"}})
        candidate = {"candidate_id": "candidate-controlled", "model_id": "viscosity", "model_version": fit["model_version"],
                     "candidate_configuration_parameters": fit["candidate_configuration_parameters"],
                     "original_configuration_parameters": fit["original_configuration_parameters"]}
        validation_fixture = ControlledMeasurementFixture(start_day=60)
        validation_service = ScientificCalibrationService(validation_fixture)
        val_start = datetime(2025, 3, 2, tzinfo=timezone.utc)
        val_end = datetime(2025, 5, 1, tzinfo=timezone.utc)
        val = validation_service.build_dataset("CONTROLLED-TEST-ONLY", "viscosity", val_start, val_end, dataset_role="VALIDATION")
        validation_fixture.datasets = {cal["dataset_id"]: cal}
        result = validation_service.validate_candidate(candidate, {"dataset_id": cal["dataset_id"]}, val, 24)
        self.assertEqual(result["status"], "VALIDATION_COMPLETED_POLICY_NOT_CONFIGURED")
        self.assertEqual(result["metrics"]["calibrated"]["count"], val["observation_count"])
        self.assertEqual(len(result["series"]), val["observation_count"])
        self.assertEqual(result["policy"]["status"], "NOT_EVALUATED")
        self.assertIsNotNone(result["metrics"]["persistence_baseline"]["mae"])
        overlapping = validation_service.build_dataset("CONTROLLED-TEST-ONLY", "viscosity", self.start, val_end, dataset_role="VALIDATION")
        with self.assertRaisesRegex(ValueError, "must start after"):
            validation_service.validate_candidate(candidate, {"dataset_id": cal["dataset_id"]}, overlapping, 0)
        boundary_fixture = ControlledMeasurementFixture(start_day=0)
        boundary_service = ScientificCalibrationService(boundary_fixture)
        boundary_cal = boundary_service.build_dataset("CONTROLLED-TEST-ONLY", "viscosity", self.start, datetime(2025, 1, 10, tzinfo=timezone.utc))
        boundary_fixture.datasets = {boundary_cal["dataset_id"]: boundary_cal}
        boundary_val = boundary_service.build_dataset("CONTROLLED-TEST-ONLY", "viscosity", datetime(2025, 1, 10, tzinfo=timezone.utc), datetime(2025, 2, 1, tzinfo=timezone.utc), dataset_role="VALIDATION")
        with self.assertRaisesRegex(ValueError, "measurement IDs overlap"):
            boundary_service.validate_candidate(candidate, {"dataset_id": boundary_cal["dataset_id"]}, boundary_val, 0)

    def test_css_temperature_pairs_are_blocked_without_cycle_linkage(self):
        class CssFixture(ControlledMeasurementFixture):
            def __init__(self):
                self.rows = [
                    {"measurement_id":"steam-1","well_id":"CONTROLLED-TEST-ONLY","source_id":"fixture","measured_at":"2025-01-01T00:00:00+00:00","variable":"steam_injected_tons","value":1000,"unit":"metric_ton","quality_status":"VALID","provenance":{}},
                    {"measurement_id":"soak-1","well_id":"CONTROLLED-TEST-ONLY","source_id":"fixture","measured_at":"2025-01-01T00:00:00+00:00","variable":"soak_days","value":5,"unit":"day","quality_status":"VALID","provenance":{}},
                    {"measurement_id":"temp-1","well_id":"CONTROLLED-TEST-ONLY","source_id":"fixture","measured_at":"2025-01-01T00:00:00+00:00","variable":"temperature_c","value":100,"unit":"°C","quality_status":"VALID","provenance":{}},
                ]
        fixture = CssFixture()
        dataset = ScientificCalibrationService(fixture).build_dataset("CONTROLLED-TEST-ONLY", "css_thermal", self.start, self.end)
        self.assertEqual(dataset["observation_count"], 0)
        self.assertIn("temperature_not_linked_to_css_cycle_and_post_soak_window", [x["reason"] for x in dataset["excluded_records"]])


if __name__ == "__main__":
    unittest.main()
