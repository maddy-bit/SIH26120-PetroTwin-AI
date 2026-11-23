"""Explicit CSS -> thermal cooling -> viscosity -> SRP coupling for simulation studies.

This composes the project's existing simplified models. It is not a reservoir simulator,
not a calibrated multiphase flow model, and not field validated.
"""
from __future__ import annotations

import math
from typing import Any

from physics.thermal_model import ThermalModel
from physics.viscosity_model import ViscosityModel
from physics.srp_model import SRPModel


class CoupledCssSrpModel:
    MODEL_ID = "petrotwin.css-srp-coupled.simulation.v1"

    def __init__(
        self,
        thermal_model: ThermalModel | None = None,
        viscosity_model: ViscosityModel | None = None,
        srp_model: SRPModel | None = None,
    ):
        self.thermal_model = thermal_model or ThermalModel()
        self.viscosity_model = viscosity_model or ViscosityModel()
        self.srp_model = srp_model or SRPModel()

    @staticmethod
    def _validate_number(name: str, value: float, lower: float, upper: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        if value < lower or value > upper:
            raise ValueError(f"{name} must be between {lower} and {upper}")
        return float(value)

    def evaluate(
        self,
        *,
        steam_mass_tons: float,
        soak_days: float,
        production_day: float,
        stroke_length_m: float,
        spm: float,
        pressure_bar: float = 55.0,
        average_daily_production_bbl: float = 90.0,
        thermal_efficiency: float = 0.72,
        pump_fillage: float = 0.88,
    ) -> dict[str, Any]:
        """Evaluate one explicit scenario and return every intermediate coupling state."""
        steam_mass_tons = self._validate_number("steam_mass_tons", steam_mass_tons, 0.1, 10000.0)
        soak_days = self._validate_number("soak_days", soak_days, 0.0, 365.0)
        production_day = self._validate_number("production_day", production_day, 0.0, 3650.0)
        stroke_length_m = self._validate_number("stroke_length_m", stroke_length_m, 0.1, 10.0)
        spm = self._validate_number("spm", spm, 0.1, 30.0)
        pressure_bar = self._validate_number("pressure_bar", pressure_bar, 0.0, 200.0)
        average_daily_production_bbl = self._validate_number(
            "average_daily_production_bbl", average_daily_production_bbl, 0.0, 100000.0
        )
        thermal_efficiency = self._validate_number("thermal_efficiency", thermal_efficiency, 0.01, 1.0)
        pump_fillage = self._validate_number("pump_fillage", pump_fillage, 0.01, 1.0)

        css = self.thermal_model.calculate_peak_temperature(
            steam_mass_tons, soak_days, thermal_efficiency=thermal_efficiency
        )
        production_temperature = self.thermal_model.predict_temperature_at_day(
            production_day,
            css["peak_temperature_c"],
            avg_daily_prod_bbl=average_daily_production_bbl,
        )
        viscosity = self.viscosity_model.calculate_viscosity(production_temperature, pressure_bar)
        srp = self.srp_model.evaluate_srp_performance(
            stroke_length_m, spm, viscosity, pump_fillage=pump_fillage
        )

        return {
            "model_id": self.MODEL_ID,
            "status": "SIMULATION_ONLY",
            "field_eligible": False,
            "calibration_status": "NOT_CALIBRATED_ON_FIELD_DATA",
            "coupling_chain": [
                {
                    "stage": "CSS_HEAT_INPUT",
                    "inputs": {
                        "steam_mass_tons": steam_mass_tons,
                        "soak_days": soak_days,
                        "thermal_efficiency_assumption": thermal_efficiency,
                    },
                    "outputs": css,
                },
                {
                    "stage": "THERMAL_COOLING",
                    "inputs": {
                        "peak_temperature_c": css["peak_temperature_c"],
                        "production_day": production_day,
                        "average_daily_production_bbl_assumption": average_daily_production_bbl,
                    },
                    "outputs": {"production_temperature_c": production_temperature},
                },
                {
                    "stage": "VISCOSITY_RESPONSE",
                    "inputs": {
                        "production_temperature_c": production_temperature,
                        "pressure_bar": pressure_bar,
                    },
                    "outputs": {"viscosity_cp": viscosity},
                },
                {
                    "stage": "SRP_MECHANICS",
                    "inputs": {
                        "viscosity_cp": viscosity,
                        "stroke_length_m": stroke_length_m,
                        "spm": spm,
                        "pump_fillage_assumption": pump_fillage,
                    },
                    "outputs": srp,
                },
            ],
            "outputs": {
                "css_thermal": css,
                "production_temperature_c": production_temperature,
                "viscosity_cp": viscosity,
                "srp_performance": srp,
            },
            "assumptions": {
                "thermal_efficiency": thermal_efficiency,
                "average_daily_production_bbl": average_daily_production_bbl,
                "pressure_bar": pressure_bar,
                "pump_fillage": pump_fillage,
                "thermal_model_parameters": "constructor defaults unless explicitly injected",
                "viscosity_model_parameters": "constructor defaults unless explicitly injected",
                "srp_geometry_and_fluid_parameters": "constructor defaults unless explicitly injected",
            },
            "limitations": [
                "Thermal response is a simplified heat-retention and exponential cooling estimate.",
                "Viscosity uses the project's empirical Walther-style relationship and simplified density/pressure corrections.",
                "SRP loads and rod-floating risk use the project's approximate rod/annular-drag model.",
                "This coupling does not solve reservoir multiphase flow, relative permeability, wellbore heat transfer, rod-string wave dynamics or measured dynamometer-card inversion.",
                "Outputs are not calibrated, field-validated or suitable as operating setpoints.",
            ],
            "decision_support_only": True,
        }
