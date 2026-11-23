"""
Unit and Integration Tests for PETRO-TWIN AI ML Service & Agent Supervisor
"""

import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml_service.models.production_forecaster import ProductionForecaster
from ml_service.models.failure_predictor import FailurePredictor
from ml_service.models.anomaly_detector import AnomalyDetector
from ml_service.optimizer.pareto_optimizer import ParetoOptimizer
from agent.agent_supervisor import AgentSupervisor


class TestMLService(unittest.TestCase):
    def setUp(self):
        self.forecaster = ProductionForecaster()
        self.failure_predictor = FailurePredictor()
        self.anomaly_detector = AnomalyDetector()
        self.optimizer = ParetoOptimizer()
        self.agent = AgentSupervisor()

    def test_production_forecaster_horizons(self):
        """Production forecaster must predict t+1, t+7, and t+30 with expanding uncertainty intervals."""
        res = self.forecaster.predict(temp_c=80.0, pressure_bar=50.0, spm=6.5, stroke_length_m=2.4, days_since_injection=45)
        self.assertIn("forecast_horizons", res)
        h = res["forecast_horizons"]
        
        self.assertGreater(h["t_plus_1"]["prediction_bpd"], 0)
        self.assertGreater(h["t_plus_30"]["uncertainty_pct"], h["t_plus_1"]["uncertainty_pct"])
        self.assertLess(h["t_plus_1"]["lower_estimate_bpd"], h["t_plus_1"]["prediction_bpd"])
        self.assertGreater(h["t_plus_1"]["upper_estimate_bpd"], h["t_plus_1"]["prediction_bpd"])
        self.assertIn("not calibrated", res["range_method"])

    def test_failure_predictor_multi_hazard(self):
        """Failure predictor must evaluate rod float, impact load, parted rod, and feature attribution."""
        res = self.failure_predictor.predict_failure_risks(stroke_length_m=2.4, spm=8.5, temp_c=50.0)
        self.assertIn("risks", res)
        self.assertIn("rod_floating", res["risks"])
        self.assertIn("parted_rod", res["risks"])
        self.assertIn("feature_contributions", res)
        self.assertIn("heuristic", res["contribution_method"].lower())
        # Cold temperature + high SPM must trigger elevated rod float risk
        self.assertGreater(res["risks"]["rod_floating"]["probability"], 0.40)
        self.assertGreater(len(res["feature_contributions"]), 0)

    def test_anomaly_detector_boundary(self):
        """Anomaly detector must flag extreme load as anomalous."""
        # Normal frame
        norm_res = self.anomaly_detector.detect(temp_c=85.0, pressure_bar=48.0, pprl_lbs=14500.0,
                                               mprl_lbs=3200.0, oil_rate_bpd=95.0, motor_power_kw=18.0)
        self.assertFalse(norm_res["is_anomaly"])

        # Anomalous frame (dangerous structural overload > 22,000 lbs)
        abnorm_res = self.anomaly_detector.detect(temp_c=85.0, pressure_bar=48.0, pprl_lbs=24000.0,
                                                 mprl_lbs=200.0, oil_rate_bpd=2.0, motor_power_kw=32.0)
        self.assertTrue(abnorm_res["is_anomaly"])
        self.assertIn(abnorm_res["severity"], ["WARNING", "CRITICAL"])

    def test_missing_artifacts_are_labeled_as_unvalidated_fallbacks(self):
        with patch("ml_service.models.production_forecaster.os.path.exists", return_value=False):
            production = ProductionForecaster()
        with patch("ml_service.models.anomaly_detector.os.path.exists", return_value=False):
            anomaly = AnomalyDetector()
        with patch("ml_service.models.failure_predictor.os.path.exists", return_value=False):
            failure = FailurePredictor()
        self.assertIn("SYNTHETIC_FALLBACK", production.model_status)
        self.assertIn("SYNTHETIC_BASELINE", anomaly.model_status)
        self.assertIn("HEURISTIC_FALLBACK", failure.model_status)
        self.assertNotIn("CALIBRATED", production.model_status)
        self.assertNotIn("CALIBRATED", anomaly.model_status)
        self.assertNotIn("CALIBRATED", failure.model_status)

    def test_pareto_optimizer_convergence(self):
        """Optimizer must return a feasible plan and a populated Pareto frontier."""
        current_state = {"oil_rate_bpd": 80.0, "sor": 4.5, "energy_kwh_bbl": 2.2, "failure_risk": 0.42}
        opt_res = self.optimizer.run_optimization(current_state)
        self.assertEqual(opt_res["status"], "GRID_SEARCH_COMPLETED")
        self.assertIn("recommended_plan", opt_res)
        self.assertIn("pareto_frontier", opt_res)
        self.assertGreater(len(opt_res["pareto_frontier"]), 5)
        
        plan = opt_res["recommended_plan"]
        self.assertGreater(plan["srp"]["spm"], 2.0)
        self.assertLess(plan["srp"]["spm"], 10.0)
        self.assertEqual(opt_res["constraint_verification"]["candidate_feasible"], True)
        self.assertIn("gearbox torque", opt_res["constraint_verification"]["checks_not_evaluated"])
        self.assertNotIn("gearbox_peak_torque", opt_res["constraint_verification"])

    def test_optimizer_handles_no_feasible_candidate(self):
        infeasible = {"is_feasible": False, "violations": ["test"], "spm": 1.0,
                      "stroke_length_m": 4.0, "steam_mass_tons": 1800.0, "production_bpd": 1.0}
        with patch.object(self.optimizer, "evaluate_candidate", return_value=infeasible):
            result = self.optimizer.run_optimization({})
        self.assertEqual(result["status"], "NO_FEASIBLE_CANDIDATE")
        self.assertIsNone(result["recommended_plan"])

    def test_optimizer_does_not_recommend_unsupported_pressure_or_cutoff(self):
        result = self.optimizer.run_optimization({"days_in_production": 40})
        css_plan = result["recommended_plan"]["css"]
        self.assertIsNone(css_plan["injection_pressure_bar"])
        self.assertEqual(css_plan["production_horizon_days"], 120.0)
        self.assertTrue(any("not optimized" in item.lower() for item in css_plan["unsupported_controls"]))

    def test_optimizer_rejects_zero_or_invalid_objective_weights(self):
        with self.assertRaisesRegex(ValueError, "at least one must be positive"):
            self.optimizer.run_optimization({}, 0, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, "finite, non-negative"):
            self.optimizer.run_optimization({}, -0.1, 0.4, 0.3, 0.3)

    def test_optimizer_passes_selected_cycle_day_and_handles_zero_baselines(self):
        observed_days = set()
        original_evaluate = self.optimizer.evaluate_candidate

        def record_day(*args, **kwargs):
            observed_days.add(kwargs["days_in_cycle"])
            return original_evaluate(*args, **kwargs)

        with patch.object(self.optimizer, "evaluate_candidate", side_effect=record_day):
            result = self.optimizer.run_optimization({
                "oil_rate_bpd": 0.0, "sor": 0.0, "energy_kwh_bbl": 0.0,
                "failure_risk": 0.0, "days_in_production": 90,
            })
        self.assertEqual(observed_days, {90})
        self.assertIsNone(result["expected_outcome"]["production_change_pct"])
        self.assertIsNone(result["expected_outcome"]["sor_change_pct"])
        self.assertIsNone(result["expected_outcome"]["energy_change_pct"])
        self.assertIsNone(result["expected_outcome"]["failure_risk_change_pct"])

    def test_agent_supervisor_tools_and_query(self):
        """Agent must execute deterministic tools and answer query with structured evidence."""
        query_res = self.agent.handle_user_query("What do you recommend for next CSS cycle?")
        self.assertIn("answer", query_res)
        self.assertIn("tools_used", query_res)
        self.assertIn("evidence_data", query_res)
        self.assertIn("get_well_state", query_res["tools_used"])
        self.assertIn("optimize_operations", query_res["tools_used"])


if __name__ == "__main__":
    unittest.main()
