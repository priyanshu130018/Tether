from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Required Core Application Info ---
    app_name: str
    app_version: str
    environment: Literal["development", "test", "production"]

    # --- Required Infrastructure URLs ---
    database_url: str
    redis_url: str
    celery_queue: str
    cors_origins: list[str] | str

    # --- Required PostgreSQL Connection Pooling ---
    db_pool_size: int
    db_max_overflow: int
    db_pool_timeout: float
    db_pool_recycle: int

    # --- Required Scheduling & Worker Retries ---
    scheduler_tick_interval_seconds: float
    retry_initial_delay_seconds: float
    retry_backoff_factor: float
    retry_max_delay_seconds: float
    target_lock_ttl_seconds: int

    # --- Required Authentication & Security ---
    secret_key: str = Field(
        validation_alias=AliasChoices("secret_key", "SECRET_KEY", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    auth_rate_limit_per_minute: int

    # --- Required Data Retention Policies (Days) ---
    result_retention_days: int
    job_retention_days: int
    alert_retention_days: int
    audit_log_retention_days: int

    # --- Required Logging ---
    log_level: str
    log_format: Literal["text", "json"]

    # --- Optional Production Observability ---
    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    enable_tracing: bool = False

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError(
                "SECRET_KEY must be a cryptographically strong secret with at least 32 characters."
            )
        return value

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            if value.startswith("[") and value.endswith("]"):
                try:
                    import json
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return value

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """Validate security and configuration constraints."""
        if len(self.secret_key) < 32:
            raise ValueError(
                "SECRET_KEY must be a cryptographically strong secret with at least 32 characters."
            )
        if self.environment == "production":
            if "insecure-dev" in self.secret_key:
                raise ValueError(
                    "Production startup rejected: SECRET_KEY must not contain insecure default substrings."
                )
            if "change-me" in self.database_url:
                raise ValueError(
                    "Production startup rejected: DATABASE_URL must not contain default development credentials ('change-me')."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
