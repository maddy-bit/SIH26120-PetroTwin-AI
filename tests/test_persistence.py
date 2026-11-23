import tempfile
import unittest
from pathlib import Path
import json
import subprocess
import sys

from ml_service.persistence import AnalysisRepository


class TestAnalysisRepository(unittest.TestCase):
    def test_saved_runs_round_trip_and_well_filtering(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = AnalysisRepository(f"sqlite:///{Path(directory) / 'state.sqlite3'}")
            repo.initialize()
            repo.seed_wells({"BW-TEST": {"name": "Synthetic test well", "depth_m": 900}})
            run_id = repo.save_analysis("BW-TEST", "optimization", {"result": 42})

            runs = repo.list_analyses("BW-TEST")
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], run_id)
            self.assertEqual(runs[0]["source_mode"], "SIMULATION")
            self.assertEqual(runs[0]["result"], {"result": 42})
            self.assertEqual(repo.list_analyses("OTHER"), [])

    def test_saved_run_survives_database_reopen_in_new_process(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'restart.sqlite3'}"
            repo = AnalysisRepository(database_url)
            repo.initialize()
            repo.seed_wells({"BW-RESTART": {"name": "Restart persistence test well"}})
            run_id = repo.save_analysis("BW-RESTART", "optimization", {"expected_outcome": {"production_bpd": 123}})

            script = (
                "import json,sys; from ml_service.persistence import AnalysisRepository; "
                "repo=AnalysisRepository(sys.argv[1]); repo.initialize(); "
                "print(json.dumps(repo.list_analyses('BW-RESTART')))"
            )
            result = subprocess.run(
                [sys.executable, "-c", script, database_url],
                check=True, capture_output=True, text=True,
            )
            runs = json.loads(result.stdout)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["run_id"], run_id)
            self.assertEqual(runs[0]["result"]["expected_outcome"]["production_bpd"], 123)

    def test_scientific_artifacts_and_policy_survive_repository_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'scientific.sqlite3'}"
            repo = AnalysisRepository(database_url); repo.initialize()
            repo.seed_wells({"FIELD-SCIENCE": {"name": "Scientific persistence fixture"}})
            dataset = repo.save_calibration_dataset({"well_id": "FIELD-SCIENCE", "model_id": "viscosity", "fingerprint": "abc123", "observations": [{"target": {"measurement_id": "m-1"}}]})
            calibration = repo.save_calibration("FIELD-SCIENCE", dataset["dataset_id"], {"status": "CALIBRATION_COMPLETED"}, {
                "model_id": "viscosity", "lifecycle_status": "VALIDATION_PENDING", "candidate_parameters": {"walther_a": 8.9},
            })
            candidate_id = calibration["candidate"]["candidate_id"]
            policy = repo.save_validation_policy("viscosity", {"policy_name": "test-policy", "owner": "test", "thresholds": {"mae": 10}})
            validation = repo.save_validation_run(candidate_id, dataset["dataset_id"], {"status": "VALIDATION_PASSED", "series": [{"measurement_id": "m-2"}]})

            reopened = AnalysisRepository(database_url); reopened.initialize()
            self.assertEqual(reopened.get_calibration_dataset(dataset["dataset_id"])["fingerprint"], "abc123")
            self.assertEqual(reopened.get_calibration(calibration["calibration_id"])["candidate"]["candidate_id"], candidate_id)
            self.assertEqual(reopened.get_candidate(candidate_id)["candidate_parameters"]["walther_a"], 8.9)
            self.assertEqual(reopened.get_validation_policy("viscosity")["policy_version"], policy["policy_version"])
            self.assertEqual(reopened.get_validation_run(validation["validation_id"])["status"], "VALIDATION_PASSED")
            self.assertEqual([event["state"] for event in reopened.list_candidate_events(candidate_id)], ["DRAFT", "CALIBRATION_COMPLETED", "VALIDATION_PENDING"])
            script = (
                "import json,sys; from ml_service.persistence import AnalysisRepository; "
                "repo=AnalysisRepository(sys.argv[1]); repo.initialize(); "
                "print(json.dumps({'dataset':repo.get_calibration_dataset(sys.argv[2]),"
                "'calibration':repo.get_calibration(sys.argv[3]),'validation':repo.get_validation_run(sys.argv[4])}))"
            )
            restarted = subprocess.run([sys.executable, "-c", script, database_url, dataset["dataset_id"],
                                        calibration["calibration_id"], validation["validation_id"]],
                                        check=True, capture_output=True, text=True)
            persisted = json.loads(restarted.stdout)
            self.assertEqual(persisted["dataset"]["fingerprint"], "abc123")
            self.assertEqual(persisted["calibration"]["candidate"]["candidate_id"], candidate_id)
            self.assertEqual(persisted["validation"]["series"][0]["measurement_id"], "m-2")


if __name__ == "__main__":
    unittest.main()
