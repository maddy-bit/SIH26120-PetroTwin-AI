"""
PETRO-TWIN AI: Core API & Machine Learning Microservice
======================================================
FastAPI service exposing physics models, hybrid ML predictors, multi-objective Pareto optimizer,
real-time telemetry simulation, and WebSocket channels.
"""

import asyncio
import csv
import io
import json
import logging
import math
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import sys
import os
import secrets
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ml_service.config import config
from ml_service.persistence import AnalysisRepository
from ml_service.auth import AuthenticationError, AuthenticationService, ROLES
from ml_service.domain.contracts import MeasurementInput
from ml_service.services.data_ingestion import DataIngestionService
from ml_service.services.field_twin_state import FieldTwinStateService
from ml_service.services.physics_execution import FieldPhysicsExecutionService, normalize_configuration, validate_configuration
from ml_service.services.scientific_calibration import ScientificCalibrationService
from ml_service.services.field_ml_training import FieldProductionTrainingService
from ml_service.services.operational_data import OperationalDataService
from ml_service.simulator.telemetry_simulator import TelemetrySimulator
from ml_service.models.production_forecaster import ProductionForecaster
from ml_service.models.failure_predictor import FailurePredictor
from ml_service.models.anomaly_detector import AnomalyDetector
from ml_service.optimizer.pareto_optimizer import ParetoOptimizer
from physics.viscosity_model import ViscosityModel
from physics.thermal_model import ThermalModel
from physics.srp_model import SRPModel
from agent.agent_supervisor import AgentSupervisor
from agent.agent_runtime import AgentRuntime, AgentUnavailableError, AgentExecutionError

app = FastAPI(
    title="PETRO-TWIN AI: Well-to-Surface Digital Twin API",
    description="SIH 2026 Problem SIH26120: AI-Enabled Digital Twin for CSS + SRP Joint Optimization (Baghewala Field, Oil India Limited)",
    version=config.version,
    docs_url=None if config.auth_mode == "required" else "/docs",
    redoc_url=None if config.auth_mode == "required" else "/redoc",
    openapi_url=None if config.auth_mode == "required" else "/openapi.json"
)
logger = logging.getLogger("petrotwin.api")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
simulator = TelemetrySimulator()
repository = AnalysisRepository(config.database_url)
repository.initialize()
auth_service = AuthenticationService(
    repository, config.jwt_secret or secrets.token_urlsafe(48), config.token_ttl_minutes
)
if config.data_mode == "simulation":
    repository.seed_wells(simulator.wells_state)
simulator.wells_state = {well["well_id"]: {key: value for key, value in well.items() if key != "well_id"} for well in repository.list_wells()}
data_ingestion = DataIngestionService(repository)
field_twin_state = FieldTwinStateService(repository)
field_physics = FieldPhysicsExecutionService()
scientific_calibration = ScientificCalibrationService(repository)
field_ml_training = FieldProductionTrainingService(repository, config.field_model_artifact_dir)
operational_data = OperationalDataService(repository)
prod_forecaster = ProductionForecaster()
failure_predictor = FailurePredictor()
anomaly_detector = AnomalyDetector()
optimizer = ParetoOptimizer()
visc_model = ViscosityModel()
thermal_model = ThermalModel()
srp_model = SRPModel()
agent = AgentSupervisor()
agent.simulator = simulator
agent_runtime = AgentRuntime(
    repository,
    database_url=config.database_url,
    data_mode=config.data_mode,
    base_url=config.agent_base_url,
    api_key=config.agent_api_key,
    model=config.agent_model,
    timeout_seconds=config.agent_timeout_seconds,
    max_tool_calls=config.agent_max_tool_calls,
)


# --- Pydantic Request Models ---
class ProductionPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature_c: float = Field(default=78.0, ge=10, le=350)
    well_id: str = "BW-DEMO-001"
    pressure_bar: float = Field(default=52.0, ge=0, le=200)
    spm: float = Field(default=6.5, ge=2, le=10.5)
    stroke_length_m: float = Field(default=2.4, ge=1.5, le=3)
    days_since_injection: int = Field(default=50, ge=0, le=365)
    recent_oil_rate_bpd: float = Field(default=95.0, ge=0, le=100000)


class FailurePredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stroke_length_m: float = Field(default=2.4, ge=1.5, le=3)
    well_id: str = "BW-DEMO-001"
    spm: float = Field(default=7.0, ge=2, le=10.5)
    temperature_c: float = Field(default=70.0, ge=10, le=350)
    pressure_bar: float = Field(default=52.0, ge=0, le=200)
    days_in_production: int = Field(default=60, ge=0, le=365)


class AnomalyDetectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature_c: float = Field(default=75.0, ge=0, le=500)
    pressure_bar: float = Field(default=50.0, ge=0, le=300)
    pprl_lbs: float = Field(default=14500.0, ge=0, le=100000)
    mprl_lbs: float = Field(default=3200.0, ge=0, le=100000)
    oil_rate_bpd: float = Field(default=90.0, ge=0, le=100000)
    motor_power_kw: float = Field(default=18.0, ge=0, le=10000)


class ViscosityPredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature_c: float = Field(default=47.0, ge=10, le=350)
    pressure_bar: float = Field(default=55.0, ge=0, le=200)


class TemperaturePredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    peak_temperature_c: float = Field(default=195.0, ge=47, le=280)
    day: int = Field(default=45, ge=0, le=365)


class CSSSimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steam_mass_tons: float = Field(default=2400.0, ge=500, le=5000)
    soak_days: float = Field(default=6.0, ge=2, le=15)


class SRPSimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stroke_length_m: float = Field(default=2.4, ge=1.5, le=3)
    spm: float = Field(default=6.5, ge=2, le=10.5)
    avg_viscosity_cp: float = Field(default=250.0, ge=1, le=100000)


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steam_volume: float = Field(default=2400.0, ge=500, le=5000)
    well_id: str = "BW-DEMO-001"
    soak_time: float = Field(default=6.0, ge=2, le=15)
    production_cutoff: float = Field(default=115.0, ge=1, le=365)
    days_in_cycle: int | None = Field(default=None, ge=0, le=365)
    stroke_length: float = Field(default=2.4, ge=1.5, le=3)
    spm: float = Field(default=6.5, ge=2, le=10.5)


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    well_id: str = "BW-DEMO-001"
    weight_production: float = Field(default=0.40, ge=0, le=1)
    weight_sor: float = Field(default=0.25, ge=0, le=1)
    weight_energy: float = Field(default=0.15, ge=0, le=1)
    weight_risk: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def require_positive_objective_weight(self):
        if self.weight_production + self.weight_sor + self.weight_energy + self.weight_risk <= 0:
            raise ValueError("At least one objective weight must be positive")
        return self


class CopilotQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    well_id: str = "BW-DEMO-001"


class MeasurementBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1, max_length=128)
    records: List[MeasurementInput] = Field(min_length=1, max_length=10000)


class WellCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    well_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=256)
    depth_m: float | None = Field(default=None, gt=0, le=20000)
    pump_depth_m: float | None = Field(default=None, gt=0, le=20000)
    status: str = Field(default="CONFIGURED", min_length=1, max_length=64)


class PhysicalParameterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float
    unit: str = Field(min_length=1, max_length=32)
    source: str = Field(min_length=1, max_length=128)
    classification: str = Field(pattern="^(MEASURED|OPERATOR_CONFIGURED|DERIVED|ASSUMED)$")
    validation_status: str = Field(default="UNVALIDATED", pattern="^(UNVALIDATED|REVIEWED|VALIDATED)$")


class PhysicalConfigurationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameters: dict[str, PhysicalParameterRequest]


class PhysicsExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot_id: str = Field(min_length=1, max_length=64)
    configuration_version: int | None = Field(default=None, ge=1)


class CalibrationDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(pattern="^(viscosity|css_thermal|srp)$")
    start_at: datetime
    end_at: datetime
    tolerance_minutes: int = Field(default=15, ge=0, le=1440)
    dataset_role: str = Field(default="CALIBRATION", pattern="^(CALIBRATION|VALIDATION)$")

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value


class OperationalImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(pattern="^1\\.0$")
    record_type: str = Field(pattern="^(css_cycle|event|srp_record)$")
    records: List[dict[str, Any]] = Field(min_length=1, max_length=1000)


class MeasurementLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: str = Field(pattern="^(css_cycle|operational_event|srp_record)$")
    entity_id: str = Field(min_length=1, max_length=128)
    measurement_id: str = Field(min_length=1, max_length=128)
    relation: str = Field(min_length=1, max_length=80)


class OperationalDatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_type: str = Field(pattern="^(css_cycle|srp|css_srp_joint|event_aligned|regime_aware)$")
    start_at: datetime
    end_at: datetime
    cycle_id: str | None = Field(default=None, max_length=128)
    calibration_fraction: float = Field(default=0.8, ge=0.5, lt=1)
    regime_label: str | None = Field(default=None, max_length=128)
    temporal_gap_hours: float = Field(default=0, ge=0, le=8760)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None: raise ValueError("timestamps must include a timezone")
        return value


class CalibrationExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=64)
    selected_parameters: List[str] = Field(min_length=1)
    parameter_bounds: dict[str, dict[str, Any]]


class IdentifiabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parameter_names: List[str] | None = None


class TemporalValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_at: datetime
    end_at: datetime
    tolerance_minutes: int = Field(default=15, ge=0, le=1440)
    temporal_gap_hours: float = Field(default=0, ge=0, le=8760)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value


class ValidationPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_name: str = Field(min_length=1, max_length=128)
    owner: str = Field(min_length=1, max_length=128)
    minimum_validation_observations: int = Field(ge=1, le=1000000)
    thresholds: dict[str, float]


class CandidateRejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class AgentInvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    well_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=2000)
    days: int = Field(default=30, ge=1, le=3650)


class FieldModelTrainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    well_id: str = Field(min_length=1, max_length=128)
    horizon_days: int = Field(default=7, ge=1, le=30)
    start_at: datetime
    end_at: datetime
    min_samples: int = Field(default=30, ge=30, le=5000)
    max_feature_age_hours: float = Field(default=72.0, ge=1, le=720)

    @field_validator("horizon_days")
    @classmethod
    def supported_horizon(cls, value: int) -> int:
        if value not in {1, 7, 30}:
            raise ValueError("horizon_days must be one of 1, 7, or 30")
        return value

    @model_validator(mode="after")
    def aware_range(self):
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("start_at and end_at must include timezone offsets")
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class FieldModelPromoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acknowledgement: str = Field(min_length=1, max_length=500)


class UserCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern="^(viewer|engineer|operator|admin)$")


class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str | None = Field(default=None, pattern="^(viewer|engineer|operator|admin)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)

    @model_validator(mode="after")
    def require_at_least_one_update(self):
        if self.role is None and self.is_active is None and self.password is None:
            raise ValueError("At least one user field must be updated")
        return self


def require_known_well(well_id: str) -> None:
    well = repository.get_well(well_id)
    if well is None:
        raise HTTPException(status_code=404, detail=f"Unknown well_id: {well_id}")
    if config.data_mode != "simulation" and is_simulation_profile(well):
        raise HTTPException(status_code=404, detail=f"{well_id} is a synthetic development profile and is unavailable in field mode")


def is_simulation_profile(well: dict[str, Any]) -> bool:
    well_id = str(well.get("well_id", "")).upper()
    name = str(well.get("name", "")).lower()
    return well_id.startswith("BW-DEMO-") or "demo well" in name


def require_simulation(feature: str) -> None:
    if config.data_mode != "simulation":
        raise HTTPException(
            status_code=503,
            detail=f"{feature} is unavailable in field mode until required measured data or a field-validated model is configured.",
        )


def require_simulated_well(well_id: str, feature: str) -> None:
    require_simulation(feature)
    if well_id not in simulator.wells_state:
        raise HTTPException(
            status_code=503,
            detail=f"{feature} is unavailable for {well_id}: no simulation profile is configured for this well.",
        )


def require_admin_user_management(request: Request) -> None:
    if config.auth_mode != "required":
        raise HTTPException(
            status_code=503,
            detail="User-management API requires PETROTWIN_AUTH_MODE=required; use scripts/manage_users.py in local development.",
        )
    user = getattr(request.state, "auth_user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")


def _is_protected_path(path: str) -> bool:
    return path.startswith((
        "/api/", "/predict/", "/detect/", "/simulate/", "/optimize",
        "/agent/", "/models", "/ws/",
    ))


def _allowed_roles_for_request(path: str, method: str) -> set[str]:
    if path.startswith(("/api/v1/auth/users", "/api/v1/auth/audit-events")):
        return {"admin"}
    if method in {"GET", "HEAD", "OPTIONS"} or path == "/api/v1/auth/logout":
        return set(ROLES)
    if path.endswith(("/approve", "/reject")) or path.endswith("/validation-policy"):
        return {"admin"}
    operator_paths = (
        "/api/v1/measurements", "/api/v1/operational-data",
        "/api/v1/operational-measurement-links",
    )
    if path == "/api/v1/wells" or path.startswith(operator_paths):
        return {"operator", "admin"}
    if any(segment in path for segment in (
        "/css-cycles", "/operational-events", "/srp-records",
    )):
        return {"operator", "admin"}
    return {"engineer", "admin"}


def _security_denial_response(
    request: Request,
    status_code: int,
    detail: str,
    reason: str,
    *,
    user_id: str | None = None,
    correlation_id: str,
) -> JSONResponse:
    ip_address = request.client.host if request.client else None
    try:
        repository.write_auth_audit_event({
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": "http_access_denied",
            "resource": request.url.path,
            "outcome": "denied",
            "ip_address": ip_address,
            "correlation_id": correlation_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": {"method": request.method, "reason": reason},
        })
    except Exception:
        logger.exception("Failed to persist an HTTP access-denial audit event")
    logger.warning(json.dumps({
        "event": "http_access_denied", "method": request.method,
        "path": request.url.path, "status_code": status_code,
        "reason": reason, "correlation_id": correlation_id,
    }))
    headers = {"X-Correlation-ID": correlation_id}
    if status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers)


@app.middleware("http")
async def request_observability(request: Request, call_next):
    supplied = request.headers.get("X-Correlation-ID", "")
    try:
        correlation_id = str(uuid.UUID(supplied)) if supplied else str(uuid.uuid4())
    except (ValueError, AttributeError):
        correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    request.state.auth_user = None
    path = request.url.path
    if config.auth_mode == "required" and _is_protected_path(path) and request.method != "OPTIONS":
        if path != "/api/v1/auth/login":
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return _security_denial_response(
                    request, 401, "Authentication required", "missing_bearer_token",
                    correlation_id=correlation_id,
                )
            try:
                authenticated_user = auth_service.authenticate(token)
            except AuthenticationError:
                return _security_denial_response(
                    request, 401, "Invalid or expired credentials", "invalid_or_expired_token",
                    correlation_id=correlation_id,
                )
            if authenticated_user["role"] not in _allowed_roles_for_request(path, request.method):
                return _security_denial_response(
                    request, 403, "Your role is not permitted to perform this action",
                    "role_not_permitted", user_id=authenticated_user["user_id"],
                    correlation_id=correlation_id,
                )
            request.state.auth_user = authenticated_user
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(json.dumps({
            "event": "http_request_failed", "method": request.method,
            "path": request.url.path, "correlation_id": correlation_id,
        }))
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(json.dumps({
        "event": "http_request", "method": request.method, "path": request.url.path,
        "status_code": response.status_code, "duration_ms": duration_ms,
        "correlation_id": correlation_id,
    }))
    return response


# --- REST Endpoints ---

v1_router = APIRouter(prefix="/api/v1")


@v1_router.post("/wells", tags=["Wells"])
def create_well(req: WellCreateRequest):
    if repository.get_well(req.well_id):
        raise HTTPException(status_code=409, detail=f"Well {req.well_id} already exists")
    configuration = req.model_dump(exclude={"well_id"})
    repository.create_well(req.well_id, configuration)
    return {"well": {"well_id": req.well_id, **configuration}}


@v1_router.post("/measurements", tags=["Data Ingestion"])
def ingest_measurement_batch(req: MeasurementBatchRequest):
    result = data_ingestion.ingest_records(
        [record.model_dump(mode="json") for record in req.records], req.source_id, "REST"
    )
    return result


@v1_router.post("/measurements/csv", tags=["Data Ingestion"])
async def ingest_measurement_csv(request: Request, source_id: str = Query(min_length=1, max_length=128)):
    if not request.headers.get("content-type", "").lower().startswith("text/csv"):
        raise HTTPException(status_code=415, detail="Send CSV data with Content-Type: text/csv")
    content = await request.body()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413 if content else 400, detail="CSV body must be 1 byte to 10 MiB")
    try:
        decoded = content.decode("utf-8-sig")
        return data_ingestion.parse_csv(decoded, source_id)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@v1_router.get("/data-sources", tags=["Data Ingestion"])
def get_data_sources():
    return {"sources": repository.list_data_sources()}


@v1_router.get("/wells/{well_id}/measurements", tags=["Data Ingestion"])
def get_measurements(well_id: str, days: int = Query(90, ge=1, le=3650),
                     variable: str | None = Query(default=None, max_length=64),
                     quality_status: str | None = Query(default=None, pattern="^(VALID|SUSPECT)$")):
    require_known_well(well_id)
    start_at = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return {"well_id": well_id, "records": repository.query_measurements(
        well_id, variable=variable, start_at=start_at, quality_status=quality_status)}


@v1_router.get("/wells/{well_id}/data-quality", tags=["Data Ingestion"])
def get_data_quality(well_id: str, window_days: int = Query(30, ge=1, le=3650)):
    require_known_well(well_id)
    records = repository.query_measurements(well_id, start_at=(datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat(), limit=10000)
    counts: dict[str, int] = {}
    for row in records:
        counts[row["variable"]] = counts.get(row["variable"], 0) + 1
    latest = repository.query_measurements(well_id, limit=10000)
    latest_by_type: dict[str, dict[str, Any]] = {}
    for row in latest:
        latest_by_type.setdefault(row["variable"], row)
    now = datetime.now(timezone.utc)
    stale = sorted(name for name, row in latest_by_type.items()
                   if now - datetime.fromisoformat(row["measured_at"].replace("Z", "+00:00")) > timedelta(hours=24))
    return {"well_id": well_id, "window_days": window_days, "measurement_counts": counts,
            "record_count": len(records), "time_coverage": {"start": min((r["measured_at"] for r in records), default=None),
            "end": max((r["measured_at"] for r in records), default=None)},
            "stale_measurement_types": stale,
            "suspect_count": sum(r["quality_status"] != "VALID" for r in records),
            "readiness": "MEASUREMENTS_RECORDED_NOT_FIELD_MODEL_READY" if records else "NO_MEASUREMENTS"}


def operational_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if "Unknown well_id" in message or "not found" in message.lower(): return HTTPException(status_code=404, detail=message)
    if "unique constraint" in message.lower() or "duplicate key" in message.lower(): return HTTPException(status_code=409, detail="Duplicate operational record or linkage")
    return HTTPException(status_code=422, detail=message)


@v1_router.post("/wells/{well_id}/css-cycles", tags=["Operational Data"])
def create_css_cycle(well_id: str, payload: dict[str, Any]):
    require_known_well(well_id)
    if payload.get("well_id") not in (None, well_id): raise HTTPException(status_code=422, detail="well_id in payload must match path")
    try: return operational_data.create_css_cycle({**payload, "well_id": well_id})
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.get("/wells/{well_id}/css-cycles", tags=["Operational Data"])
def list_css_cycles(well_id: str):
    require_known_well(well_id); return {"well_id": well_id, "cycles": repository.list_css_cycles(well_id)}


@v1_router.get("/css-cycles/{cycle_id}", tags=["Operational Data"])
def get_css_cycle(cycle_id: str):
    cycle=repository.get_css_cycle(cycle_id)
    if cycle is None: raise HTTPException(status_code=404, detail="CSS cycle not found")
    return cycle


@v1_router.put("/css-cycles/{cycle_id}", tags=["Operational Data"])
def put_css_cycle(cycle_id: str, payload: dict[str, Any]):
    current=repository.get_css_cycle(cycle_id)
    if current is None: raise HTTPException(status_code=404, detail="CSS cycle not found")
    try:
        if payload.get("well_id",current["well_id"]) != current["well_id"]: raise ValueError("CSS cycle well_id cannot be changed")
        return operational_data.update_css_cycle(cycle_id,{**payload,"well_id":current["well_id"]})
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.delete("/css-cycles/{cycle_id}", tags=["Operational Data"])
def archive_css_cycle(cycle_id: str):
    result=repository.archive_operational_record("css_cycle",cycle_id)
    if result is None: raise HTTPException(status_code=404, detail="CSS cycle not found")
    return {"status":"ARCHIVED","cycle_id":cycle_id,"archived_at":result["archived_at"]}


@v1_router.post("/wells/{well_id}/operational-events", tags=["Operational Data"])
def create_operational_event(well_id: str, payload: dict[str, Any]):
    require_known_well(well_id)
    if payload.get("well_id") not in (None,well_id): raise HTTPException(status_code=422,detail="well_id in payload must match path")
    try: return operational_data.create_event({**payload,"well_id":well_id})
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.get("/wells/{well_id}/operational-events", tags=["Operational Data"])
def list_operational_events(well_id: str, start_at: datetime | None = None, end_at: datetime | None = None):
    require_known_well(well_id)
    if (start_at and (start_at.tzinfo is None or start_at.utcoffset() is None)) or (end_at and (end_at.tzinfo is None or end_at.utcoffset() is None)): raise HTTPException(status_code=422,detail="time filters must include a timezone")
    start_utc=start_at.astimezone(timezone.utc).isoformat() if start_at else None; end_utc=end_at.astimezone(timezone.utc).isoformat() if end_at else None
    if start_utc and end_utc and end_utc<start_utc: raise HTTPException(status_code=422,detail="end_at must not precede start_at")
    return {"well_id":well_id,"events":repository.list_operational_events(well_id,start_utc,end_utc)}


@v1_router.get("/operational-events/{event_id}", tags=["Operational Data"])
def get_operational_event(event_id: str):
    event=repository.get_operational_event(event_id)
    if event is None: raise HTTPException(status_code=404,detail="Operational event not found")
    return event


@v1_router.put("/operational-events/{event_id}", tags=["Operational Data"])
def put_operational_event(event_id: str,payload: dict[str,Any]):
    current=repository.get_operational_event(event_id)
    if current is None: raise HTTPException(status_code=404,detail="Operational event not found")
    try: return repository.update_operational_event(event_id,operational_data.validate_event({**payload,"well_id":current["well_id"]}))
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.delete("/operational-events/{event_id}",tags=["Operational Data"])
def archive_operational_event(event_id: str):
    result=repository.archive_operational_record("operational_event",event_id)
    if result is None: raise HTTPException(status_code=404,detail="Operational event not found")
    return {"status":"ARCHIVED","event_id":event_id,"archived_at":result["archived_at"]}


@v1_router.post("/wells/{well_id}/srp-records",tags=["Operational Data"])
def create_srp_record(well_id: str,payload: dict[str,Any]):
    require_known_well(well_id)
    if payload.get("well_id") not in (None,well_id): raise HTTPException(status_code=422,detail="well_id in payload must match path")
    try: return operational_data.create_srp_record({**payload,"well_id":well_id})
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.get("/wells/{well_id}/srp-records",tags=["Operational Data"])
def list_srp_records(well_id: str,start_at: datetime | None = None,end_at: datetime | None = None):
    require_known_well(well_id)
    if (start_at and (start_at.tzinfo is None or start_at.utcoffset() is None)) or (end_at and (end_at.tzinfo is None or end_at.utcoffset() is None)): raise HTTPException(status_code=422,detail="time filters must include a timezone")
    start_utc=start_at.astimezone(timezone.utc).isoformat() if start_at else None; end_utc=end_at.astimezone(timezone.utc).isoformat() if end_at else None
    if start_utc and end_utc and end_utc<start_utc: raise HTTPException(status_code=422,detail="end_at must not precede start_at")
    return {"well_id":well_id,"records":repository.list_srp_records(well_id,start_utc,end_utc)}


@v1_router.get("/srp-records/{record_id}",tags=["Operational Data"])
def get_srp_record(record_id: str):
    record=repository.get_srp_record(record_id)
    if record is None: raise HTTPException(status_code=404,detail="SRP operational record not found")
    return record


@v1_router.put("/srp-records/{record_id}",tags=["Operational Data"])
def put_srp_record(record_id: str,payload: dict[str,Any]):
    current=repository.get_srp_record(record_id)
    if current is None: raise HTTPException(status_code=404,detail="SRP operational record not found")
    try: return repository.update_srp_record(record_id,operational_data.validate_srp_record({**payload,"well_id":current["well_id"]}))
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.delete("/srp-records/{record_id}",tags=["Operational Data"])
def archive_srp_record(record_id: str):
    result=repository.archive_operational_record("srp_record",record_id)
    if result is None: raise HTTPException(status_code=404,detail="SRP record not found")
    return {"status":"ARCHIVED","record_id":record_id,"archived_at":result["archived_at"]}


@v1_router.post("/operational-data/import/json",tags=["Operational Data"])
def import_operational_json(req: OperationalImportRequest):
    try: return operational_data.import_records(req.record_type,req.records)
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.post("/operational-data/import/csv",tags=["Operational Data"])
async def import_operational_csv(request: Request,record_type: str = Query(pattern="^(css_cycle|event|srp_record)$")):
    if not request.headers.get("content-type","").lower().startswith("text/csv"): raise HTTPException(status_code=415,detail="Send CSV data with Content-Type: text/csv")
    content=await request.body()
    if not content or len(content)>10*1024*1024: raise HTTPException(status_code=413 if content else 400,detail="CSV body must be 1 byte to 10 MiB")
    try:
        text=content.decode("utf-8-sig"); reader=csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or set(reader.fieldnames)!={"schema_version","record_json"}: raise ValueError("CSV columns must be exactly schema_version,record_json")
        rows=[]
        for row in reader:
            if row["schema_version"]!="1.0": raise ValueError("Each CSV row must declare schema_version 1.0")
            value=json.loads(row["record_json"])
            if not isinstance(value,dict): raise ValueError("record_json must decode to an object")
            rows.append(value)
        if not rows: raise ValueError("CSV must contain at least one operational record")
        return operational_data.import_records(record_type,rows)
    except (UnicodeDecodeError,ValueError,json.JSONDecodeError) as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc


@v1_router.post("/operational-measurement-links",tags=["Operational Data"])
def link_operational_measurement(req: MeasurementLinkRequest):
    try: return operational_data.link_measurement(req.entity_type,req.entity_id,req.measurement_id,req.relation)
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.get("/wells/{well_id}/operational-timeline",tags=["Operational Data"])
def get_operational_timeline(well_id: str,start_at: datetime | None=None,end_at: datetime | None=None):
    try: return operational_data.timeline(well_id,start_at.isoformat() if start_at else None,end_at.isoformat() if end_at else None)
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.get("/wells/{well_id}/operational-calibration-readiness",tags=["Operational Data"])
def get_operational_calibration_readiness(well_id: str):
    try: return operational_data.calibration_readiness(well_id)
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.post("/wells/{well_id}/operational-datasets",tags=["Operational Data"])
def create_operational_dataset(well_id: str,req: OperationalDatasetRequest):
    try: return operational_data.build_dataset(well_id,req.dataset_type,req.start_at,req.end_at,req.cycle_id,req.calibration_fraction,req.regime_label,req.temporal_gap_hours)
    except Exception as exc: raise operational_error(exc) from exc


@v1_router.post("/wells/{well_id}/twin-state", tags=["Digital Twin"])
def construct_field_twin_state(well_id: str, window_hours: int = Query(168, ge=1, le=8760)):
    require_known_well(well_id)
    return field_twin_state.build_snapshot(well_id, window_hours)


@v1_router.put("/wells/{well_id}/physical-configuration", tags=["Digital Twin"])
def save_physical_configuration(well_id: str, req: PhysicalConfigurationRequest):
    require_known_well(well_id)
    parameters = normalize_configuration(req.model_dump(mode="json")["parameters"])
    invalid = validate_configuration(parameters)
    if invalid: raise HTTPException(status_code=422, detail=invalid)
    config = repository.save_physical_configuration(well_id, {"parameters": parameters})
    return {**config, "model_configuration_completeness": field_physics.eligibility({}, config)}


@v1_router.get("/wells/{well_id}/physical-configuration", tags=["Digital Twin"])
def get_physical_configuration(well_id: str):
    require_known_well(well_id)
    configuration = repository.get_physical_configuration(well_id)
    if configuration is None: return {"well_id": well_id, "configuration": None, "status": "NOT_CONFIGURED"}
    return {"configuration": configuration, "model_eligibility": field_physics.eligibility({}, configuration)}


@v1_router.get("/wells/{well_id}/physics-eligibility", tags=["Digital Twin"])
def get_physics_eligibility(well_id: str, snapshot_id: str = Query(min_length=1, max_length=64)):
    require_known_well(well_id)
    snapshot = repository.get_twin_snapshot(snapshot_id)
    if snapshot is None: raise HTTPException(status_code=404, detail="Snapshot not found")
    if snapshot["well_id"] != well_id: raise HTTPException(status_code=409, detail="Snapshot belongs to a different well")
    return {"well_id": well_id, "snapshot_id": snapshot_id,
            "configuration": repository.get_physical_configuration(well_id),
            "models": field_physics.eligibility(snapshot, repository.get_physical_configuration(well_id))}


@v1_router.post("/wells/{well_id}/physics-runs", tags=["Digital Twin"])
def execute_field_physics(well_id: str, req: PhysicsExecutionRequest):
    require_known_well(well_id)
    snapshot = repository.get_twin_snapshot(req.snapshot_id)
    if snapshot is None: raise HTTPException(status_code=404, detail="Snapshot not found")
    if snapshot["well_id"] != well_id: raise HTTPException(status_code=409, detail="Snapshot belongs to a different well")
    configuration = repository.get_physical_configuration(well_id)
    if req.configuration_version is not None and (configuration is None or configuration["config_version"] != req.configuration_version):
        raise HTTPException(status_code=409, detail="Requested physical configuration version is not the current well configuration")
    result = field_physics.execute(snapshot, configuration)
    run = repository.save_physics_run(well_id, req.snapshot_id, configuration["configuration_id"] if configuration else None, result)
    return run


@v1_router.get("/physics-runs/{run_id}", tags=["Digital Twin"])
def get_physics_run(run_id: str):
    run = repository.get_physics_run(run_id)
    if run is None: raise HTTPException(status_code=404, detail="Physics run not found")
    return run


@v1_router.get("/wells/{well_id}/physics-runs", tags=["Digital Twin"])
def list_physics_runs(well_id: str, limit: int = Query(50, ge=1, le=200)):
    require_known_well(well_id)
    return {"runs": repository.list_physics_runs(well_id, limit)}


@v1_router.get("/wells/{well_id}/calibration-eligibility", tags=["Digital Twin"])
def get_calibration_eligibility(well_id: str, days: int = Query(365, ge=1, le=3650)):
    require_known_well(well_id)
    start_at = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    records = repository.query_measurements(well_id, start_at=start_at, limit=10000)
    return field_physics.calibration_eligibility(well_id, records)


@v1_router.post("/wells/{well_id}/calibration-datasets", tags=["Scientific Calibration"])
def create_calibration_dataset(well_id: str, req: CalibrationDatasetRequest):
    require_known_well(well_id)
    if req.end_at <= req.start_at: raise HTTPException(status_code=422, detail="end_at must be after start_at")
    try:
        return scientific_calibration.build_dataset(well_id, req.model_id, req.start_at, req.end_at,
                                                    req.tolerance_minutes, req.dataset_role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@v1_router.get("/calibration-datasets/{dataset_id}", tags=["Scientific Calibration"])
def get_calibration_dataset(dataset_id: str):
    dataset = repository.get_calibration_dataset(dataset_id)
    if dataset is None: raise HTTPException(status_code=404, detail="Calibration dataset not found")
    return dataset


@v1_router.post("/calibration-datasets/{dataset_id}/identifiability", tags=["Scientific Calibration"])
def assess_parameter_identifiability(dataset_id: str, req: IdentifiabilityRequest | None = None):
    dataset = repository.get_calibration_dataset(dataset_id)
    if dataset is None: raise HTTPException(status_code=404, detail="Calibration dataset not found")
    configuration_ref = dataset.get("physical_configuration_reference")
    configuration = repository.get_physical_configuration_by_id(configuration_ref["configuration_id"]) if configuration_ref else None
    if dataset["model_id"] == "viscosity" and configuration is None:
        return {"dataset_id": dataset_id, "model_id": "viscosity", "status": "INSUFFICIENT_DATA", "parameters": {}, "reason": "A persisted source physical configuration is required for sensitivity analysis."}
    assessment = scientific_calibration.assess_identifiability(dataset, configuration or {}, req.parameter_names if req else None)
    return assessment


@v1_router.post("/wells/{well_id}/calibrations", tags=["Scientific Calibration"])
def execute_calibration(well_id: str, req: CalibrationExecutionRequest):
    require_known_well(well_id)
    dataset = repository.get_calibration_dataset(req.dataset_id)
    if dataset is None: raise HTTPException(status_code=404, detail="Calibration dataset not found")
    if dataset["well_id"] != well_id: raise HTTPException(status_code=409, detail="Dataset belongs to another well")
    if dataset["dataset_role"] != "CALIBRATION": raise HTTPException(status_code=409, detail="Only a calibration-role dataset may fit parameters")
    configuration_ref = dataset.get("physical_configuration_reference")
    configuration = repository.get_physical_configuration_by_id(configuration_ref["configuration_id"]) if configuration_ref else None
    if configuration is None: raise HTTPException(status_code=409, detail="Dataset has no persisted source configuration")
    try:
        result = scientific_calibration.calibrate(dataset, configuration, req.selected_parameters, req.parameter_bounds)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    candidate = None
    if result["status"] == "CALIBRATION_COMPLETED":
        candidate = {"model_id": result["model_id"], "model_version": result["model_version"],
                     "dataset_id": result["dataset_id"], "dataset_fingerprint": result["dataset_fingerprint"],
                     "original_configuration_id": result["original_configuration_id"],
                     "original_configuration_version": result["original_configuration_version"],
                     "original_configuration_parameters": result["original_configuration_parameters"],
                     "candidate_parameters": result["candidate_parameters"],
                     "candidate_configuration_parameters": result["candidate_configuration_parameters"],
                     "identifiability": result["identifiability"], "lifecycle_status": "VALIDATION_PENDING",
                     "validation_status": "PENDING", "approval_status": "NOT_REQUESTED",
                     "activation_enabled": False, "activation_block_reason": "No authentication/RBAC approval system is implemented."}
    return repository.save_calibration(well_id, req.dataset_id, result, candidate)


@v1_router.get("/calibrations/{calibration_id}", tags=["Scientific Calibration"])
def get_calibration_result(calibration_id: str):
    result = repository.get_calibration(calibration_id)
    if result is None: raise HTTPException(status_code=404, detail="Calibration run not found")
    return result


@v1_router.put("/models/{model_id}/validation-policy", tags=["Scientific Calibration"])
def set_validation_policy(model_id: str, req: ValidationPolicyRequest):
    if model_id != "viscosity": raise HTTPException(status_code=422, detail="Validation policy currently supports viscosity only")
    allowed = {"mae", "rmse", "max_abs_bias", "mean_absolute_relative_error"}
    if not req.thresholds or set(req.thresholds) - allowed: raise HTTPException(status_code=422, detail=f"thresholds must contain supported metrics: {sorted(allowed)}")
    if any(not math.isfinite(value) or value < 0 for value in req.thresholds.values()): raise HTTPException(status_code=422, detail="Thresholds must be finite and non-negative")
    return repository.save_validation_policy(model_id, req.model_dump(mode="json"))


@v1_router.get("/models/{model_id}/validation-policy", tags=["Scientific Calibration"])
def get_validation_policy(model_id: str):
    policy = repository.get_validation_policy(model_id)
    if policy is None: return {"model_id": model_id, "status": "NOT_CONFIGURED"}
    return policy


@v1_router.post("/calibration-candidates/{candidate_id}/validate", tags=["Scientific Calibration"])
def validate_calibration_candidate(candidate_id: str, req: TemporalValidationRequest):
    if req.end_at <= req.start_at: raise HTTPException(status_code=422, detail="end_at must be after start_at")
    candidate = repository.get_candidate(candidate_id)
    if candidate is None: raise HTTPException(status_code=404, detail="Calibration candidate not found")
    if candidate["lifecycle_status"] != "VALIDATION_PENDING": raise HTTPException(status_code=409, detail="Candidate is not pending validation")
    calibration = repository.get_calibration(candidate["calibration_id"])
    try:
        dataset = scientific_calibration.build_dataset(candidate["well_id"], candidate["model_id"], req.start_at, req.end_at,
                                                       req.tolerance_minutes, "VALIDATION")
        result = scientific_calibration.validate_candidate(candidate, calibration, dataset, req.temporal_gap_hours)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    persisted = repository.save_validation_run(candidate_id, dataset["dataset_id"], result)
    if result["status"] == "VALIDATION_PASSED":
        candidate["validation_status"] = "VALIDATION_PASSED"
        candidate["lifecycle_status"] = "APPROVAL_PENDING"
        candidate["approval_status"] = "APPROVAL_PENDING"
        candidate.setdefault("lifecycle_history", []).append({"state": "VALIDATION_PASSED", "validation_id": persisted["validation_id"], "timestamp": persisted["created_at"]})
    elif result["status"] == "VALIDATION_FAILED":
        candidate["validation_status"] = "VALIDATION_FAILED"
        candidate["lifecycle_status"] = "VALIDATION_FAILED"
    else:
        candidate["validation_status"] = result["status"]
    candidate.setdefault("lifecycle_history", []).append({"state": candidate["lifecycle_status"], "validation_id": persisted["validation_id"], "timestamp": persisted["created_at"]})
    repository.update_candidate(candidate_id, candidate, candidate["lifecycle_status"])
    repository.save_candidate_event(candidate_id, {"state": candidate["lifecycle_status"], "validation_id": persisted["validation_id"], "actor_authentication": "NOT_AVAILABLE"})
    return persisted


@v1_router.get("/validation-runs/{validation_id}", tags=["Scientific Calibration"])
def get_validation_result(validation_id: str):
    result = repository.get_validation_run(validation_id)
    if result is None: raise HTTPException(status_code=404, detail="Validation run not found")
    return result


@v1_router.get("/calibration-candidates/{candidate_id}", tags=["Scientific Calibration"])
def get_calibration_candidate(candidate_id: str):
    candidate = repository.get_candidate(candidate_id)
    if candidate is None: raise HTTPException(status_code=404, detail="Calibration candidate not found")
    return {**candidate, "lifecycle_events": repository.list_candidate_events(candidate_id)}


@v1_router.get("/calibration-candidates/{candidate_id}/comparison", tags=["Scientific Calibration"])
def compare_calibration_candidate(candidate_id: str):
    candidate = repository.get_candidate(candidate_id)
    if candidate is None: raise HTTPException(status_code=404, detail="Calibration candidate not found")
    validations = repository.list_candidate_validation_runs(candidate_id)
    if not validations: raise HTTPException(status_code=404, detail="No temporal validation comparison exists for this candidate")
    return {"candidate_id": candidate_id, "model_id": candidate["model_id"], "latest_validation": validations[0],
            "all_validation_runs": validations, "candidate_parameters": candidate["candidate_parameters"],
            "original_configuration_version": candidate["original_configuration_version"],
            "field_validation_claim": "POLICY_RESULT_ONLY_NOT_INDEPENDENT_FIELD_VALIDATION"}


@v1_router.get("/wells/{well_id}/calibration-candidates", tags=["Scientific Calibration"])
def list_calibration_candidates(well_id: str):
    require_known_well(well_id)
    return {"well_id": well_id, "candidates": repository.list_candidates(well_id), "activation_enabled": False}


@v1_router.post("/calibration-candidates/{candidate_id}/reject", tags=["Scientific Calibration"])
def reject_calibration_candidate(candidate_id: str, req: CandidateRejectionRequest):
    candidate = repository.get_candidate(candidate_id)
    if candidate is None: raise HTTPException(status_code=404, detail="Calibration candidate not found")
    if candidate["lifecycle_status"] in {"ACTIVE", "REJECTED", "SUPERSEDED"}: raise HTTPException(status_code=409, detail="Candidate cannot transition from its current state")
    candidate["lifecycle_status"] = "REJECTED"
    candidate["approval_status"] = "REJECTED"
    candidate.setdefault("lifecycle_history", []).append({"state": "REJECTED", "reason": req.reason, "actor_authentication": "NOT_AVAILABLE"})
    repository.update_candidate(candidate_id, candidate, "REJECTED")
    return repository.save_candidate_event(candidate_id, {"state": "REJECTED", "reason": req.reason, "actor_authentication": "NOT_AVAILABLE", "workflow_security": "UNPROTECTED_DEVELOPMENT_ONLY"})


@v1_router.post("/calibration-candidates/{candidate_id}/approve", tags=["Scientific Calibration"])
def approve_calibration_candidate(candidate_id: str):
    if repository.get_candidate(candidate_id) is None: raise HTTPException(status_code=404, detail="Calibration candidate not found")
    raise HTTPException(status_code=403, detail="Approval and activation are disabled until authentication, RBAC, and an authorized audit workflow exist.")


@v1_router.get("/wells/{well_id}/active-calibration-history", tags=["Scientific Calibration"])
def get_active_calibration_history(well_id: str):
    require_known_well(well_id)
    return {"well_id": well_id, "active_candidate": None, "history": [], "activation_enabled": False,
            "reason": "No authenticated approval or activation workflow exists; candidates never replace active well configuration."}


@v1_router.get("/physics-runs/{run_id}/comparisons", tags=["Digital Twin"])
def compare_physics_run(run_id: str):
    run = repository.get_physics_run(run_id)
    if run is None: raise HTTPException(status_code=404, detail="Physics run not found")
    snapshot = repository.get_twin_snapshot(run["snapshot_id"])
    measurements = (snapshot or {}).get("measurements", {})
    comparisons = []
    candidates = (("viscosity", "viscosity_cp", "viscosity_cp", "cP"),
                  ("srp", "estimated_production_bpd", "oil_rate_bpd", "bbl/day"))
    for model_name, output_name, measurement_name, unit in candidates:
        output = run.get("model_results", {}).get(model_name, {}).get("outputs", {}).get(output_name)
        observed = measurements.get(measurement_name)
        if output and observed and observed.get("unit") == unit:
            predicted = output.get("value")
            measured = observed.get("value")
            comparisons.append({"model": model_name, "output": output_name, "measurement_id": observed.get("measurement_id"),
                                "measurement_timestamp": observed.get("measured_at"), "predicted_value": predicted,
                                "observed_value": measured, "unit": unit,
                                "absolute_error": abs(predicted - measured) if isinstance(predicted, (int, float)) else None,
                                "comparison_status": "INFORMATIONAL_SINGLE_SNAPSHOT_COMPARISON_NOT_VALIDATION"})
    return {"run_id": run_id, "comparisons": comparisons,
            "status": "AVAILABLE" if comparisons else "NO_COMPATIBLE_MEASURED_OUTPUTS",
            "reason": None if comparisons else "This snapshot has no measured value with a directly compatible output variable and unit."}


@v1_router.get("/agent/status", tags=["Agentic AI"])
def get_agent_status():
    return agent_runtime.status()


@v1_router.post("/agent/investigate", tags=["Agentic AI"])
async def investigate_with_agent(req: AgentInvestigationRequest, request: Request):
    require_known_well(req.well_id)
    actor = getattr(request.state, "auth_user", None)
    try:
        result = await agent_runtime.investigate(
            req.well_id, req.question, days=req.days,
            actor_user_id=actor.get("user_id") if actor else None,
        )
        return result
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AgentExecutionError as exc:
        logger.exception("Agent investigation failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@v1_router.get("/agent/runs", tags=["Agentic AI"])
def list_agent_runs(well_id: str = Query(min_length=1, max_length=128),
                    limit: int = Query(50, ge=1, le=200)):
    require_known_well(well_id)
    return {"runs": repository.list_agent_runs(well_id, limit)}


@v1_router.get("/models/production", tags=["Field ML"])
def list_field_production_models(well_id: str = Query(min_length=1, max_length=128),
                                 limit: int = Query(50, ge=1, le=200)):
    require_known_well(well_id)
    models = repository.list_field_models(well_id, limit)
    return {"models": [{
        "model_id": item["model_id"],
        "well_id": item["well_id"],
        "model_family": item["model_family"],
        "horizon_days": item["horizon_days"],
        "lifecycle_status": item["lifecycle_status"],
        "sample_count": item["sample_count"],
        "metrics": item["metrics"],
        "dataset_fingerprint": item["dataset_fingerprint"],
        "created_at": item["created_at"],
        "approved_at": item["approved_at"],
        "approved_by": item["approved_by"],
    } for item in models]}


@v1_router.post("/models/production/train", tags=["Field ML"])
def train_field_production_model(req: FieldModelTrainRequest, request: Request):
    require_known_well(req.well_id)
    if config.data_mode != "field":
        raise HTTPException(status_code=503, detail="Measured-data model training is disabled in simulation mode")
    try:
        result = field_ml_training.train(
            req.well_id,
            req.horizon_days,
            req.start_at,
            req.end_at,
            min_samples=req.min_samples,
            max_feature_age_hours=req.max_feature_age_hours,
        )
        actor = getattr(request.state, "auth_user", None)
        repository.write_auth_audit_event({
            "event_id": str(uuid.uuid4()),
            "user_id": actor.get("user_id") if actor else None,
            "action": "field_model_trained",
            "resource": f"well:{req.well_id}",
            "outcome": result["model"]["lifecycle_status"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "details": {"model_id": result["model"]["model_id"], "horizon_days": req.horizon_days,
                        "dataset_fingerprint": result["model"]["dataset_fingerprint"]},
        })
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@v1_router.post("/models/{model_id}/promote", tags=["Field ML"])
def promote_field_production_model(model_id: str, req: FieldModelPromoteRequest, request: Request):
    actor = getattr(request.state, "auth_user", None)
    if not actor or actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required to promote a field model")
    if req.acknowledgement != "I_HAVE_REVIEWED_FIELD_MODEL_EVIDENCE":
        raise HTTPException(status_code=422, detail="Explicit model-review acknowledgement is required")
    try:
        record = field_ml_training.verify_artifact(model_id)
        promoted = repository.promote_field_model(model_id, actor["user_id"])
        repository.write_auth_audit_event({
            "event_id": str(uuid.uuid4()), "user_id": actor["user_id"],
            "action": "field_model_promoted", "resource": f"model:{model_id}",
            "outcome": "success", "created_at": datetime.now(timezone.utc).isoformat(),
            "details": {"well_id": record["well_id"], "horizon_days": record["horizon_days"],
                        "dataset_fingerprint": record["dataset_fingerprint"]},
        })
        return {"model_id": promoted["model_id"], "lifecycle_status": promoted["lifecycle_status"],
                "approved_at": promoted["approved_at"], "approved_by": promoted["approved_by"],
                "field_validation": "NOT_ESTABLISHED_WITHOUT_EXTERNAL_REVIEW_AND_FIELD_EVIDENCE"}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@v1_router.get("/models/production/predict", tags=["Field ML"])
def predict_with_promoted_field_model(well_id: str = Query(min_length=1, max_length=128),
                                      horizon_days: int = Query(7)):
    require_known_well(well_id)
    if config.data_mode != "field":
        raise HTTPException(status_code=503, detail="Measured-data model inference is disabled in simulation mode")
    try:
        return field_ml_training.predict(well_id, horizon_days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@auth_router.post("/login")
def login(req: LoginRequest, request: Request):
    try:
        return auth_service.login(
            req.username, req.password,
            ip_address=request.client.host if request.client else None,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@auth_router.get("/me")
def get_current_user(request: Request):
    user = getattr(request.state, "auth_user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication is disabled or no active session is present")
    return {"user": auth_service.public_user(user)}


@auth_router.post("/logout")
def logout(request: Request):
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        auth_service.logout(
            token, ip_address=request.client.host if request.client else None,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"status": "SIGNED_OUT"}


@auth_router.get("/users")
def list_users(request: Request):
    require_admin_user_management(request)
    return {"users": repository.list_auth_users(), "roles": sorted(ROLES)}


@auth_router.get("/audit-events")
def list_auth_audit_events(request: Request, limit: int = Query(200, ge=1, le=1000)):
    require_admin_user_management(request)
    return {"events": repository.list_auth_audit_events(limit)}


@auth_router.post("/users", status_code=201)
def create_user(req: UserCreateRequest, request: Request):
    require_admin_user_management(request)
    if repository.get_auth_user_by_username(req.username.casefold()):
        raise HTTPException(status_code=409, detail="Username already exists")
    actor = getattr(request.state, "auth_user", None)
    try:
        user = auth_service.create_user(req.username, req.password, req.role,
                                        actor_user_id=actor["user_id"] if actor else None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"user": user}


@auth_router.patch("/users/{username}")
def update_user(username: str, req: UserUpdateRequest, request: Request):
    require_admin_user_management(request)
    actor = getattr(request.state, "auth_user", None)
    try:
        user = auth_service.update_user(
            username, role=req.role, is_active=req.is_active, password=req.password,
            actor_user_id=actor["user_id"] if actor else None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"user": user}


app.include_router(auth_router)
app.include_router(v1_router)


@app.get("/health", tags=["System"])
def health_check():
    try:
        repository.list_wells()
        database_status = "READY"
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc.__class__.__name__}") from exc
    return {
        "status": "UP",
        "service": config.service_name,
        "version": config.version,
        "database": database_status,
        "data_mode": config.data_mode.upper(),
        "data_availability": "SIMULATED_DEVELOPMENT_DATA" if config.data_mode == "simulation" else "AWAITING_MEASURED_DATA",
        "auth_required": config.auth_mode == "required",
        "disclaimer": "Synthetic development simulation; not field data" if config.data_mode == "simulation" else "Field mode; no telemetry is fabricated",
        "data_sources": repository.list_data_sources(),
    }


@app.get("/health/live", tags=["System"])
def liveness_check():
    return {"status": "ALIVE", "service": config.service_name}


@app.get("/health/ready", tags=["System"])
def readiness_check():
    health = health_check()
    return {"status": "READY", "database": health["database"], "data_mode": health["data_mode"]}


@app.get("/models", tags=["System"])
def list_models():
    return {
        "models": [
            {"name": "production_forecaster", "status": prod_forecaster.model_status, "field_inference": "UNAVAILABLE_UNVALIDATED_ARTIFACT"},
            {"name": "failure_predictor", "status": failure_predictor.model_status, "field_inference": "UNAVAILABLE_NO_FIELD_FAILURE_LABELS"},
            {"name": "anomaly_detector", "status": anomaly_detector.model_status, "field_inference": "UNAVAILABLE_SYNTHETIC_BASELINE"},
            {"name": "thermal_model", "status": "SIMULATION_ONLY", "type": "simplified analytical model; not field validated"}
        ]
    }


# --- Well State & Telemetry Endpoints ---

@app.get("/api/wells", tags=["Wells"])
def get_wells():
    wells_list = []
    for w in repository.list_wells():
        if config.data_mode != "simulation" and is_simulation_profile(w):
            continue
        wid = w["well_id"]
        wells_list.append({
            "well_id": wid,
            "name": w["name"],
            "depth_m": w.get("depth_m"),
            "pump_depth_m": w.get("pump_depth_m"),
            "cycle_number": w.get("cycle_number"),
            "days_in_production": w.get("days_in_production"),
            "status": w.get("status", "CONFIGURED")
        })
    return {"wells": wells_list}


@app.get("/api/wells/{well_id}", tags=["Wells"])
def get_well_details(well_id: str):
    require_known_well(well_id)
    well = repository.get_well(well_id)
    if well is None:
        raise HTTPException(status_code=404, detail="Well not found")
    return {"well": well}


@app.get("/api/wells/{well_id}/state", tags=["Wells"])
def get_well_digital_twin_state(well_id: str):
    require_known_well(well_id)
    require_simulated_well(well_id, "Digital twin state synthesis")
    return simulator.generate_current_telemetry(well_id)


@app.get("/api/wells/{well_id}/telemetry", tags=["Telemetry"])
def get_latest_telemetry(well_id: str):
    require_known_well(well_id)
    require_simulated_well(well_id, "Synthetic telemetry")
    return simulator.generate_current_telemetry(well_id)


@app.get("/api/wells/{well_id}/production", tags=["Telemetry"])
def get_well_production_history(well_id: str, days: int = Query(60, ge=10, le=180)):
    require_known_well(well_id)
    records = repository.list_measurements(well_id, days)
    if records:
        return {"history": records, "data_source_mode": "MEASURED", "provenance": "Each row identifies its source and quality status"}
    if config.data_mode == "simulation":
        return {"history": simulator.generate_historical_time_series(well_id, days), "data_source_mode": "SIMULATION"}
    if not records:
        raise HTTPException(status_code=503, detail=f"Production history unavailable for {well_id}: no measured records in the requested period")
    return {"history": records, "data_source_mode": "MEASURED", "provenance": "Each row identifies its source and quality status"}


@app.get("/api/wells/{well_id}/time-machine/{day}", tags=["Simulation"])
def get_time_machine_state(well_id: str, day: int):
    require_known_well(well_id)
    require_simulated_well(well_id, "Time-machine projection")
    if day < 0 or day > 180:
        raise HTTPException(status_code=422, detail="day must be between 0 and 180")
    return simulator.generate_current_telemetry(well_id, day_override=day)


@app.get("/api/wells/{well_id}/css", tags=["CSS"])
def get_well_css_history(well_id: str):
    require_known_well(well_id)
    require_simulated_well(well_id, "Synthetic CSS history")
    return {**agent.get_css_history(well_id), "data_source_mode": "SIMULATION"}


@app.get("/api/wells/{well_id}/srp", tags=["SRP"])
def get_well_srp_history(well_id: str):
    require_known_well(well_id)
    require_simulated_well(well_id, "Synthetic SRP history")
    return agent.get_srp_history(well_id)


@app.get("/api/wells/{well_id}/analysis-runs", tags=["Persistence"])
def get_analysis_runs(well_id: str, limit: int = Query(50, ge=1, le=200)):
    require_known_well(well_id)
    return {"runs": repository.list_analyses(well_id, limit)}


@app.get("/api/wells/{well_id}/srp/dyno-card", tags=["SRP"])
def get_dynamometer_card(well_id: str):
    require_known_well(well_id)
    require_simulated_well(well_id, "Synthetic dynamometer card")
    state = simulator.generate_current_telemetry(well_id)
    stroke_m = state["srp_operating_state"]["stroke_length_m"]
    spm = state["srp_operating_state"]["spm"]
    visc = state["fluid_state"]["estimated_viscosity_cp"]
    card_points = srp_model.generate_dynamometer_card(stroke_m, spm, visc)
    return {
        "well_id": well_id,
        "stroke_length_m": stroke_m,
        "spm": spm,
        "viscosity_cp": visc,
        "rod_floating_detected": state["srp_operating_state"]["rod_floating_detected"],
        "card_points": card_points
    }


# --- Prediction Endpoints ---

@app.post("/predict/production", tags=["ML Predictions"])
def predict_production_endpoint(req: ProductionPredictRequest):
    require_known_well(req.well_id)
    require_simulation("Production forecasting")
    result = prod_forecaster.predict(
        req.temperature_c, req.pressure_bar, req.spm, req.stroke_length_m,
        req.days_since_injection, req.recent_oil_rate_bpd
    )
    result["inputs"] = req.model_dump()
    result["run_id"] = repository.save_analysis(req.well_id, "production_forecast", result)
    return result


@app.post("/predict/failure", tags=["ML Predictions"])
def predict_failure_endpoint(req: FailurePredictRequest):
    require_known_well(req.well_id)
    require_simulation("Failure prediction")
    result = failure_predictor.predict_failure_risks(
        req.stroke_length_m, req.spm, req.temperature_c, req.pressure_bar, req.days_in_production
    )
    return result


@app.post("/predict/viscosity", tags=["ML Predictions"])
def predict_viscosity_endpoint(req: ViscosityPredictRequest):
    visc = visc_model.calculate_viscosity(req.temperature_c, req.pressure_bar)
    mob = visc_model.calculate_mobility(req.temperature_c, pressure_bar=req.pressure_bar)
    return {
        "temperature_c": req.temperature_c,
        "viscosity_cp": visc,
        "darcy_mobility_md_cp": mob,
        "formulation": "Walther / ASTM D341 calibrated on Baghewala crude"
    }


@app.post("/predict/temperature", tags=["ML Predictions"])
def predict_temperature_endpoint(req: TemperaturePredictRequest):
    temp = thermal_model.predict_temperature_at_day(float(req.day), req.peak_temperature_c)
    return {
        "peak_temperature_c": req.peak_temperature_c,
        "day": req.day,
        "predicted_reservoir_temperature_c": temp
    }


@app.post("/detect/anomaly", tags=["ML Predictions"])
def detect_anomaly_endpoint(req: AnomalyDetectRequest):
    require_simulation("Anomaly detection")
    return anomaly_detector.detect(
        req.temperature_c, req.pressure_bar, req.pprl_lbs, req.mprl_lbs,
        req.oil_rate_bpd, req.motor_power_kw
    )


# --- Simulation & What-If Endpoints ---

@app.post("/simulate/css", tags=["Simulation"])
def simulate_css_endpoint(req: CSSSimulateRequest):
    require_simulation("Synthetic CSS thermal simulation")
    res = thermal_model.calculate_peak_temperature(req.steam_mass_tons, req.soak_days)
    cooling_curve = thermal_model.generate_cooling_curve(res["peak_temperature_c"], max_days=180, step_days=10)
    return {
        "data_source_mode": "SIMULATION",
        "peak_metrics": res,
        "cooling_projection": cooling_curve
    }


@app.post("/simulate/srp", tags=["Simulation"])
def simulate_srp_endpoint(req: SRPSimulateRequest):
    require_simulation("Synthetic SRP performance simulation")
    perf = srp_model.evaluate_srp_performance(req.stroke_length_m, req.spm, req.avg_viscosity_cp)
    dyno = srp_model.generate_dynamometer_card(req.stroke_length_m, req.spm, req.avg_viscosity_cp)
    return {
        "data_source_mode": "SIMULATION",
        "performance": perf,
        "dynamometer_card": dyno
    }


@app.post("/simulate/scenario", tags=["Simulation"])
def simulate_scenario_endpoint(req: ScenarioRequest):
    require_known_well(req.well_id)
    require_simulation("Synthetic CSS + SRP scenario evaluation")
    well_state = simulator.wells_state.get(req.well_id, {}) if config.data_mode == "simulation" else {}
    latest = repository.latest_measurements(req.well_id) if config.data_mode != "simulation" else {}
    days_in_cycle = req.days_in_cycle
    if days_in_cycle is None and config.data_mode == "simulation":
        days_in_cycle = well_state.get("days_in_production")
    if days_in_cycle is None and "days_in_production" in latest:
        days_in_cycle = int(latest["days_in_production"]["value"])
    if days_in_cycle is None:
        raise HTTPException(status_code=503, detail="Scenario needs the selected well's measured cycle day or an explicit days_in_cycle input")
    result = optimizer.evaluate_candidate(
        req.steam_volume, req.soak_time, req.stroke_length, req.spm,
        days_in_cycle=days_in_cycle,
        production_cutoff_days=req.production_cutoff,
    )
    result["scenario_assumptions"] = {
        "production_cutoff_days": req.production_cutoff,
        "injection_pressure": "unsupported; fixed steam properties are used by the thermal model",
        "vfd_frequency_hz": "derived from SPM using the project conversion factor",
    }
    result["data_source_mode"] = "SIMULATION"
    return result


# --- Optimization Endpoints ---

@app.post("/optimize", tags=["Optimization"])
@app.post("/optimize/joint", tags=["Optimization"])
def run_optimization_endpoint(req: OptimizeRequest):
    require_known_well(req.well_id)
    require_simulated_well(req.well_id, "Joint optimization")
    result = agent.optimize_operations(
        req.well_id, req.weight_production, req.weight_sor, req.weight_energy, req.weight_risk
    )
    state = agent.get_well_state(req.well_id)
    result["inputs"] = {
        "well_id": req.well_id,
        "objective_weights": {
            "production": req.weight_production,
            "sor": req.weight_sor,
            "energy": req.weight_energy,
            "risk": req.weight_risk,
        },
        "well_state": {
            "cycle_day": state["cycle_info"]["days_in_production"],
            "oil_rate_bpd": state["production_state"]["oil_rate_bpd"],
            "sor": state["cycle_info"]["sor_cumulative"],
            "energy_kwh_bbl": state["srp_operating_state"]["kwh_per_barrel"],
            "failure_risk": state["srp_operating_state"]["rod_floating_risk"],
        },
    }
    result["run_id"] = repository.save_analysis(req.well_id, "optimization", result)
    return result


# --- Agentic AI Copilot Endpoint ---

@app.post("/api/copilot/query", tags=["Agentic AI"])
@app.post("/agent/query", tags=["Agentic AI"])
def query_copilot(req: CopilotQueryRequest):
    require_known_well(req.well_id)
    require_simulated_well(req.well_id, "Deterministic simulator-based analysis")
    return agent.handle_user_query(req.query, req.well_id)


# --- WebSocket Streaming Endpoint ---

@app.websocket("/ws/telemetry/{well_id}")
async def websocket_telemetry_stream(websocket: WebSocket, well_id: str):
    if config.auth_mode == "required":
        authorization = websocket.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            await websocket.close(code=4401, reason="Authentication required")
            return
        try:
            auth_service.authenticate(token)
        except AuthenticationError:
            await websocket.close(code=4401, reason="Invalid or expired credentials")
            return
    if config.data_mode != "simulation":
        await websocket.close(code=1013, reason="Field telemetry stream is unavailable; no connected telemetry source")
        return
    if well_id not in simulator.wells_state:
        await websocket.close(code=1008, reason="Unknown well_id")
        return
    await websocket.accept()
    try:
        while True:
            data = simulator.generate_current_telemetry(well_id)
            await websocket.send_json(data)
            await asyncio.sleep(2.0)  # Stream tick every 2 seconds
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.host, port=config.port, reload=False)
