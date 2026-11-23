"""Measured-data-only chronological production model training and promotion.

The trainer is deliberately separate from synthetic demo artifacts. It creates
reviewable candidates and never activates them automatically.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from bisect import bisect_left
import hashlib
import json
import math
import os
from pathlib import Path
import uuid
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_NAMES = [
    "temperature_c",
    "bottomhole_pressure_bar",
    "spm",
    "stroke_length_m",
    "current_oil_rate_bpd",
]
FEATURE_UNITS = ["°C", "bar", "stroke/min", "m", "bbl/day"]
HORIZONS = {1: 12.0, 7: 24.0, 30: 72.0}


def _aware(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("All dataset timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    residual = predicted - actual
    return {
        "mae": float(np.mean(np.abs(residual))),
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "bias": float(np.mean(residual)),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FieldProductionTrainingService:
    def __init__(self, repository, artifact_dir: str | Path):
        self.repository = repository
        self.artifact_dir = Path(artifact_dir).resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _measurement_index(rows: list[dict[str, Any]]) -> dict[str, list[tuple[datetime, dict[str, Any]]]]:
        result: dict[str, list[tuple[datetime, dict[str, Any]]]] = {}
        for row in rows:
            try:
                measured_at = _aware(row["measured_at"])
            except (ValueError, TypeError, KeyError):
                continue
            result.setdefault(row["variable"], []).append((measured_at, row))
        for values in result.values():
            values.sort(key=lambda entry: entry[0])
        return result

    @staticmethod
    def _latest_at_or_before(
        rows: list[tuple[datetime, dict[str, Any]]], at: datetime, max_age: timedelta
    ) -> dict[str, Any] | None:
        for measured_at, row in reversed(rows):
            if measured_at <= at:
                if at - measured_at <= max_age:
                    return row
                return None
        return None

    def _build_examples(
        self,
        rows: list[dict[str, Any]],
        horizon_days: int,
        max_feature_age_hours: float,
    ) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
        index = self._measurement_index([
            row for row in rows
            if row.get("quality_status") == "VALID"
            and isinstance(row.get("value"), (int, float))
            and math.isfinite(float(row["value"]))
        ])
        required = {"temperature_c", "bottomhole_pressure_bar", "spm", "stroke_length_m", "oil_rate_bpd"}
        missing = required - index.keys()
        if missing:
            raise ValueError(f"Missing VALID measured variables: {', '.join(sorted(missing))}")
        oil_rows = index["oil_rate_bpd"]
        horizon = timedelta(days=horizon_days)
        tolerance = timedelta(hours=HORIZONS[horizon_days])
        feature_age = timedelta(hours=max_feature_age_hours)
        x_values: list[list[float]] = []
        y_values: list[float] = []
        examples: list[dict[str, Any]] = []
        used_targets: set[str] = set()

        oil_times = [entry[0] for entry in oil_rows]
        expected_units = {
            "temperature_c": "°C",
            "bottomhole_pressure_bar": "bar",
            "spm": "stroke/min",
            "stroke_length_m": "m",
            "oil_rate_bpd": "bbl/day",
        }
        for origin_at, origin_oil in oil_rows:
            target_at = origin_at + horizon
            left = bisect_left(oil_times, target_at - tolerance)
            right = bisect_left(oil_times, target_at + tolerance)
            future = [(abs((oil_rows[index][0] - target_at).total_seconds()), oil_rows[index][0], oil_rows[index][1])
                      for index in range(left, min(right + 1, len(oil_rows)))
                      if oil_rows[index][0] > origin_at]
            if not future:
                continue
            _, observed_at, target = min(future, key=lambda item: item[0])
            if target["measurement_id"] in used_targets:
                continue
            temperature = self._latest_at_or_before(index["temperature_c"], origin_at, feature_age)
            pressure = self._latest_at_or_before(index["bottomhole_pressure_bar"], origin_at, feature_age)
            spm = self._latest_at_or_before(index["spm"], origin_at, feature_age)
            stroke = self._latest_at_or_before(index["stroke_length_m"], origin_at, feature_age)
            if any(item is None for item in (temperature, pressure, spm, stroke)):
                continue
            selected_measurements = {
                "temperature_c": temperature,
                "bottomhole_pressure_bar": pressure,
                "spm": spm,
                "stroke_length_m": stroke,
                "oil_rate_bpd": origin_oil,
            }
            if any(item.get("unit") != expected_units[name] for name, item in selected_measurements.items()):
                continue
            if target.get("unit") != expected_units["oil_rate_bpd"]:
                continue
            vector = [
                float(temperature["value"]), float(pressure["value"]), float(spm["value"]),
                float(stroke["value"]), float(origin_oil["value"]),
            ]
            if not all(math.isfinite(value) for value in vector) or not math.isfinite(float(target["value"])):
                continue
            x_values.append(vector)
            y_values.append(float(target["value"]))
            examples.append({
                "origin_at": origin_at.isoformat(),
                "target_at": observed_at.isoformat(),
                "origin_measurement_ids": {
                    "temperature": temperature["measurement_id"],
                    "pressure": pressure["measurement_id"],
                    "spm": spm["measurement_id"],
                    "stroke": stroke["measurement_id"],
                    "current_oil_rate": origin_oil["measurement_id"],
                },
                "target_measurement_id": target["measurement_id"],
                "source_ids": sorted({
                    temperature["source_id"], pressure["source_id"], spm["source_id"],
                    stroke["source_id"], origin_oil["source_id"], target["source_id"],
                }),
                "actual_horizon_hours": round((observed_at - origin_at).total_seconds() / 3600, 3),
            })
            used_targets.add(target["measurement_id"])

        if not x_values:
            return np.empty((0, len(FEATURE_NAMES))), np.empty((0,)), []
        return np.asarray(x_values, dtype=float), np.asarray(y_values, dtype=float), examples

    def train(
        self,
        well_id: str,
        horizon_days: int,
        start_at: str | datetime,
        end_at: str | datetime,
        *,
        min_samples: int = 30,
        max_feature_age_hours: float = 72.0,
    ) -> dict[str, Any]:
        if well_id.upper().startswith("BW-DEMO-"):
            raise ValueError("Synthetic demo wells are not eligible for field-model training")
        if horizon_days not in HORIZONS:
            raise ValueError("horizon_days must be one of 1, 7, or 30")
        start, end = _aware(start_at), _aware(end_at)
        if end <= start:
            raise ValueError("end_at must be after start_at")
        if min_samples < 30 or min_samples > 5000:
            raise ValueError("min_samples must be between 30 and 5000")
        if not math.isfinite(max_feature_age_hours) or not 1 <= max_feature_age_hours <= 720:
            raise ValueError("max_feature_age_hours must be between 1 and 720")
        # Retrieve the complete declared range in one query; quality is checked again here.
        rows = self.repository.query_measurements(
            well_id, start_at=start.isoformat(), end_at=end.isoformat(),
            quality_status="VALID", limit=10000,
        )
        X, y, examples = self._build_examples(rows, horizon_days, max_feature_age_hours)
        sample_count = len(y)
        if sample_count < min_samples:
            raise ValueError(
                f"Insufficient leakage-safe measured examples: {sample_count}; minimum required is {min_samples}. "
                "Synthetic/demo records and SUSPECT measurements are excluded."
            )

        # Chronological train/validation/test: no row-level random split.
        order = np.argsort([example["origin_at"] for example in examples])
        X, y = X[order], y[order]
        examples = [examples[int(i)] for i in order]
        n = len(y)
        train_boundary = int(n * 0.60)
        test_boundary = int(n * 0.80)
        if train_boundary >= n or test_boundary >= n:
            raise ValueError("Insufficient observations for chronological train/validation/test splits")

        # Purge labels whose target timestamps cross the next split boundary.
        # Otherwise a model could train on a future oil-rate measurement that
        # would not yet exist at the start of validation or final testing.
        validation_start = examples[train_boundary]["origin_at"]
        test_start = examples[test_boundary]["origin_at"]
        train_indices = [
            i for i in range(train_boundary)
            if examples[i]["target_at"] < validation_start
        ]
        validation_indices = [
            i for i in range(train_boundary, test_boundary)
            if examples[i]["target_at"] < test_start
        ]
        test_indices = list(range(test_boundary, n))
        if len(train_indices) < 18 or len(validation_indices) < 6 or len(test_indices) < 6:
            raise ValueError(
                "Purged chronological split requires at least 18 train, 6 validation and 6 test examples; "
                "increase the measured-data period or sampling density."
            )
        X_train, y_train = X[train_indices], y[train_indices]
        X_validation, y_validation = X[validation_indices], y[validation_indices]
        X_test, y_test = X[test_indices], y[test_indices]
        used_indices = train_indices + validation_indices + test_indices
        purged_count = n - len(used_indices)

        best: Pipeline | None = None
        best_alpha: float | None = None
        best_validation_mae = float("inf")
        for alpha in (0.01, 0.1, 1.0, 10.0, 100.0):
            candidate = Pipeline([
                ("scaler", StandardScaler()),
                ("regressor", Ridge(alpha=alpha)),
            ])
            candidate.fit(X_train, y_train)
            mae = float(np.mean(np.abs(candidate.predict(X_validation) - y_validation)))
            if mae < best_validation_mae:
                best, best_alpha, best_validation_mae = candidate, alpha, mae
        assert best is not None and best_alpha is not None
        # Refit on train + validation only after selecting alpha. The purge
        # guarantees every included validation label occurs before test start.
        pretest_indices = train_indices + validation_indices
        best.fit(X[pretest_indices], y[pretest_indices])

        predictions = best.predict(X_test)
        baseline = X_test[:, FEATURE_NAMES.index("current_oil_rate_bpd")]
        model_metrics = _metrics(y_test, predictions)
        baseline_metrics = _metrics(y_test, baseline)
        improvement = (
            (baseline_metrics["mae"] - model_metrics["mae"]) / baseline_metrics["mae"]
            if baseline_metrics["mae"] > 0 else None
        )
        promotable = improvement is not None and improvement >= 0.05 and len(y_test) >= 6
        lifecycle_status = "CANDIDATE_REVIEW_REQUIRED" if promotable else "REJECTED_BASELINE_NOT_BEATEN"

        measurement_ids = sorted({
            measurement_id
            for example in examples
            for measurement_id in (
                list(example["origin_measurement_ids"].values()) + [example["target_measurement_id"]]
            )
        })
        fingerprint_payload = {
            "well_id": well_id,
            "horizon_days": horizon_days,
            "feature_names": FEATURE_NAMES,
            "examples": examples,
            "measurement_ids": measurement_ids,
        }
        dataset_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        model_id = str(uuid.uuid4())
        trained_at = datetime.now(timezone.utc).isoformat()
        artifact_path = self.artifact_dir / f"{model_id}.joblib"
        temp_path = artifact_path.with_suffix(".joblib.tmp")
        joblib.dump({
            "model_id": model_id,
            "model_family": "field_production_ridge",
            "well_id": well_id,
            "horizon_days": horizon_days,
            "feature_names": FEATURE_NAMES,
            "feature_units": FEATURE_UNITS,
            "model": best,
            "best_alpha": best_alpha,
            "dataset_fingerprint": dataset_fingerprint,
            "trained_at": trained_at,
            "validation": {"mae": best_validation_mae, "count": len(y_validation)},
            "test_metrics": model_metrics,
            "persistence_baseline_metrics": baseline_metrics,
            "data_cohort": "MEASURED_VALID_ONLY",
        }, temp_path)
        os.replace(temp_path, artifact_path)
        artifact_sha = _sha256(artifact_path)
        model_record = self.repository.register_field_model({
            "model_id": model_id,
            "well_id": well_id,
            "model_family": "field_production_ridge",
            "horizon_days": horizon_days,
            "lifecycle_status": lifecycle_status,
            "feature_schema": [{"name": name, "unit": unit} for name, unit in zip(FEATURE_NAMES, FEATURE_UNITS)],
            "dataset_fingerprint": dataset_fingerprint,
            "sample_count": sample_count,
            "train_count": len(y_train),
            "validation_count": len(y_validation),
            "test_count": len(y_test),
            "metrics": {
                "selected_alpha": best_alpha,
                "validation_mae_bbl_day": best_validation_mae,
                "test": model_metrics,
                "persistence_baseline_test": baseline_metrics,
                "test_mae_improvement_vs_persistence": improvement,
                "promotable": promotable,
                "chronological_split": {
                    "train_start": examples[train_indices[0]]["origin_at"],
                    "train_end": examples[train_indices[-1]]["origin_at"],
                    "validation_start": examples[validation_indices[0]]["origin_at"],
                    "validation_end": examples[validation_indices[-1]]["origin_at"],
                    "test_start": examples[test_indices[0]]["origin_at"],
                    "test_end": examples[test_indices[-1]]["origin_at"],
                    "purged_examples": purged_count,
                    "label_boundaries_respected": True,
                },
                "data_quality_policy": "VALID measurements only; nearest prior feature values only; bounded feature age; future target is strictly after origin",
            },
            "artifact_path": str(artifact_path),
            "artifact_sha256": artifact_sha,
            "created_at": trained_at,
            "approved_at": None,
            "approved_by": None,
        })
        return {
            "model": model_record,
            "field_validation": "NOT_ESTABLISHED",
            "automatic_promotion": False,
            "limitations": [
                "Only the specified well and measurement period were used; no cross-well validation is claimed.",
                "A chronological holdout is not independent external field validation.",
                "The model must be reviewed and explicitly promoted by an administrator before field prediction uses it.",
                "Prediction intervals, drift monitoring, and production deployment approval are not implemented by this trainer.",
            ],
        }

    def predict(self, well_id: str, horizon_days: int) -> dict[str, Any]:
        if horizon_days not in HORIZONS:
            raise ValueError("horizon_days must be one of 1, 7, or 30")
        record = self.repository.get_active_field_model(well_id, horizon_days)
        if record is None:
            raise LookupError("No administrator-promoted field model exists for this well and horizon")
        path = Path(record["artifact_path"])
        if not path.is_file() or _sha256(path) != record["artifact_sha256"]:
            raise RuntimeError("Active model artifact is missing or failed integrity verification")
        artifact = joblib.load(path)
        if artifact.get("model_id") != record["model_id"] or artifact.get("dataset_fingerprint") != record["dataset_fingerprint"]:
            raise RuntimeError("Active model artifact metadata does not match the model registry")
        rows = self.repository.query_measurements(
            well_id,
            start_at=(datetime.now(timezone.utc) - timedelta(hours=720)).isoformat(),
            quality_status="VALID",
            limit=10000,
        )
        index = self._measurement_index(rows)
        now = datetime.now(timezone.utc)
        feature_age = timedelta(hours=72)
        latest_oil = self._latest_at_or_before(index.get("oil_rate_bpd", []), now, feature_age)
        required = {
            "temperature_c": index.get("temperature_c", []),
            "bottomhole_pressure_bar": index.get("bottomhole_pressure_bar", []),
            "spm": index.get("spm", []),
            "stroke_length_m": index.get("stroke_length_m", []),
        }
        selected = {
            name: self._latest_at_or_before(values, now, feature_age)
            for name, values in required.items()
        }
        if latest_oil is None or any(value is None for value in selected.values()):
            raise LookupError("Fresh VALID measurements for temperature, pressure, SPM, stroke and oil rate are required")
        vector = np.asarray([[
            float(selected["temperature_c"]["value"]),
            float(selected["bottomhole_pressure_bar"]["value"]),
            float(selected["spm"]["value"]),
            float(selected["stroke_length_m"]["value"]),
            float(latest_oil["value"]),
        ]], dtype=float)
        value = float(artifact["model"].predict(vector)[0])
        if not math.isfinite(value) or value < 0:
            raise RuntimeError("Active model returned a non-finite or negative production forecast")
        return {
            "well_id": well_id,
            "model_id": record["model_id"],
            "model_family": record["model_family"],
            "horizon_days": horizon_days,
            "prediction_bpd": value,
            "current_oil_rate_bpd": float(latest_oil["value"]),
            "feature_measurement_ids": {
                **{name: selected[name]["measurement_id"] for name in required},
                "current_oil_rate": latest_oil["measurement_id"],
            },
            "dataset_fingerprint": record["dataset_fingerprint"],
            "artifact_sha256": record["artifact_sha256"],
            "data_cohort": "MEASURED_VALID_ONLY",
            "field_validation": "NOT_ESTABLISHED_BY_CHRONOLOGICAL_HOLDOUT_ALONE",
            "decision_support_only": True,
        }

    def verify_artifact(self, model_id: str) -> dict[str, Any]:
        record = self.repository.get_field_model(model_id)
        if record is None:
            raise LookupError("Field model not found")
        path = Path(record["artifact_path"])
        if not path.is_file() or _sha256(path) != record["artifact_sha256"]:
            raise RuntimeError("Model artifact is missing or failed SHA-256 integrity verification")
        artifact = joblib.load(path)
        if artifact.get("model_id") != record["model_id"] or artifact.get("dataset_fingerprint") != record["dataset_fingerprint"]:
            raise RuntimeError("Model artifact metadata does not match its registry record")
        return record
