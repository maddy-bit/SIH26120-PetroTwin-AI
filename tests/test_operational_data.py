import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ml_service.persistence import AnalysisRepository
from ml_service.services.data_ingestion import DataIngestionService
from ml_service.services.operational_data import OperationalDataService
from ml_service.services.scientific_calibration import ScientificCalibrationService


PROVENANCE = {"source_record_id": "operator-record-1", "source_type": "CONTROLLED_TEST_FIXTURE"}


class TestOperationalData(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite:///{Path(self.temp.name) / 'ops.sqlite3'}"
        self.repo = AnalysisRepository(self.database_url)
        self.repo.initialize()
        self.repo.seed_wells({"OP-TEST-001": {"name": "Controlled operational test fixture"}, "OP-TEST-002": {"name": "Other fixture"}})
        self.service = OperationalDataService(self.repo)
        self.ingestion = DataIngestionService(self.repo)

    def tearDown(self): self.temp.cleanup()

    def cycle_input(self, **changes):
        return {"well_id":"OP-TEST-001","cycle_number":1,"injection_start":"2025-01-01T00:00:00Z","injection_end":"2025-01-01T12:00:00Z",
            "soak_start":"2025-01-01T12:00:00Z","soak_end":"2025-01-03T12:00:00Z","production_restart":"2025-01-03T12:00:00Z",
            "post_soak_observation_start":"2025-01-03T12:00:00Z","post_soak_observation_end":"2025-01-10T00:00:00Z",
            "injection_mass_tons":{"value":1800,"unit":"metric_ton"},"injection_pressure_bar":{"value":45,"unit":"bar"},
            "injection_temperature_c":{"value":290,"unit":"°C"},"steam_quality":{"value":0.78,"unit":"fraction"},
            "source":"controlled-fixture","provenance":PROVENANCE,**changes}

    def ingest(self, variable, value, unit, external_id, metadata=None):
        return self.ingestion.ingest_records([{"well_id":"OP-TEST-001","measured_at":"2025-01-04T00:00:00Z","variable":variable,"value":value,"unit":unit,"external_id":external_id,"metadata":metadata or ({"measurement_context":"RESERVOIR_TEMPERATURE","sensor_reference":"downhole-temp-1"} if variable=="temperature_c" else {})}],"test-measurements")

    def test_css_chronology_incomplete_cycles_and_unit_validation(self):
        incomplete=self.service.create_css_cycle({"well_id":"OP-TEST-001","cycle_number":1,"injection_start":"2025-01-01T00:00:00Z","source":"operator","provenance":PROVENANCE})
        self.assertEqual(incomplete["status"],"INCOMPLETE")
        self.assertIn("soak_start",incomplete["completeness"]["missing_fields"])
        with self.assertRaisesRegex(ValueError,"chronology"):
            self.service.create_css_cycle(self.cycle_input(soak_start="2025-01-01T11:00:00Z"))
        with self.assertRaisesRegex(ValueError,"injection_pressure_bar.unit"):
            self.service.validate_cycle(self.cycle_input(injection_pressure_bar={"value":4500,"unit":"kPa"}))

    def test_cycle_duplicate_measurement_link_dataset_traceability_and_readiness(self):
        cycle=self.service.create_css_cycle(self.cycle_input())
        temp=self.ingest("temperature_c",104,"°C","temp-1")
        oil=self.ingest("oil_rate_bpd",88,"bbl/day","oil-1")
        measurements=self.repo.query_measurements("OP-TEST-001",limit=10)
        by_type={x["variable"]:x for x in measurements}
        self.service.link_measurement("css_cycle",cycle["cycle_id"],by_type["temperature_c"]["measurement_id"],"POST_SOAK_TEMPERATURE")
        self.service.link_measurement("css_cycle",cycle["cycle_id"],by_type["oil_rate_bpd"]["measurement_id"],"PRODUCTION_OUTCOME")
        with self.assertRaisesRegex(ValueError,"different CSS cycle"):
            second=self.service.create_css_cycle(self.cycle_input(cycle_number=2))
            self.service.link_measurement("css_cycle",second["cycle_id"],by_type["temperature_c"]["measurement_id"],"POST_SOAK_TEMPERATURE")
        result=ScientificCalibrationService(self.repo).build_dataset("OP-TEST-001","css_thermal",datetime(2025,1,1,tzinfo=timezone.utc),datetime(2025,2,1,tzinfo=timezone.utc))
        self.assertEqual(result["observation_count"],1)
        self.assertEqual(result["observations"][0]["cycle_id"],cycle["cycle_id"])
        self.assertEqual(result["observations"][0]["target"]["measurement_id"],by_type["temperature_c"]["measurement_id"])
        self.assertEqual(result["observations"][0]["inputs"]["soak_days"]["value"],2)
        self.assertEqual(result["calibration_capability"],"BLOCKED_NOT_IDENTIFIABLE_OR_TARGET_NOT_LINKED")
        readiness=self.service.calibration_readiness("OP-TEST-001")
        self.assertEqual(readiness["css"]["status"],"DATA_LINKAGE_READY_FOR_DOMAIN_REVIEW")
        self.assertEqual(readiness["css"]["sample_size_assessment"],"DOMAIN_DEFINED_THRESHOLD_NOT_SET")
        self.assertFalse(readiness["css_srp_coupled"]["calibration_supported"])

    def test_srp_configuration_is_distinct_from_observations_and_load_card_validation(self):
        config=self.service.create_srp_record({"well_id":"OP-TEST-001","record_type":"CONFIGURATION","valid_from":"2025-01-01T00:00:00Z","valid_to":"2025-12-31T00:00:00Z",
            "parameters":{"pump_depth_m":{"value":1400,"unit":"m"},"plunger_diameter_mm":{"value":38,"unit":"mm"}},"source":"well-file","provenance":PROVENANCE})
        observation=self.service.create_srp_record({"well_id":"OP-TEST-001","record_type":"OPERATING_OBSERVATION","valid_at":"2025-01-04T00:00:00Z",
            "parameters":{"stroke_length_m":{"value":2.4,"unit":"m"},"spm":{"value":6,"unit":"stroke/min"},"oil_rate_bpd":{"value":80,"unit":"bbl/day"}},
            "observations":[{"type":"DYNAMOMETER_CARD","measured_at":"2025-01-04T00:00:00Z","load_unit":"N","points":[{"position_deg":0,"load_n":1000},{"position_deg":180,"load_n":800}],"provenance":PROVENANCE}],
            "source":"field-export","provenance":PROVENANCE})
        readiness=self.service.calibration_readiness("OP-TEST-001")
        self.assertEqual(readiness["srp"]["configuration_record_count"],1)
        self.assertEqual(readiness["srp"]["observation_count"],1)
        self.assertTrue(readiness["srp"]["dynamometer_available"])
        self.assertEqual(config["record_type"],"CONFIGURATION")
        self.assertEqual(observation["record_type"],"OPERATING_OBSERVATION")
        with self.assertRaisesRegex(ValueError,"load_unit"):
            self.service.validate_srp_record({"well_id":"OP-TEST-001","record_type":"OPERATING_OBSERVATION","valid_at":"2025-01-04T00:00:00Z","parameters":{"spm":{"value":6,"unit":"stroke/min"}},"observations":[{"type":"DYNAMOMETER_CARD","measured_at":"2025-01-04T00:00:00Z","load_unit":"lbf","points":[{"position_deg":0,"load_n":1},{"position_deg":1,"load_n":2}]}],"source":"field","provenance":PROVENANCE})

    def test_css_target_without_explicit_reservoir_sensor_context_is_excluded(self):
        cycle=self.service.create_css_cycle(self.cycle_input())
        self.ingestion.ingest_records([{"well_id":"OP-TEST-001","measured_at":"2025-01-04T00:00:00Z","variable":"temperature_c","value":100,"unit":"°C","external_id":"ambiguous-temp"}],"ambiguous-temperature")
        measurement=self.repo.query_measurements("OP-TEST-001",variable="temperature_c",limit=1)[0]
        self.service.link_measurement("css_cycle",cycle["cycle_id"],measurement["measurement_id"],"POST_SOAK_TEMPERATURE")
        dataset=ScientificCalibrationService(self.repo).build_dataset("OP-TEST-001","css_thermal",datetime(2025,1,1,tzinfo=timezone.utc),datetime(2025,2,1,tzinfo=timezone.utc))
        self.assertEqual(dataset["observation_count"],0)
        self.assertIn("temperature_target_missing_explicit_reservoir_context_or_sensor_reference",[x["reason"] for x in dataset["excluded_records"]])

    def test_events_json_dataset_and_restart_persistence(self):
        cycle=self.service.create_css_cycle(self.cycle_input())
        event=self.service.create_event({"well_id":"OP-TEST-001","cycle_id":cycle["cycle_id"],"event_type":"WORKOVER","occurred_at":"2025-02-01T00:00:00Z","external_id":"work-1","source":"operator","provenance":PROVENANCE})
        duplicate=self.service.import_records("event",[{"well_id":"OP-TEST-001","event_type":"WORKOVER","occurred_at":"2025-02-01T00:00:00Z","external_id":"work-1","source":"operator","provenance":PROVENANCE}])
        self.assertEqual(duplicate["duplicates"],1)
        dataset=self.service.build_dataset("OP-TEST-001","css_cycle",datetime(2025,1,1,tzinfo=timezone.utc),datetime(2025,3,1,tzinfo=timezone.utc))
        timeline=self.service.timeline("OP-TEST-001")
        self.assertEqual(len(timeline["entries"]),2)
        self.assertEqual(event["event_type"],"WORKOVER")
        reopened=AnalysisRepository(self.database_url); reopened.initialize()
        self.assertEqual(reopened.get_css_cycle(cycle["cycle_id"])["status"],"COMPLETE")
        self.assertEqual(reopened.get_operational_event(event["event_id"])["external_id"],"work-1")
        self.assertEqual(reopened.get_calibration_dataset(dataset["dataset_id"])["fingerprint"],dataset["fingerprint"])
        script=("import json,sys; from ml_service.persistence import AnalysisRepository; "
            "r=AnalysisRepository(sys.argv[1]); r.initialize(); "
            "print(json.dumps({'cycle':r.get_css_cycle(sys.argv[2]),'event':r.get_operational_event(sys.argv[3]),'dataset':r.get_calibration_dataset(sys.argv[4])}))")
        restarted=subprocess.run([sys.executable,"-c",script,self.database_url,cycle["cycle_id"],event["event_id"],dataset["dataset_id"]],check=True,capture_output=True,text=True)
        result=json.loads(restarted.stdout)
        self.assertEqual(result["cycle"]["cycle_id"],cycle["cycle_id"])
        self.assertEqual(result["event"]["event_id"],event["event_id"])
        self.assertEqual(result["dataset"]["fingerprint"],dataset["fingerprint"])

    def test_operational_datasets_are_chronological_grouped_and_only_use_explicit_regimes(self):
        for index in range(3):
            payload=self.cycle_input(cycle_number=index+1)
            shift=index*30
            for key in ("injection_start","injection_end","soak_start","soak_end","production_restart","post_soak_observation_start","post_soak_observation_end"):
                moment=datetime.fromisoformat(payload[key].replace("Z","+00:00"))
                payload[key]=(moment+timedelta(days=shift)).isoformat()
            if index==0: payload["metadata"]={"operating_regime_labels":["POST_WORKOVER"]}
            self.service.create_css_cycle(payload)
        chronological=self.service.build_dataset("OP-TEST-001","css_cycle",datetime(2025,1,1,tzinfo=timezone.utc),datetime(2025,6,1,tzinfo=timezone.utc),calibration_fraction=0.67)
        self.assertEqual(chronological["group_count"],3)
        splits={row["cycle_number"]:row["chronological_split"] for row in chronological["observations"]}
        self.assertEqual(splits,{1:"CALIBRATION",2:"CALIBRATION",3:"VALIDATION_UNTOUCHED"})
        gap_limited=self.service.build_dataset("OP-TEST-001","css_cycle",datetime(2025,1,1,tzinfo=timezone.utc),datetime(2025,6,1,tzinfo=timezone.utc),calibration_fraction=0.67,temporal_gap_hours=1000)
        self.assertEqual(gap_limited["validation_group_count"],0)
        self.assertTrue(any(row["chronological_split"]=="EXCLUDED_TEMPORAL_GAP_OR_INSUFFICIENT_GROUPS" for row in gap_limited["observations"]))
        regimes=self.service.build_dataset("OP-TEST-001","regime_aware",datetime(2025,1,1,tzinfo=timezone.utc),datetime(2025,6,1,tzinfo=timezone.utc),regime_label="POST_WORKOVER")
        self.assertEqual(regimes["observation_count"],1)
        self.assertEqual(regimes["operating_regime"]["labels"],["POST_WORKOVER"])

    def test_unknown_well_is_rejected_and_regime_is_not_inferred(self):
        with self.assertRaisesRegex(ValueError,"Unknown well_id"):
            self.service.create_event({"well_id":"UNKNOWN","event_type":"SHUTDOWN","occurred_at":"2025-01-01T00:00:00Z","source":"operator","provenance":PROVENANCE})
        self.assertEqual(self.service.timeline("OP-TEST-001")["operating_regime"]["status"],"UNAVAILABLE_UNLESS_EXPLICITLY_LABELED")


if __name__ == "__main__": unittest.main()
