import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ml_service.services.physics_execution import FieldPhysicsExecutionService


def config(parameter_updates=None):
    params = {
        "native_temp_c": 47, "steam_temp_c": 295, "steam_quality": 0.78,
        "latent_heat_kj_kg": 1420, "water_cp_kj_kg_k": 4.184,
        "formation_thickness_m": 18, "porosity": 0.26, "rock_density_kg_m3": 2450,
        "rock_cp_kj_kg_k": 0.92, "conduction_decay_rate": 0.0135,
        "walther_a": 8.924, "walther_b": 3.315, "api_gravity": 18.2,
        "native_density_kg_m3": 945, "pump_depth_m": 900,
        "plunger_diameter_mm": 57.15, "rod_weight_air_n": 31200,
        "tubing_id_mm": 62, "rod_outer_diameter_mm": 22.22,
        "fluid_density_kg_m3": 945, "steel_density_kg_m3": 7850,
    }
    units = {
        "native_temp_c": "°C", "steam_temp_c": "°C", "steam_quality": "fraction",
        "latent_heat_kj_kg": "kJ/kg", "water_cp_kj_kg_k": "kJ/kg/K",
        "formation_thickness_m": "m", "porosity": "fraction", "rock_density_kg_m3": "kg/m3",
        "rock_cp_kj_kg_k": "kJ/kg/K", "conduction_decay_rate": "1/day",
        "walther_a": "dimensionless", "walther_b": "dimensionless", "api_gravity": "API",
        "native_density_kg_m3": "kg/m3", "pump_depth_m": "m", "plunger_diameter_mm": "mm",
        "rod_weight_air_n": "N", "tubing_id_mm": "mm", "rod_outer_diameter_mm": "mm",
        "fluid_density_kg_m3": "kg/m3", "steel_density_kg_m3": "kg/m3",
    }
    params.update(parameter_updates or {})
    parameters = {key: {"value": value, "unit": units[key], "source": "test well record",
                        "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"}
                 for key, value in params.items()}
    return {"configuration_id": "config-1", "config_version": 1, "parameters": parameters}


def snapshot(measurement_updates=None, age=timedelta(seconds=1)):
    now = datetime.now(timezone.utc)
    values = {"temperature_c": (75, "°C"), "bottomhole_pressure_bar": (65, "bar"),
              "steam_injected_tons": (2000, "metric_ton"), "soak_days": (6, "day"),
              "stroke_length_m": (2.4, "m"), "spm": (6, "stroke/min"), "viscosity_cp": (250, "cP")}
    values.update(measurement_updates or {})
    measurements = {key: {"measurement_id": f"measurement-{key}", "well_id": "FIELD-TEST", "variable": key,
                          "value": value[0], "unit": value[1], "quality_status": "VALID",
                          "measured_at": (now - age).isoformat(), "source_id": "source-test",
                          "provenance": {"source_id": "source-test"}}
                   for key, value in values.items()}
    return {"snapshot_id": "snapshot-1", "well_id": "FIELD-TEST", "state_version": 1,
            "created_at": (now - age).isoformat(), "measurements": measurements}


class TestFieldPhysicsExecution(unittest.TestCase):
    def setUp(self):
        self.service = FieldPhysicsExecutionService()

    def test_explicit_complete_configuration_executes_real_models_and_captures_provenance(self):
        result = self.service.execute(snapshot(), config())
        self.assertEqual(result["model_results"]["css_thermal"]["status"], "EXECUTED")
        self.assertEqual(result["model_results"]["viscosity"]["status"], "EXECUTED")
        self.assertEqual(result["model_results"]["srp"]["status"], "EXECUTED")
        css = result["model_results"]["css_thermal"]
        self.assertIn("peak_temperature_c", css["outputs"])
        self.assertEqual(css["inputs_consumed"]["measurements"][0]["source_id"], "source-test")
        self.assertEqual(css["inputs_consumed"]["configuration_version"], 1)
        self.assertEqual(result["calibration_status"], "NOT_CALIBRATED")
        self.assertEqual(result["eligibility"]["css_thermal"]["status"], "EXECUTED")
        self.assertEqual(result["eligibility"]["production_reservoir"]["status"], "BLOCKED")
        self.assertEqual(result["eligibility"]["css_srp_interaction"]["status"], "BLOCKED")

    def test_missing_configuration_and_unvalidated_assumptions_block_without_defaults(self):
        report = self.service.eligibility(snapshot(), None)
        self.assertEqual(report["css_thermal"]["status"], "BLOCKED")
        self.assertTrue(report["css_thermal"]["missing_inputs"]["configuration"])
        partial = config()
        partial["parameters"].pop("native_temp_c")
        partial["parameters"]["steam_temp_c"]["validation_status"] = "REVIEWED"
        report = self.service.eligibility(snapshot(), partial)
        self.assertEqual(report["css_thermal"]["status"], "BLOCKED")
        self.assertIn("native_temp_c", report["css_thermal"]["missing_inputs"]["configuration"])
        self.assertIn("steam_temp_c", report["css_thermal"]["reasons"][0] + " " + " ".join(report["css_thermal"]["reasons"]))

    def test_unused_api_gravity_is_not_required_or_used_by_field_viscosity_execution(self):
        with_optional = config()
        without_optional = config()
        without_optional["parameters"].pop("api_gravity")
        first = self.service.execute(snapshot(), with_optional)
        second = self.service.execute(snapshot(), without_optional)
        self.assertEqual(first["model_results"]["viscosity"]["outputs"], second["model_results"]["viscosity"]["outputs"])
        self.assertNotIn("api_gravity", second["model_results"]["viscosity"]["inputs_consumed"]["configuration"])

    def test_invalid_units_values_and_assumed_parameters_block(self):
        bad = config()
        bad["parameters"]["porosity"]["value"] = 1.2
        bad["parameters"]["steam_temp_c"]["unit"] = "K"
        bad["parameters"]["rock_density_kg_m3"]["classification"] = "ASSUMED"
        report = self.service.eligibility(snapshot(), bad)
        self.assertEqual(report["css_thermal"]["status"], "BLOCKED")
        self.assertTrue({"porosity", "steam_temp_c", "rock_density_kg_m3"}.issubset(set(report["css_thermal"]["invalid_inputs"])))

    def test_stale_snapshot_and_invalid_measurement_block_execution(self):
        stale = self.service.eligibility(snapshot(age=timedelta(days=2)), config())
        self.assertEqual(stale["css_thermal"]["status"], "BLOCKED")
        self.assertTrue(stale["css_thermal"]["stale_inputs"])
        invalid_snapshot = snapshot()
        invalid_snapshot["measurements"]["temperature_c"]["quality_status"] = "SUSPECT"
        invalid = self.service.eligibility(invalid_snapshot, config())
        self.assertEqual(invalid["viscosity"]["status"], "BLOCKED")
        out_of_model_range = snapshot({"temperature_c": (400, "°C")})
        bounded = self.service.eligibility(out_of_model_range, config())
        self.assertEqual(bounded["viscosity"]["status"], "BLOCKED")

    def test_calibration_is_only_assessed_and_excludes_suspect_records(self):
        assessment = self.service.calibration_eligibility("FIELD-TEST", [
            {"variable": "temperature_c", "measured_at": datetime.now(timezone.utc).isoformat(), "quality_status": "VALID"},
            {"variable": "viscosity_cp", "measured_at": datetime.now(timezone.utc).isoformat(), "quality_status": "SUSPECT"},
        ])
        self.assertEqual(assessment["status"], "NOT_ASSESSED")
        self.assertEqual(assessment["models"]["viscosity"]["observed_counts"]["viscosity_cp"], 0)
        self.assertEqual(assessment["models"]["viscosity"]["excluded_non_valid_counts"]["viscosity_cp"], 1)
        self.assertEqual(assessment["activation"], "NO_FITTED_PARAMETERS_CAN_BE_ACTIVATED_BY_THIS_ASSESSMENT")

    def test_one_engine_failure_does_not_abort_independent_models(self):
        with patch("ml_service.services.physics_execution.ThermalModel.calculate_peak_temperature", side_effect=RuntimeError("thermal failure")):
            result = self.service.execute(snapshot(), config())
        self.assertEqual(result["model_results"]["viscosity"]["status"], "EXECUTED")
        self.assertEqual(result["model_results"]["srp"]["status"], "EXECUTED")
        self.assertEqual(result["eligibility"]["css_thermal"]["status"], "FAILED")
        self.assertIn("thermal failure", result["errors"]["css_thermal"])
        self.assertEqual(result["execution_status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
