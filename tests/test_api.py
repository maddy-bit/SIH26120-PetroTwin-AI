import unittest
import os
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Never point API tests at a developer's configured database.
_test_data_dir = tempfile.TemporaryDirectory(prefix="petrotwin-api-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_test_data_dir.name) / 'api.sqlite3'}"
os.environ["PETROTWIN_DATA_MODE"] = "simulation"

from fastapi.testclient import TestClient

from ml_service.main import app


class TestApplicationApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_reports_simulation_and_database(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data_mode"], "SIMULATION")
        self.assertEqual(response.json()["database"], "READY")

    def test_well_list_is_database_backed_and_unknown_well_is_rejected(self):
        wells = self.client.get("/api/wells")
        self.assertEqual(wells.status_code, 200)
        well_ids = {well["well_id"] for well in wells.json()["wells"]}
        self.assertTrue({"BW-DEMO-001", "BW-DEMO-002", "BW-DEMO-003"}.issubset(well_ids))
        self.assertIn("FIELD-CSV-001", well_ids)
        self.assertEqual(self.client.get("/api/wells/not-a-well/telemetry").status_code, 404)

    def test_bounds_and_time_machine_contract(self):
        invalid = self.client.post("/simulate/srp", json={"spm": 99})
        self.assertEqual(invalid.status_code, 422)
        state = self.client.get("/api/wells/BW-DEMO-001/time-machine/90")
        self.assertEqual(state.status_code, 200)
        payload = state.json()
        self.assertEqual(payload["cycle_info"]["days_in_production"], 90)
        self.assertEqual(payload["data_source_mode"], "SIMULATION")

    def test_forecast_endpoint_returns_explicit_heuristic_range_and_saves_run(self):
        response = self.client.post("/predict/production", json={"well_id": "BW-DEMO-001"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["confidence"], "NOT_CALIBRATED")
        self.assertIn("not calibrated", payload["range_method"].lower())
        self.assertIn("run_id", payload)
        self.assertEqual(payload["inputs"]["well_id"], "BW-DEMO-001")
        self.assertIn("temperature_c", payload["inputs"])
        runs = self.client.get("/api/wells/BW-DEMO-001/analysis-runs").json()["runs"]
        saved = next(run for run in runs if run["run_id"] == payload["run_id"])
        self.assertEqual(saved["result"]["inputs"], payload["inputs"])

    def test_optimization_is_saved_and_retrievable(self):
        response = self.client.post("/optimize/joint", json={"well_id": "BW-DEMO-001"})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["algorithm"], "Finite grid search with weighted recommendation and nondominated filtering")
        self.assertIn("run_id", result)
        self.assertEqual(result["inputs"]["well_id"], "BW-DEMO-001")
        self.assertIn("objective_weights", result["inputs"])
        history = self.client.get("/api/wells/BW-DEMO-001/analysis-runs")
        self.assertEqual(history.status_code, 200)
        saved = next(run for run in history.json()["runs"] if run["run_id"] == result["run_id"])
        self.assertEqual(saved["result"]["inputs"], result["inputs"])
        self.assertIsNone(result["recommended_plan"]["css"]["injection_pressure_bar"])
        self.assertEqual(result["recommended_plan"]["css"]["production_horizon_days"], 120.0)

    def test_optimization_rejects_all_zero_objective_weights(self):
        response = self.client.post("/optimize/joint", json={
            "well_id": "BW-DEMO-001", "weight_production": 0, "weight_sor": 0,
            "weight_energy": 0, "weight_risk": 0,
        })
        self.assertEqual(response.status_code, 422)

    def test_scenario_cutoff_changes_cycle_oil_and_sor(self):
        base = {
            "well_id": "BW-DEMO-001", "steam_volume": 2400, "soak_time": 6,
            "stroke_length": 2.4, "spm": 6.5,
        }
        short = self.client.post("/simulate/scenario", json={**base, "production_cutoff": 30})
        long = self.client.post("/simulate/scenario", json={**base, "production_cutoff": 150})
        self.assertEqual(short.status_code, 200)
        self.assertEqual(long.status_code, 200)
        self.assertEqual(short.json()["production_cutoff_days"], 30)
        self.assertEqual(long.json()["production_cutoff_days"], 150)
        self.assertGreater(long.json()["estimated_cycle_oil_bbl"], short.json()["estimated_cycle_oil_bbl"])
        self.assertLess(long.json()["sor"], short.json()["sor"])
        self.assertEqual(short.json()["production_bpd"], long.json()["production_bpd"])

    def test_scenario_rejects_unsupported_pressure_and_redundant_vfd_inputs(self):
        base = {"well_id": "BW-DEMO-001", "production_cutoff": 115}
        unsupported_pressure = self.client.post(
            "/simulate/scenario", json={**base, "injection_pressure": 80}
        )
        redundant_vfd = self.client.post("/simulate/scenario", json={**base, "vfd": 42})
        self.assertEqual(unsupported_pressure.status_code, 422)
        self.assertEqual(redundant_vfd.status_code, 422)

    def test_scenario_soak_and_steam_inputs_change_thermal_outputs(self):
        base = {
            "well_id": "BW-DEMO-001", "steam_volume": 2400, "soak_time": 6,
            "production_cutoff": 115, "stroke_length": 2.4, "spm": 6.5,
        }
        baseline = self.client.post("/simulate/scenario", json=base).json()
        more_steam = self.client.post(
            "/simulate/scenario", json={**base, "steam_volume": 3000}
        ).json()
        longer_soak = self.client.post(
            "/simulate/scenario", json={**base, "soak_time": 12}
        ).json()
        self.assertNotEqual(more_steam["total_heat_injected_gj"], baseline["total_heat_injected_gj"])
        self.assertNotEqual(more_steam["heated_radius_m"], baseline["heated_radius_m"])
        self.assertNotEqual(longer_soak["heat_retained_post_soak_gj"], baseline["heat_retained_post_soak_gj"])
        self.assertNotEqual(longer_soak["heated_radius_m"], baseline["heated_radius_m"])

    def test_csv_ingestion_validates_units_preserves_provenance_and_is_idempotent(self):
        well = self.client.post("/api/v1/wells", json={
            "well_id": "FIELD-CSV-001", "name": "Ingestion test well",
            "depth_m": 1200, "pump_depth_m": 1050,
        })
        self.assertEqual(well.status_code, 200)
        self.assertEqual(self.client.get("/api/wells/FIELD-CSV-001/telemetry").status_code, 503)
        csv_text = (
            "well_id,measured_at,variable,value,unit,external_id\n"
            "FIELD-CSV-001,2026-11-21T10:00:00Z,bottomhole_pressure_bar,3000,kPa,p-1\n"
            "FIELD-CSV-001,2026-11-21T10:00:00Z,oil_rate_bpd,85,bbl/day,q-1\n"
            "FIELD-CSV-001,2026-11-21T10:00:00Z,temperature_c,75,bar,bad-unit\n"
        )
        first = self.client.post(
            "/api/v1/measurements/csv?source_id=csv-test",
            content=csv_text,
            headers={"Content-Type": "text/csv"},
        )
        self.assertEqual(first.status_code, 200)
        result = first.json()
        self.assertEqual(result["accepted"], 2)
        self.assertEqual(len(result["rejected"]), 1)
        self.assertEqual(result["provenance"]["source_type"], "CSV")
        self.assertTrue(result["ingestion_batch_id"])
        second = self.client.post(
            "/api/v1/measurements/csv?source_id=csv-test",
            content=csv_text.splitlines()[0] + "\n" + "\n".join(csv_text.splitlines()[1:3]) + "\n",
            headers={"Content-Type": "text/csv"},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["accepted"], 0)
        self.assertEqual(second.json()["duplicates"], 2)
        measurements = self.client.get("/api/v1/wells/FIELD-CSV-001/measurements")
        self.assertEqual(measurements.status_code, 200)
        pressure = next(item for item in measurements.json()["records"] if item["variable"] == "bottomhole_pressure_bar")
        self.assertEqual(pressure["value"], 30.0)
        self.assertEqual(pressure["unit"], "bar")
        self.assertEqual(pressure["source_id"], "csv-test")
        self.assertEqual(pressure["provenance"]["processing_stage"], "validated_ingestion")
        self.assertEqual(pressure["provenance"]["original_value"], 3000)
        self.assertEqual(pressure["provenance"]["original_unit"], "kPa")
        self.assertEqual(pressure["provenance"]["source_record_id"], "p-1")

    def test_field_state_is_incomplete_and_traceable_without_fabricated_values(self):
        well_id = "FIELD-STATE-001"
        created = self.client.post("/api/v1/wells", json={"well_id": well_id, "name": "State test"})
        self.assertEqual(created.status_code, 200)
        ingest = self.client.post("/api/v1/measurements", json={"source_id": "state-api", "records": [{
            "well_id": well_id, "measured_at": "2026-11-22T10:00:00Z", "variable": "oil_rate_bpd",
            "value": 42, "unit": "bbl/day", "external_id": "row-42",
        }]})
        self.assertEqual(ingest.status_code, 200)
        stale = self.client.post("/api/v1/measurements", json={"source_id": "state-api", "records": [{
            "well_id": well_id, "measured_at": "2026-11-20T10:00:00Z", "variable": "temperature_c",
            "value": 70, "unit": "C", "external_id": "stale-temp",
        }]})
        self.assertEqual(stale.status_code, 200)
        state = self.client.post(f"/api/v1/wells/{well_id}/twin-state").json()
        self.assertEqual(state["status"], "AVAILABLE_MEASUREMENTS")
        self.assertEqual(state["measurements"]["oil_rate_bpd"]["value"], 42)
        self.assertEqual(state["measurement_references"], [state["measurements"]["oil_rate_bpd"]["measurement_id"]])
        self.assertIn("temperature_c", state["missing_measurement_types"])
        self.assertIn("temperature_c", state["stale_measurement_types"])
        self.assertNotIn("temperature_c", state["suspect_measurement_types"])
        self.assertEqual(state["calibration"]["status"], "NOT_CALIBRATED")
        self.assertEqual(state["uncertainty"], "NOT_ESTIMATED_NO_VALIDATED_METHOD")

    def test_measurement_query_filters_type_and_quality_and_rejects_naive_time(self):
        invalid = self.client.post("/api/v1/measurements", json={"source_id": "bad-time", "records": [{
            "well_id": "FIELD-CSV-001", "measured_at": "2026-11-22T10:00:00", "variable": "oil_rate_bpd", "value": 1, "unit": "bbl/day",
        }]})
        self.assertEqual(invalid.status_code, 422)
        response = self.client.get("/api/v1/wells/FIELD-CSV-001/measurements?variable=bottomhole_pressure_bar&quality_status=VALID")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(row["variable"] == "bottomhole_pressure_bar" and row["quality_status"] == "VALID" for row in response.json()["records"]))

    def test_operational_cycle_event_srp_import_timeline_and_readiness_apis(self):
        well_id = "FIELD-OPS-API-001"
        self.assertEqual(self.client.post("/api/v1/wells", json={"well_id":well_id,"name":"Operational API fixture"}).status_code,200)
        provenance={"source_record_id":"api-fixture-1","quality_protocol":"test-only"}
        cycle={"cycle_number":1,"injection_start":"2025-01-01T00:00:00Z","injection_end":"2025-01-01T12:00:00Z",
            "soak_start":"2025-01-01T12:00:00Z","soak_end":"2025-01-03T12:00:00Z","production_restart":"2025-01-03T12:00:00Z",
            "post_soak_observation_start":"2025-01-03T12:00:00Z","post_soak_observation_end":"2025-01-10T00:00:00Z",
            "injection_mass_tons":{"value":1800,"unit":"metric_ton"},"injection_pressure_bar":{"value":45,"unit":"bar"},
            "injection_temperature_c":{"value":290,"unit":"°C"},"source":"api-controlled-fixture","provenance":provenance}
        created=self.client.post(f"/api/v1/wells/{well_id}/css-cycles",json=cycle)
        self.assertEqual(created.status_code,200,created.text)
        cycle_id=created.json()["cycle_id"]
        self.assertEqual(created.json()["status"],"COMPLETE")
        self.assertEqual(self.client.get(f"/api/v1/css-cycles/{cycle_id}").status_code,200)
        listed=self.client.get(f"/api/v1/wells/{well_id}/css-cycles").json()["cycles"]
        self.assertEqual(len(listed),1)
        invalid=self.client.post(f"/api/v1/wells/{well_id}/css-cycles",json={**cycle,"cycle_number":2,"soak_start":"2025-01-01T11:00:00Z"})
        self.assertEqual(invalid.status_code,422)
        measured=self.client.post("/api/v1/measurements",json={"source_id":"ops-link-fixture","records":[
            {"well_id":well_id,"measured_at":"2025-01-04T00:00:00Z","variable":"temperature_c","value":104,"unit":"°C","external_id":"temp-after-soak","metadata":{"measurement_context":"RESERVOIR_TEMPERATURE","sensor_reference":"downhole-sensor-7"}},
            {"well_id":well_id,"measured_at":"2025-01-04T01:00:00Z","variable":"oil_rate_bpd","value":88,"unit":"bbl/day","external_id":"cycle-oil-rate"}]})
        self.assertEqual(measured.status_code,200)
        records=self.client.get(f"/api/v1/wells/{well_id}/measurements?days=3650").json()["records"]
        for record,relation in ((next(x for x in records if x["variable"]=="temperature_c"),"POST_SOAK_TEMPERATURE"),(next(x for x in records if x["variable"]=="oil_rate_bpd"),"PRODUCTION_OUTCOME")):
            linked=self.client.post("/api/v1/operational-measurement-links",json={"entity_type":"css_cycle","entity_id":cycle_id,"measurement_id":record["measurement_id"],"relation":relation})
            self.assertEqual(linked.status_code,200,linked.text)
        event=self.client.post(f"/api/v1/wells/{well_id}/operational-events",json={"cycle_id":cycle_id,"event_type":"WORKOVER","occurred_at":"2025-02-01T00:00:00Z","source":"operator","provenance":provenance})
        self.assertEqual(event.status_code,200,event.text)
        event_id=event.json()["event_id"]
        self.assertEqual(self.client.get(f"/api/v1/operational-events/{event_id}").json()["event_type"],"WORKOVER")
        srp=self.client.post(f"/api/v1/wells/{well_id}/srp-records",json={"record_type":"CONFIGURATION","valid_from":"2025-01-01T00:00:00Z","parameters":{"pump_depth_m":{"value":1400,"unit":"m"}},"source":"well-file","provenance":provenance})
        self.assertEqual(srp.status_code,200,srp.text)
        self.assertEqual(srp.json()["record_type"],"CONFIGURATION")
        imported=self.client.post("/api/v1/operational-data/import/json",json={"schema_version":"1.0","record_type":"event","records":[{"well_id":well_id,"event_type":"SHUTDOWN","occurred_at":"2025-03-01T00:00:00Z","external_id":"shutdown-1","source":"operator","provenance":provenance}]})
        self.assertEqual(imported.status_code,200,imported.text)
        self.assertEqual(imported.json()["accepted"],1)
        duplicate=self.client.post("/api/v1/operational-data/import/json",json={"schema_version":"1.0","record_type":"event","records":[{"well_id":well_id,"event_type":"SHUTDOWN","occurred_at":"2025-03-01T00:00:00Z","external_id":"shutdown-1","source":"operator","provenance":provenance}]})
        self.assertEqual(duplicate.json()["duplicates"],1)
        timeline=self.client.get(f"/api/v1/wells/{well_id}/operational-timeline").json()
        self.assertEqual(len(timeline["entries"]),4)
        readiness=self.client.get(f"/api/v1/wells/{well_id}/operational-calibration-readiness").json()
        self.assertEqual(readiness["css"]["status"],"DATA_LINKAGE_READY_FOR_DOMAIN_REVIEW")
        self.assertEqual(readiness["css"]["sample_size_assessment"],"DOMAIN_DEFINED_THRESHOLD_NOT_SET")
        dataset=self.client.post(f"/api/v1/wells/{well_id}/operational-datasets",json={"dataset_type":"css_cycle","start_at":"2025-01-01T00:00:00Z","end_at":"2025-02-01T00:00:00Z"})
        self.assertEqual(dataset.status_code,200,dataset.text)
        self.assertEqual(dataset.json()["observation_count"],1)
        self.assertIn("CHRONOLOGICAL",dataset.json()["split_method"].upper())
        scientific=self.client.post(f"/api/v1/wells/{well_id}/calibration-datasets",json={"model_id":"css_thermal","start_at":"2025-01-01T00:00:00Z","end_at":"2025-02-01T00:00:00Z"})
        self.assertEqual(scientific.status_code,200,scientific.text)
        self.assertEqual(scientific.json()["observation_count"],1)
        self.assertEqual(scientific.json()["observations"][0]["cycle_id"],cycle_id)

    def test_physics_execution_uses_existing_css_engine_and_persists_partial_run(self):
        well_id = "FIELD-PHYSICS-001"
        self.client.post("/api/v1/wells", json={"well_id": well_id, "name": "Physics test"})
        records = [
            {"well_id":well_id,"measured_at":"2026-11-22T10:00:00Z","variable":"steam_injected_tons","value":2000,"unit":"metric_ton"},
            {"well_id":well_id,"measured_at":"2026-11-22T10:01:00Z","variable":"soak_days","value":6,"unit":"day"},
        ]
        self.client.post("/api/v1/measurements", json={"source_id":"physics-test","records":records})
        snapshot = self.client.post(f"/api/v1/wells/{well_id}/twin-state?window_hours=168").json()
        config = {"parameters": {
            "native_temp_c":{"value":47,"unit":"°C","source":"well-test","classification":"OPERATOR_CONFIGURED"},
            "steam_temp_c":{"value":295,"unit":"°C","source":"steam-spec","classification":"OPERATOR_CONFIGURED"},
            "steam_quality":{"value":0.78,"unit":"fraction","source":"steam-spec","classification":"OPERATOR_CONFIGURED"},
            "latent_heat_kj_kg":{"value":1420,"unit":"kJ/kg","source":"steam-spec","classification":"OPERATOR_CONFIGURED"},
            "water_cp_kj_kg_k":{"value":4.184,"unit":"kJ/kg/K","source":"reference","classification":"OPERATOR_CONFIGURED"},
            "formation_thickness_m":{"value":18,"unit":"m","source":"well-log","classification":"OPERATOR_CONFIGURED"},
            "porosity":{"value":0.26,"unit":"fraction","source":"core-analysis","classification":"OPERATOR_CONFIGURED"},
            "rock_density_kg_m3":{"value":2450,"unit":"kg/m3","source":"core-analysis","classification":"OPERATOR_CONFIGURED"},
            "rock_cp_kj_kg_k":{"value":0.92,"unit":"kJ/kg/K","source":"reference","classification":"OPERATOR_CONFIGURED"},
            "conduction_decay_rate":{"value":0.0135,"unit":"1/day","source":"calibration-pending","classification":"OPERATOR_CONFIGURED"},
        }}
        for parameter in config["parameters"].values():
            parameter["validation_status"] = "VALIDATED"
        saved = self.client.put(f"/api/v1/wells/{well_id}/physical-configuration", json=config)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["config_version"], 1)
        self.assertEqual(saved.json()["parameters"]["native_temp_c"]["configuration_version"], 1)
        self.assertEqual(self.client.post(f"/api/v1/wells/{well_id}/physics-runs", json={"snapshot_id":snapshot["snapshot_id"], "configuration_version":2}).status_code, 409)
        eligibility = self.client.get(f"/api/v1/wells/{well_id}/physics-eligibility?snapshot_id={snapshot['snapshot_id']}")
        self.assertEqual(eligibility.status_code, 200)
        self.assertEqual(eligibility.json()["models"]["css_thermal"]["status"], "ELIGIBLE")
        run = self.client.post(f"/api/v1/wells/{well_id}/physics-runs", json={"snapshot_id":snapshot["snapshot_id"]})
        self.assertEqual(run.status_code, 200)
        payload = run.json()
        self.assertEqual(payload["execution_status"], "PARTIAL")
        self.assertEqual(payload["model_results"]["css_thermal"]["status"], "EXECUTED")
        self.assertIn("peak_temperature_c", payload["model_results"]["css_thermal"]["outputs"])
        self.assertEqual(payload["model_results"]["css_thermal"]["validation_status"], "NOT_VALIDATED_ON_HELD_OUT_FIELD_DATA")
        self.assertEqual(self.client.get(f"/api/v1/physics-runs/{payload['run_id']}").json()["run_id"], payload["run_id"])
        self.assertEqual(self.client.get(f"/api/v1/wells/{well_id}/physics-runs").json()["runs"][0]["run_id"], payload["run_id"])
        comparison = self.client.get(f"/api/v1/physics-runs/{payload['run_id']}/comparisons")
        self.assertEqual(comparison.status_code, 200)
        self.assertEqual(comparison.json()["status"], "NO_COMPATIBLE_MEASURED_OUTPUTS")
        calibration = self.client.get(f"/api/v1/wells/{well_id}/calibration-eligibility")
        self.assertEqual(calibration.status_code, 200)
        self.assertEqual(calibration.json()["status"], "NOT_ASSESSED")

    def test_physical_configuration_rejects_invalid_units_and_fraction_values(self):
        well_id = "FIELD-CONFIG-INVALID-001"
        self.client.post("/api/v1/wells", json={"well_id": well_id, "name": "Config validation"})
        invalid = self.client.put(f"/api/v1/wells/{well_id}/physical-configuration", json={"parameters": {
            "steam_quality": {"value": 1.5, "unit": "fraction", "source": "test", "classification": "OPERATOR_CONFIGURED"},
            "native_temp_c": {"value": 45, "unit": "K", "source": "test", "classification": "OPERATOR_CONFIGURED"},
        }})
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("steam_quality", str(invalid.json()["detail"]))
        self.assertIn("native_temp_c", str(invalid.json()["detail"]))

    def test_physical_configuration_converts_supported_fraction_units_with_provenance(self):
        well_id = "FIELD-CONFIG-UNITS-001"
        self.client.post("/api/v1/wells", json={"well_id": well_id, "name": "Config unit conversion"})
        saved = self.client.put(f"/api/v1/wells/{well_id}/physical-configuration", json={"parameters": {
            "steam_quality": {"value": 78, "unit": "%", "source": "steam quality sheet", "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"},
        }})
        self.assertEqual(saved.status_code, 200)
        parameter = saved.json()["parameters"]["steam_quality"]
        self.assertEqual(parameter["value"], 0.78)
        self.assertEqual(parameter["unit"], "fraction")
        self.assertEqual(parameter["source_value"], 78)
        self.assertEqual(parameter["source_unit"], "%")

    def test_physics_comparison_reports_only_compatible_measurement_pair(self):
        well_id = "FIELD-COMPARE-001"
        self.client.post("/api/v1/wells", json={"well_id": well_id, "name": "Comparison well"})
        self.client.post("/api/v1/measurements", json={"source_id": "compare-test", "records": [
            {"well_id":well_id,"measured_at":"2026-11-22T10:00:00Z","variable":"temperature_c","value":75,"unit":"C"},
            {"well_id":well_id,"measured_at":"2026-11-22T10:00:00Z","variable":"bottomhole_pressure_bar","value":65,"unit":"bar"},
            {"well_id":well_id,"measured_at":"2026-11-22T10:00:00Z","variable":"viscosity_cp","value":240,"unit":"cP"},
        ]})
        snapshot = self.client.post(f"/api/v1/wells/{well_id}/twin-state").json()
        params = {"walther_a":(8.924,"dimensionless"),"walther_b":(3.315,"dimensionless"),"api_gravity":(18.2,"API"),"native_density_kg_m3":(945,"kg/m3")}
        config = {"parameters": {key:{"value":value,"unit":unit,"source":"lab-test","classification":"OPERATOR_CONFIGURED","validation_status":"VALIDATED"} for key,(value,unit) in params.items()}}
        self.assertEqual(self.client.put(f"/api/v1/wells/{well_id}/physical-configuration", json=config).status_code, 200)
        run = self.client.post(f"/api/v1/wells/{well_id}/physics-runs", json={"snapshot_id":snapshot["snapshot_id"]}).json()
        comparison = self.client.get(f"/api/v1/physics-runs/{run['run_id']}/comparisons").json()
        self.assertEqual(comparison["status"], "AVAILABLE")
        self.assertEqual(comparison["comparisons"][0]["measurement_id"], snapshot["measurements"]["viscosity_cp"]["measurement_id"])
        self.assertEqual(comparison["comparisons"][0]["comparison_status"], "INFORMATIONAL_SINGLE_SNAPSHOT_COMPARISON_NOT_VALIDATION")

    def test_scientific_calibration_persists_candidate_and_blocks_activation(self):
        from physics.viscosity_model import ViscosityModel
        well_id = "FIELD-CALIBRATION-API-001"
        self.client.post("/api/v1/wells", json={"well_id": well_id, "name": "Controlled API calibration test"})
        parameters = {
            "walther_a": (9.2, "dimensionless"), "walther_b": (3.55, "dimensionless"),
            "api_gravity": (18.2, "API"), "native_density_kg_m3": (945, "kg/m3"),
        }
        config_payload = {"parameters": {key: {"value": value, "unit": unit, "source": "controlled-test-fixture",
                           "classification": "OPERATOR_CONFIGURED", "validation_status": "VALIDATED"}
                           for key, (value, unit) in parameters.items()}}
        self.assertEqual(self.client.put(f"/api/v1/wells/{well_id}/physical-configuration", json=config_payload).status_code, 200)
        truth = ViscosityModel(8.8, 3.3, 18.2, 945)
        records = []
        for period, first_day in (("calibration", 0), ("validation", 60)):
            for index, temperature in enumerate((35, 45, 55, 65, 75, 85, 95, 105, 120, 140)):
                measured_at = (datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=first_day + index * 2)).isoformat()
                pressure = 55 + (index % 4) * 3
                records.extend([
                    {"well_id": well_id, "measured_at": measured_at, "variable": "temperature_c", "value": temperature, "unit": "°C", "external_id": f"{period}-temp-{index}"},
                    {"well_id": well_id, "measured_at": measured_at, "variable": "bottomhole_pressure_bar", "value": pressure, "unit": "bar", "external_id": f"{period}-pressure-{index}"},
                    {"well_id": well_id, "measured_at": measured_at, "variable": "viscosity_cp", "value": truth.calculate_viscosity(temperature, pressure), "unit": "cP", "external_id": f"{period}-viscosity-{index}"},
                ])
        ingested = self.client.post("/api/v1/measurements", json={"source_id": "controlled-calibration-test", "records": records})
        self.assertEqual(ingested.status_code, 200)
        self.assertEqual(ingested.json()["accepted"], 60)
        cal_data = self.client.post(f"/api/v1/wells/{well_id}/calibration-datasets", json={
            "model_id": "viscosity", "start_at": "2025-01-01T00:00:00Z", "end_at": "2025-02-01T00:00:00Z",
            "tolerance_minutes": 1, "dataset_role": "CALIBRATION",
        })
        self.assertEqual(cal_data.status_code, 200, cal_data.text)
        dataset = cal_data.json()
        self.assertEqual(dataset["observation_count"], 10)
        self.assertEqual(self.client.get(f"/api/v1/calibration-datasets/{dataset['dataset_id']}").json()["fingerprint"], dataset["fingerprint"])
        identifiable = self.client.post(f"/api/v1/calibration-datasets/{dataset['dataset_id']}/identifiability")
        self.assertEqual(identifiable.status_code, 200)
        self.assertGreaterEqual(identifiable.json()["sensitivity_matrix_rank"], 2)
        calibration = self.client.post(f"/api/v1/wells/{well_id}/calibrations", json={
            "dataset_id": dataset["dataset_id"], "selected_parameters": ["walther_a", "walther_b"],
            "parameter_bounds": {"walther_a": {"lower": 8.0, "upper": 10.0, "unit": "dimensionless"}, "walther_b": {"lower": 3.0, "upper": 4.0, "unit": "dimensionless"}},
        })
        self.assertEqual(calibration.status_code, 200, calibration.text)
        run = calibration.json()
        self.assertEqual(run["status"], "CALIBRATION_COMPLETED")
        candidate_id = run["candidate"]["candidate_id"]
        self.assertEqual(run["candidate"]["activation_enabled"], False)
        self.assertEqual(self.client.get(f"/api/v1/calibrations/{run['calibration_id']}").status_code, 200)
        policy = self.client.put("/api/v1/models/viscosity/validation-policy", json={
            "policy_name": "controlled-test-permissive", "owner": "test-only", "minimum_validation_observations": 2,
            "thresholds": {"mae": 1000000, "rmse": 1000000, "max_abs_bias": 1000000, "mean_absolute_relative_error": 1000000},
        })
        self.assertEqual(policy.status_code, 200)
        validation = self.client.post(f"/api/v1/calibration-candidates/{candidate_id}/validate", json={
            "start_at": "2025-03-01T00:00:00Z", "end_at": "2025-04-01T00:00:00Z", "tolerance_minutes": 1, "temporal_gap_hours": 24,
        })
        self.assertEqual(validation.status_code, 200, validation.text)
        self.assertEqual(validation.json()["status"], "VALIDATION_PASSED")
        self.assertTrue(validation.json()["series"])
        self.assertEqual(self.client.get(f"/api/v1/validation-runs/{validation.json()['validation_id']}").status_code, 200)
        comparison = self.client.get(f"/api/v1/calibration-candidates/{candidate_id}/comparison")
        self.assertEqual(comparison.status_code, 200)
        self.assertEqual(comparison.json()["latest_validation"]["validation_id"], validation.json()["validation_id"])
        candidate = self.client.get(f"/api/v1/calibration-candidates/{candidate_id}").json()
        self.assertEqual(candidate["lifecycle_status"], "APPROVAL_PENDING")
        self.assertEqual(candidate["candidate_configuration_parameters"]["walther_a"]["validation_status"], "UNVALIDATED")
        self.assertEqual(self.client.post(f"/api/v1/calibration-candidates/{candidate_id}/approve").status_code, 403)
        self.assertEqual(self.client.get(f"/api/v1/wells/{well_id}/active-calibration-history").json()["activation_enabled"], False)
        self.assertEqual(self.client.get(f"/api/v1/wells/{well_id}/physical-configuration").json()["configuration"]["config_version"], 1)
        self.assertEqual(self.client.post(f"/api/v1/calibration-candidates/{candidate_id}/reject", json={"reason": "test lifecycle"}).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/calibration-candidates/{candidate_id}").json()["lifecycle_status"], "REJECTED")

    def test_field_mode_hides_demo_profiles_and_reports_missing_measurements(self):
        from ml_service.config import config
        previous_mode = config.data_mode
        config.data_mode = "field"
        try:
            wells = self.client.get("/api/wells").json()["wells"]
            self.assertFalse(any(item["well_id"].startswith("BW-DEMO-") for item in wells))
            self.assertEqual(self.client.get("/api/wells/BW-DEMO-001/telemetry").status_code, 404)
            self.assertEqual(self.client.post("/simulate/css", json={}).status_code, 503)
            self.assertEqual(self.client.post("/simulate/srp", json={}).status_code, 503)
            empty = self.client.post("/api/v1/wells", json={"well_id": "FIELD-EMPTY-001", "name": "Empty well"})
            self.assertEqual(empty.status_code, 200)
            unavailable = self.client.get("/api/wells/FIELD-EMPTY-001/telemetry")
            self.assertEqual(unavailable.status_code, 503)
            self.assertIn("measured data", unavailable.json()["detail"])
            scenario = self.client.post("/simulate/scenario", json={
                "well_id": "FIELD-EMPTY-001", "days_in_cycle": 10,
                "steam_volume": 2400, "soak_time": 6, "production_cutoff": 115,
                "stroke_length": 2.4, "spm": 6.5,
            })
            self.assertEqual(scenario.status_code, 503)
            self.assertIn("Synthetic CSS + SRP", scenario.json()["detail"])
            self.assertEqual(self.client.get("/health").json()["data_mode"], "FIELD")
        finally:
            config.data_mode = previous_mode


if __name__ == "__main__":
    unittest.main()
