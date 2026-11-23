"""Validated, provenance-preserving measurement ingestion."""

import csv
import io
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from ml_service.domain.contracts import MeasurementInput
from ml_service.persistence import AnalysisRepository


UNIT_ALIASES: dict[str, tuple[str, float]] = {
    "bbl/day": ("bbl/day", 1.0), "bbl/d": ("bbl/day", 1.0),
    "m3/day": ("m3/day", 1.0), "m³/day": ("m3/day", 1.0),
    "c": ("°C", 1.0), "°c": ("°C", 1.0), "bar": ("bar", 1.0),
    "metric_ton": ("metric_ton", 1.0), "tonne": ("metric_ton", 1.0),
    "day": ("day", 1.0), "days": ("day", 1.0),
    "spm": ("stroke/min", 1.0), "stroke/min": ("stroke/min", 1.0),
    "m": ("m", 1.0), "hz": ("Hz", 1.0),
    "kpa": ("bar", 0.01), "psi": ("bar", 0.0689475729), "cp": ("cP", 1.0),
}

VARIABLE_UNITS: dict[str, set[str]] = {
    "oil_rate_bpd": {"bbl/day"}, "water_rate_bpd": {"bbl/day"},
    "gas_rate_m3_day": {"m3/day"}, "temperature_c": {"°C"},
    "bottomhole_pressure_bar": {"bar"}, "wellhead_pressure_bar": {"bar"},
    "injection_pressure_bar": {"bar"}, "steam_injected_tons": {"metric_ton"},
    "days_in_production": {"day"}, "soak_days": {"day"},
    "spm": {"stroke/min"}, "stroke_length_m": {"m"},
    "vfd_frequency_hz": {"Hz"},
    "viscosity_cp": {"cP"},
}

BOUNDS: dict[str, tuple[float, float]] = {
    "oil_rate_bpd": (0, 1_000_000), "water_rate_bpd": (0, 1_000_000),
    "gas_rate_m3_day": (0, 10_000_000), "temperature_c": (-50, 500),
    "bottomhole_pressure_bar": (0, 2_000), "wellhead_pressure_bar": (0, 2_000),
    "injection_pressure_bar": (0, 2_000), "steam_injected_tons": (0, 10_000_000),
    "days_in_production": (0, 3_650), "soak_days": (0, 365),
    "spm": (0, 60), "stroke_length_m": (0, 20),
    "vfd_frequency_hz": (0, 200),
    "viscosity_cp": (0.001, 10_000_000),
}


class DataIngestionService:
    def __init__(self, repository: AnalysisRepository, max_records: int = 10_000):
        self.repository = repository
        self.max_records = max_records

    def parse_csv(self, content: str, source_id: str) -> dict[str, Any]:
        reader = csv.DictReader(io.StringIO(content))
        required = {"well_id", "measured_at", "variable", "value", "unit"}
        headers = set(reader.fieldnames or [])
        if not required.issubset(headers):
            missing = ", ".join(sorted(required - headers))
            raise ValueError(f"CSV is missing required columns: {missing}")
        if headers - (required | {"external_id", "quality_status", "metadata_json"}):
            extra = ", ".join(sorted(headers - (required | {"external_id", "quality_status", "metadata_json"})))
            raise ValueError(f"CSV has unsupported columns: {extra}")

        records: list[dict[str, Any]] = []
        parse_rejections: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if line_number > self.max_records + 1:
                raise ValueError(f"CSV exceeds the {self.max_records}-record limit")
            try:
                raw = dict(row)
                raw["value"] = float(raw["value"])
                if raw.get("metadata_json"):
                    import json
                    raw["metadata"] = json.loads(raw.pop("metadata_json"))
                    if not isinstance(raw["metadata"], dict): raise ValueError("metadata_json must decode to an object")
                else:
                    raw.pop("metadata_json", None)
                parsed = MeasurementInput.model_validate(raw)
                records.append(parsed.model_dump(mode="json"))
            except (ValidationError, ValueError, TypeError) as exc:
                parse_rejections.append({"row": str(line_number), "reason": str(exc)[:500]})

        result = self.ingest_records(records, source_id, source_type="CSV")
        self.repository.record_ingestion_rejections(source_id, parse_rejections)
        result["rejected"] = parse_rejections + result["rejected"]
        return result

    def ingest_records(self, records: list[dict[str, Any]], source_id: str,
                       source_type: str = "REST") -> dict[str, Any]:
        if not source_id.strip() or len(source_id) > 128:
            raise ValueError("source_id must contain 1 to 128 characters")
        if len(records) > self.max_records:
            raise ValueError(f"Request exceeds the {self.max_records}-record limit")

        valid: list[dict[str, Any]] = []
        rejected: list[dict[str, str]] = []
        batch_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        for index, raw in enumerate(records):
            try:
                record = MeasurementInput.model_validate(raw)
                normalized = self._normalize(record, now)
                normalized.update({
                    "source_id": source_id,
                    "source_type": source_type,
                    "provenance": {
                        "source_id": source_id,
                        "source_type": source_type,
                        "source_record_id": record.external_id,
                        "ingestion_batch_id": batch_id,
                        "original_value": record.value,
                        "original_unit": record.unit,
                        "processing_stage": "validated_ingestion",
                        "contract_version": "1",
                        "source_metadata": record.metadata,
                    },
                })
                valid.append(normalized)
            except (ValidationError, ValueError, TypeError) as exc:
                rejected.append({"row": str(index + 1), "reason": str(exc)[:500]})

        result = self.repository.ingest_measurements(valid, source_id, source_type, rejected)
        repository_rejected = result.get("rejected", [])
        return {
            "source_id": source_id,
            "ingestion_batch_id": batch_id,
            "accepted": result["inserted"],
            "duplicates": result["duplicates"],
            "rejected": rejected + repository_rejected,
            "provenance": {
                "source_id": source_id,
                "source_type": source_type,
                "processing_stage": "validated_ingestion",
                "contract_version": "1",
            },
        }

    @staticmethod
    def _normalize(record: MeasurementInput, now: datetime) -> dict[str, Any]:
        variable = record.variable.strip().lower()
        if variable not in VARIABLE_UNITS:
            raise ValueError(f"Unsupported measurement variable: {record.variable}")
        unit_key = record.unit.strip().lower()
        if unit_key not in UNIT_ALIASES:
            raise ValueError(f"Unsupported unit: {record.unit}")
        canonical_unit, factor = UNIT_ALIASES[unit_key]
        if canonical_unit not in VARIABLE_UNITS[variable]:
            raise ValueError(f"Unit {record.unit} is not valid for {variable}")
        value = record.value * factor
        if not math.isfinite(value):
            raise ValueError("Measurement value must be finite")
        lower, upper = BOUNDS[variable]
        if value < lower or value > upper:
            raise ValueError(f"{variable} must be between {lower} and {upper} {canonical_unit}")
        measured_at = record.measured_at.astimezone(timezone.utc)
        if measured_at > now + timedelta(minutes=5):
            raise ValueError("measured_at is more than five minutes in the future")
        # Historical observations can be valid calibration evidence. Operational
        # freshness is enforced by snapshot/execution services independently.
        quality = record.quality_status
        return {
            **record.model_dump(mode="json"),
            "variable": variable,
            "value": value,
            "unit": canonical_unit,
            "canonical_unit": canonical_unit,
            "measured_at": measured_at.isoformat(),
            "quality_status": quality,
        }
