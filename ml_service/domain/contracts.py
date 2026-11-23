"""Versioned boundary contracts for measured data and provenance."""

from datetime import datetime
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MeasurementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    well_id: str = Field(min_length=1, max_length=128)
    measured_at: datetime
    variable: str = Field(min_length=1, max_length=64)
    value: float
    unit: str = Field(min_length=1, max_length=32)
    external_id: str | None = Field(default=None, max_length=256)
    quality_status: Literal["VALID", "SUSPECT"] = "VALID"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("measured_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("measured_at must include a timezone")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        try: json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc: raise ValueError("metadata must contain finite JSON values") from exc
        context=value.get("measurement_context")
        if context is not None and (not isinstance(context,str) or not context.strip()): raise ValueError("measurement_context must be a non-empty label")
        depth=value.get("sensor_depth_m")
        if depth is not None and (isinstance(depth,bool) or not isinstance(depth,(int,float)) or not math.isfinite(float(depth)) or depth < 0): raise ValueError("sensor_depth_m must be a finite nonnegative value in metres")
        reference=value.get("sensor_reference")
        if reference is not None and (not isinstance(reference,str) or not reference.strip()): raise ValueError("sensor_reference must be a non-empty identifier")
        return value


class MeasurementRecord(MeasurementInput):
    measurement_id: str
    source_id: str
    source_type: str
    canonical_unit: str
    quality_status: Literal["VALID", "SUSPECT"]
    provenance: dict[str, str]


class IngestionResult(BaseModel):
    source_id: str
    accepted: int
    duplicates: int
    rejected: list[dict[str, str]]
    provenance: dict[str, str]
