"""
PETRO-TWIN AI: Constrained Multi-Objective Pareto Optimizer
===========================================================
Joint optimization of Cyclic Steam Stimulation (CSS) and Sucker Rod Pump (SRP).
Objectives:
1. Maximize clean heavy oil production (bbl/day)
2. Minimize cumulative Steam-to-Oil Ratio (SOR)
3. Minimize electrical energy consumption (kWh/barrel)
4. Minimize mechanical failure & rod-floating risk (0.0 to 1.0)
"""

import math
from typing import Dict, Any, List, Tuple
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from physics.thermal_model import ThermalModel
from physics.viscosity_model import ViscosityModel
from physics.srp_model import SRPModel
from physics.coupled_css_srp_model import CoupledCssSrpModel


class ParetoOptimizer:
    """
    Constrained Multi-Objective Optimizer for CSS + SRP.
    """
    def __init__(self):
        self.thermal_model = ThermalModel()
        self.visc_model = ViscosityModel()
        self.srp_model = SRPModel()
        self.coupled_model = CoupledCssSrpModel(self.thermal_model, self.visc_model, self.srp_model)

    def evaluate_candidate(self, steam_mass_tons: float, soak_days: float, stroke_length_m: float,
                           spm: float, days_in_cycle: int = 40,
                           production_cutoff_days: float = 120.0) -> Dict[str, Any]:
        """
        Evaluates physical feasibility, production, SOR, energy, and failure risk of a candidate plan.
        """
        # 1–2. Explicit CSS -> cooling -> viscosity -> SRP model chain.
        # The same simplified model formulations are retained, but every
        # intermediate state is now part of the candidate evidence.
        coupled = self.coupled_model.evaluate(
            steam_mass_tons=steam_mass_tons,
            soak_days=soak_days,
            production_day=float(days_in_cycle),
            stroke_length_m=stroke_length_m,
            spm=spm,
            pressure_bar=55.0,
            average_daily_production_bbl=90.0,
            thermal_efficiency=0.72,
            pump_fillage=0.88,
        )
        peak_res = coupled["outputs"]["css_thermal"]
        current_temp = coupled["outputs"]["production_temperature_c"]
        viscosity_cp = coupled["outputs"]["viscosity_cp"]
        srp_eval = coupled["outputs"]["srp_performance"]
        prod_bpd = srp_eval["estimated_production_bpd"]
        kwh_per_bbl = srp_eval["kwh_per_barrel"]
        rod_float_risk = srp_eval["rod_floating_risk"]
        pprl = srp_eval["pprl_lbs"]
        mprl = srp_eval["mprl_lbs"]

        # 3. Estimated cycle cumulative oil & SOR. The 0.82 factor is a
        # simplified assumed average-to-peak production ratio over the horizon.
        avg_cycle_prod = prod_bpd * 0.82
        cum_oil_bbl = avg_cycle_prod * production_cutoff_days
        # Steam CWE bbls = tons * 6.2898 (since 1 m3 water ~ 1 ton ~ 6.29 bbl)
        steam_bbls = steam_mass_tons * 6.2898
        sor = steam_bbls / max(100.0, cum_oil_bbl)

        # 4. Constraint verification
        violations = []
        if spm > 9.5:
            violations.append(f"SPM ({spm}) exceeds maximum mechanical limit of 9.5")
        if spm < 2.0:
            violations.append(f"SPM ({spm}) below minimum motor cooling limit of 2.0")
        if stroke_length_m > 3.0:
            violations.append(f"Stroke ({stroke_length_m}m) exceeds walking beam geometry limit")
        if pprl > 22000.0:
            violations.append(f"Peak load ({pprl} lbs) exceeds API structure rating (22,000 lbs)")
        if rod_float_risk > 0.40:
            violations.append(f"Rod floating risk ({round(rod_float_risk*100, 1)}%) exceeds safety threshold (40%)")
        if soak_days < 2.0:
            violations.append(f"Soak period ({soak_days} days) insufficient to condense high-pressure steam")

        is_feasible = len(violations) == 0

        return {
            "steam_mass_tons": round(steam_mass_tons, 1),
            "soak_days": round(soak_days, 1),
            "stroke_length_m": round(stroke_length_m, 2),
            "spm": round(spm, 2),
            "vfd_frequency_hz": round(spm * 6.46, 1),
            "production_bpd": round(prod_bpd, 1),
            "production_cutoff_days": round(production_cutoff_days, 1),
            "estimated_cycle_oil_bbl": round(cum_oil_bbl, 1),
            "peak_temperature_c": peak_res["peak_temperature_c"],
            "heated_radius_m": peak_res["heated_radius_m"],
            "total_heat_injected_gj": peak_res["total_heat_injected_gj"],
            "heat_retained_post_soak_gj": peak_res["heat_retained_post_soak_gj"],
            "temperature_at_cycle_day_c": current_temp,
            "sor": round(sor, 2),
            "energy_kwh_bbl": round(kwh_per_bbl, 2),
            "failure_risk": round(rod_float_risk, 3),
            "peak_polished_rod_load_lbs": pprl,
            "viscosity_cp": viscosity_cp,
            "coupled_model_id": coupled["model_id"],
            "coupling_chain": coupled["coupling_chain"],
            "model_validation_status": coupled["calibration_status"],
            "field_eligible": coupled["field_eligible"],
            "is_feasible": is_feasible,
            "violations": violations
        }

    def run_optimization(self, current_state: Dict[str, Any], weight_prod: float = 0.40,
                         weight_sor: float = 0.25, weight_energy: float = 0.15,
                         weight_risk: float = 0.20) -> Dict[str, Any]:
        """
        Executes exploration across operating space, discovers Pareto frontier, and selects best compromise.
        """
        weights = (weight_prod, weight_sor, weight_energy, weight_risk)
        if any(not math.isfinite(weight) or weight < 0 for weight in weights) or sum(weights) <= 0:
            raise ValueError("Objective weights must be finite, non-negative, and at least one must be positive")

        candidates = []
        pareto_points = []
        
        # Exhaustive evaluation over this small, explicitly defined grid.
        steam_options = [1800.0, 2200.0, 2600.0, 3000.0]
        soak_options = [4.0, 6.0, 8.0]
        stroke_options = [2.0, 2.4, 2.8]
        spm_options = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5]

        best_score = -999999.0
        best_candidate = None
        rejected_candidates = []

        for st in steam_options:
            for sk in soak_options:
                for sl in stroke_options:
                    for spm in spm_options:
                        eval_res = self.evaluate_candidate(
                            st, sk, sl, spm,
                            days_in_cycle=int(current_state.get("days_in_production", 40)),
                        )
                        candidates.append(eval_res)

                        if eval_res["is_feasible"]:
                            # Normalized objective scoring:
                            # Higher production is better, lower SOR, energy, and risk are better
                            norm_prod = (eval_res["production_bpd"] - 20.0) / 180.0
                            norm_sor = 1.0 - (min(8.0, eval_res["sor"]) - 1.5) / 6.5
                            norm_energy = 1.0 - (min(4.0, eval_res["energy_kwh_bbl"]) - 0.8) / 3.2
                            norm_risk = 1.0 - eval_res["failure_risk"]

                            composite_score = (
                                weight_prod * norm_prod +
                                weight_sor * norm_sor +
                                weight_energy * norm_energy +
                                weight_risk * norm_risk
                            )

                            pareto_points.append({
                                "production_bpd": eval_res["production_bpd"],
                                "sor": eval_res["sor"],
                                "energy_kwh_bbl": eval_res["energy_kwh_bbl"],
                                "failure_risk": eval_res["failure_risk"],
                                "spm": eval_res["spm"],
                                "stroke_m": eval_res["stroke_length_m"],
                                "steam_tons": eval_res["steam_mass_tons"],
                                "composite_score": round(composite_score, 3)
                            })

                            if composite_score > best_score:
                                best_score = composite_score
                                best_candidate = eval_res
                        else:
                            if len(rejected_candidates) < 5:
                                rejected_candidates.append({
                                    "spm": eval_res["spm"],
                                    "stroke_m": eval_res["stroke_length_m"],
                                    "steam_tons": eval_res["steam_mass_tons"],
                                    "production_bpd": eval_res["production_bpd"],
                                    "rejection_reason": "; ".join(eval_res["violations"])
                                })

        # Baseline comparison
        curr_prod = current_state.get("oil_rate_bpd", 85.0)
        curr_sor = current_state.get("sor", 4.8)
        curr_energy = current_state.get("energy_kwh_bbl", 2.3)
        curr_risk = current_state.get("failure_risk", 0.38)

        if best_candidate is None:
            return {
                "status": "NO_FEASIBLE_CANDIDATE",
                "algorithm": "Finite grid search with weighted ranking and nondominated filtering",
                "recommended_plan": None,
                "expected_outcome": None,
                "constraint_verification": {"status": "No candidate met the configured constraints"},
                "pareto_frontier": [],
                "rejected_alternatives_sample": rejected_candidates,
                "decision_support_disclaimer": "No recommendation is available; review model assumptions and constraints."
            }

        def percent_change(value: float, baseline: float) -> float | None:
            if baseline == 0:
                return None
            return round(((value - baseline) / baseline) * 100.0, 1)

        prod_change_pct = percent_change(best_candidate["production_bpd"], curr_prod)
        sor_change_pct = percent_change(best_candidate["sor"], curr_sor)
        energy_change_pct = percent_change(best_candidate["energy_kwh_bbl"], curr_energy)
        risk_change_pct = percent_change(best_candidate["failure_risk"], curr_risk)

        # Keep only candidates not dominated on all four tracked objectives.
        nondominated = []
        for candidate in pareto_points:
            dominated = any(
                other is not candidate
                and other["production_bpd"] >= candidate["production_bpd"]
                and other["sor"] <= candidate["sor"]
                and other["energy_kwh_bbl"] <= candidate["energy_kwh_bbl"]
                and other["failure_risk"] <= candidate["failure_risk"]
                and (
                    other["production_bpd"] > candidate["production_bpd"]
                    or other["sor"] < candidate["sor"]
                    or other["energy_kwh_bbl"] < candidate["energy_kwh_bbl"]
                    or other["failure_risk"] < candidate["failure_risk"]
                )
                for other in pareto_points
            )
            if not dominated:
                nondominated.append(candidate)
        pareto_points = sorted(nondominated, key=lambda x: x["composite_score"], reverse=True)

        return {
            "status": "GRID_SEARCH_COMPLETED",
            "algorithm": "Finite grid search with weighted recommendation and nondominated filtering",
            "recommended_plan": {
                "css": {
                    "steam_volume_tons": best_candidate["steam_mass_tons"],
                    "soak_time_days": best_candidate["soak_days"],
                    "injection_pressure_bar": None,
                    "production_horizon_days": best_candidate["production_cutoff_days"],
                    "unsupported_controls": [
                        "Injection pressure is not modeled or optimized.",
                        "Production cutoff is not optimized; the horizon is used only for cycle-oil and SOR estimates.",
                    ],
                },
                "srp": {
                    "stroke_length_m": best_candidate["stroke_length_m"],
                    "spm": best_candidate["spm"],
                    "vfd_frequency_hz": best_candidate["vfd_frequency_hz"],
                    "operating_mode": "THERMAL_TRACKING_CONTINUOUS"
                }
            },
            "expected_outcome": {
                "production_bpd": best_candidate["production_bpd"],
                "production_change_pct": prod_change_pct,
                "sor": best_candidate["sor"],
                "sor_change_pct": sor_change_pct,
                "energy_kwh_bbl": best_candidate["energy_kwh_bbl"],
                "energy_change_pct": energy_change_pct,
                "failure_risk": best_candidate["failure_risk"],
                "failure_risk_change_pct": risk_change_pct,
            },
            "physics_coupling": {
                "model_id": best_candidate["coupled_model_id"],
                "status": "SIMULATION_ONLY",
                "field_eligible": best_candidate["field_eligible"],
                "calibration_status": best_candidate["model_validation_status"],
                "representative_chain": best_candidate["coupling_chain"],
            },
            "constraint_verification": {
                "candidate_feasible": best_candidate["is_feasible"],
                "checks_evaluated": [
                    "SPM operating bounds", "stroke length upper bound",
                    "peak polished rod load upper bound", "rod floating risk threshold",
                    "minimum soak duration",
                ],
                "checks_not_evaluated": [
                    "formation fracture pressure", "gearbox torque", "API allowable stress",
                ],
            },
            "pareto_frontier": pareto_points,
            "rejected_alternatives_sample": rejected_candidates,
            "decision_support_disclaimer": "SIMULATED MODEL ESTIMATE ONLY. No setpoint was dispatched. Engineer review is required before any operational change."
        }
