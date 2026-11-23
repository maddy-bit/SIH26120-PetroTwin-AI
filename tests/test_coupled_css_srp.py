import math
import unittest

from physics.coupled_css_srp_model import CoupledCssSrpModel


class TestCoupledCssSrpModel(unittest.TestCase):
    def setUp(self):
        self.model = CoupledCssSrpModel()

    def evaluate(self, production_day):
        return self.model.evaluate(
            steam_mass_tons=2200,
            soak_days=6,
            production_day=production_day,
            stroke_length_m=2.4,
            spm=6.5,
        )

    def test_css_heat_cooling_viscosity_and_srp_are_a_single_traceable_chain(self):
        result = self.evaluate(30)
        self.assertEqual(result["status"], "SIMULATION_ONLY")
        self.assertFalse(result["field_eligible"])
        self.assertEqual(result["calibration_status"], "NOT_CALIBRATED_ON_FIELD_DATA")
        stages = result["coupling_chain"]
        self.assertEqual(
            [stage["stage"] for stage in stages],
            ["CSS_HEAT_INPUT", "THERMAL_COOLING", "VISCOSITY_RESPONSE", "SRP_MECHANICS"],
        )
        self.assertEqual(
            stages[1]["inputs"]["peak_temperature_c"],
            stages[0]["outputs"]["peak_temperature_c"],
        )
        self.assertEqual(
            stages[2]["inputs"]["production_temperature_c"],
            stages[1]["outputs"]["production_temperature_c"],
        )
        self.assertEqual(
            stages[3]["inputs"]["viscosity_cp"],
            stages[2]["outputs"]["viscosity_cp"],
        )
        self.assertTrue(math.isfinite(result["outputs"]["srp_performance"]["pprl_lbs"]))

    def test_cooling_increases_viscosity_and_transfers_it_to_srp_drag(self):
        early = self.evaluate(0)
        late = self.evaluate(60)
        self.assertLess(
            late["outputs"]["production_temperature_c"],
            early["outputs"]["production_temperature_c"],
        )
        self.assertGreater(late["outputs"]["viscosity_cp"], early["outputs"]["viscosity_cp"])
        self.assertGreater(
            late["outputs"]["srp_performance"]["viscous_drag_lbf"],
            early["outputs"]["srp_performance"]["viscous_drag_lbf"],
        )
        self.assertGreater(
            late["outputs"]["srp_performance"]["rod_floating_risk"],
            early["outputs"]["srp_performance"]["rod_floating_risk"],
        )

    def test_invalid_inputs_and_non_finite_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "steam_mass_tons"):
            self.model.evaluate(
                steam_mass_tons=float("nan"), soak_days=6, production_day=30,
                stroke_length_m=2.4, spm=6.5,
            )
        with self.assertRaisesRegex(ValueError, "spm"):
            self.model.evaluate(
                steam_mass_tons=2200, soak_days=6, production_day=30,
                stroke_length_m=2.4, spm=-1,
            )


if __name__ == "__main__":
    unittest.main()
