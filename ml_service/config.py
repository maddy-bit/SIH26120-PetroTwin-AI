"""
PETRO-TWIN AI: ML Service Configuration
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field, field_validator

ROOT_DIR = Path(__file__).resolve().parent.parent


class ServiceConfig(BaseModel):
    service_name: str = "petro-twin-ml-service"
    version: str = "1.4.0"
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")), ge=1, le=65535)
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    cors_origins: list[str] = Field(default_factory=lambda: [
        origin.strip() for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
        ).split(",") if origin.strip()
    ])
    models_dir: str = str(ROOT_DIR / "ml_service" / "saved_models")
    field_model_artifact_dir: str = os.getenv("PETROTWIN_FIELD_MODEL_ARTIFACT_DIR", "").strip() or str(ROOT_DIR / "ml_service" / "saved_models" / "field")
    data_sources_path: str = str(ROOT_DIR / "data" / "sources" / "dataset_sources.yaml")
    physics_config_path: str = str(ROOT_DIR / "config" / "physics.yaml")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{ROOT_DIR / 'data' / 'petrotwin.sqlite3'}")
    data_mode: str = os.getenv("PETROTWIN_DATA_MODE", "field").strip().lower()
    auth_mode: str = os.getenv("PETROTWIN_AUTH_MODE", "disabled").strip().lower()
    jwt_secret: str = os.getenv("PETROTWIN_JWT_SECRET", "")
    token_ttl_minutes: int = Field(default_factory=lambda: int(os.getenv("PETROTWIN_TOKEN_TTL_MINUTES", "15")), ge=5, le=60)
    agent_base_url: str = os.getenv("PETROTWIN_AGENT_BASE_URL", "").strip().rstrip("/")
    agent_api_key: str = os.getenv("PETROTWIN_AGENT_API_KEY", "")
    agent_model: str = os.getenv("PETROTWIN_AGENT_MODEL", "").strip()
    agent_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("PETROTWIN_AGENT_TIMEOUT_SECONDS", "60")), ge=10, le=180)
    agent_max_tool_calls: int = Field(default_factory=lambda: int(os.getenv("PETROTWIN_AGENT_MAX_TOOL_CALLS", "8")), ge=7, le=12)

    @field_validator("agent_base_url")
    @classmethod
    def validate_agent_base_url(cls, value: str) -> str:
        if value:
            from urllib.parse import urlparse
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("PETROTWIN_AGENT_BASE_URL must be an absolute HTTP(S) URL")
        return value

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, value: str) -> str:
        if value not in {"disabled", "required"}:
            raise ValueError("PETROTWIN_AUTH_MODE must be 'disabled' or 'required'")
        return value

    @field_validator("jwt_secret")
    @classmethod
    def require_jwt_secret_in_protected_mode(cls, value: str, info) -> str:
        if info.data.get("auth_mode") == "required" and len(value.encode("utf-8")) < 32:
            raise ValueError("PETROTWIN_JWT_SECRET must contain at least 32 bytes when auth is required")
        return value

    @field_validator("data_mode")
    @classmethod
    def validate_data_mode(cls, value: str) -> str:
        if value not in {"field", "simulation"}:
            raise ValueError("PETROTWIN_DATA_MODE must be 'field' or 'simulation'")
        return value


config = ServiceConfig()
