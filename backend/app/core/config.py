from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Core Application Info
    app_name: str = "Tether"
    app_version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"

    # Infrastructure URLs
    database_url: str = "postgresql+psycopg://netwatch:change-me@localhost:5432/netwatch"
    redis_url: str = "redis://localhost:6379/0"
    celery_queue: str = "monitoring"
    cors_origins: list[str] | str = ["http://localhost:5173", "http://localhost:3000"]

    # PostgreSQL Connection Pooling (Production)
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: float = 30.0
    db_pool_recycle: int = 1800

    # Scheduling & Worker Retries
    scheduler_tick_interval_seconds: float = 5.0
    retry_initial_delay_seconds: float = 1.0
    retry_backoff_factor: float = 2.0
    retry_max_delay_seconds: float = 30.0
    target_lock_ttl_seconds: int = 300

    # Authentication & Security
    secret_key: str = Field(
        default="tether-insecure-dev-secret-key-change-in-production-long-random-string-12345",
        validation_alias=AliasChoices("secret_key", "SECRET_KEY", "JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    auth_rate_limit_per_minute: int = 30

    # Data Retention Policies (Days)
    result_retention_days: int = 30
    job_retention_days: int = 14
    alert_retention_days: int = 90
    audit_log_retention_days: int = 365

    # Observability & Logging
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    enable_tracing: bool = False

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

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
    def validate_production_configuration(self) -> "Settings":
        """Fail safely at startup if production environment has insecure or missing configuration."""
        if self.environment == "production":
            # 1. Enforce strong, non-default secret key
            if "insecure-dev-secret-key" in self.secret_key or len(self.secret_key) < 32:
                raise ValueError(
                    "Production startup rejected: SECRET_KEY must be a cryptographically strong secret with at least 32 characters."
                )
            # 2. Check for default database credentials
            if "change-me" in self.database_url:
                raise ValueError(
                    "Production startup rejected: DATABASE_URL must not contain default development credentials ('change-me')."
                )
            # 3. Default log format in production to JSON if not explicitly specified
            if self.log_format == "text":
                object.__setattr__(self, "log_format", "json")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
