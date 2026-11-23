import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ml_service.persistence import AnalysisRepository
from ml_service.services.data_ingestion import DataIngestionService
from ml_service.services.field_ml_training import FieldProductionTrainingService


class TestFieldProductionTraining(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db_path = Path(self.temp.name) / "field-training.sqlite3"
        self.repository = AnalysisRepository(f"sqlite:///{db_path}")
        self.repository.initialize()
        self.well_id = "FIELD-ML-TRAINING-TEST"
        self.repository.create_well(self.well_id, {"name": "Controlled ML training fixture"})
        self.artifact_dir = Path(self.temp.name) / "artifacts"
        self.service = FieldProductionTrainingService(self.repository, self.artifact_dir)
        self.end = datetime.now(timezone.utc)
        self.start = self.end - timedelta(days=120)
        records = []
        for index in range(240):
            measured_at = (self.start + timedelta(hours=12 * index)).isoformat()
            temperature = 180.0 - 0.5 * index
            pressure = 55.0
            spm = 5.5
            stroke = 2.4
            oil_rate = 60.0 + 1.2 * temperature + 5.0 * spm + 0.02 * pressure
            values = [
                ("temperature_c", temperature, "°C"),
                ("bottomhole_pressure_bar", pressure, "bar"),
                ("spm", spm, "stroke/min"),
                ("stroke_length_m", stroke, "m"),
                ("oil_rate_bpd", oil_rate, "bbl/day"),
            ]
            for variable, value, unit in values:
                records.append({
                    "well_id": self.well_id,
                    "measured_at": measured_at,
                    "variable": variable,
                    "value": value,
                    "unit": unit,
                    "quality_status": "VALID",
                })
        result = DataIngestionService(self.repository).ingest_records(
            records, source_id="controlled-ml-fixture", source_type="TEST_FIXTURE"
        )
        self.assertEqual(result["accepted"], len(records))
        self.assertEqual(result["rejected"], [])

    def tearDown(self):
        self.temp.cleanup()

    def train(self):
        return self.service.train(
            self.well_id,
            1,
            self.start,
            self.end,
            min_samples=30,
            max_feature_age_hours=24,
        )

    def test_measured_training_is_chronological_traceable_and_not_auto_promoted(self):
        result = self.train()
        model = result["model"]
        self.assertGreaterEqual(model["sample_count"], 30)
        self.assertEqual(model["model_family"], "field_production_ridge")
        self.assertEqual(result["field_validation"], "NOT_ESTABLISHED")
        self.assertFalse(result["automatic_promotion"])
        self.assertLessEqual(model["train_count"] + model["validation_count"] + model["test_count"], model["sample_count"])
        split = model["metrics"]["chronological_split"]
        self.assertLess(split["train_start"], split["validation_start"])
        self.assertLess(split["validation_end"], split["test_start"])
        self.assertGreaterEqual(split["purged_examples"], 0)
        self.assertTrue(split["label_boundaries_respected"])
        self.assertEqual(len(model["dataset_fingerprint"]), 64)
        self.assertTrue(Path(model["artifact_path"]).is_file())
        self.assertEqual(len(model["artifact_sha256"]), 64)

    def test_artifact_integrity_and_model_lifecycle_are_enforced(self):
        result = self.train()
        model = result["model"]
        verified = self.service.verify_artifact(model["model_id"])
        self.assertEqual(verified["model_id"], model["model_id"])
        if model["lifecycle_status"] == "CANDIDATE_REVIEW_REQUIRED":
            promoted = self.repository.promote_field_model(model["model_id"], "controlled-admin-id")
            self.assertEqual(promoted["lifecycle_status"], "ACTIVE")
            prediction = self.service.predict(self.well_id, 1)
            self.assertEqual(prediction["model_id"], model["model_id"])
            self.assertEqual(prediction["data_cohort"], "MEASURED_VALID_ONLY")
            self.assertEqual(prediction["field_validation"], "NOT_ESTABLISHED_BY_CHRONOLOGICAL_HOLDOUT_ALONE")
        else:
            with self.assertRaisesRegex(ValueError, "Only candidates"):
                self.repository.promote_field_model(model["model_id"], "controlled-admin-id")
            with self.assertRaises(LookupError):
                self.service.predict(self.well_id, 1)

        artifact = Path(model["artifact_path"])
        original = artifact.read_bytes()
        artifact.write_bytes(original + b"tampered")
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.service.verify_artifact(model["model_id"])

    def test_unavailable_or_invalid_field_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Insufficient leakage-safe measured examples"):
            self.service.train(
                self.well_id, 7, self.start, self.end,
                min_samples=2000, max_feature_age_hours=24,
            )
        with self.assertRaisesRegex(ValueError, "horizon_days"):
            self.service.train(self.well_id, 2, self.start, self.end)

    def test_registry_promotion_rejects_rejected_candidates(self):
        result = self.train()
        model_id = result["model"]["model_id"]
        stored = self.repository.get_field_model(model_id)
        self.assertIn(stored["lifecycle_status"], {"CANDIDATE_REVIEW_REQUIRED", "REJECTED_BASELINE_NOT_BEATEN"})


if __name__ == "__main__":
    unittest.main()
