import os
import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_missing_required_environment_variables_raises_validation_error(monkeypatch):
    """Verifies that missing required environment variables causes Settings to fail fast with a clear ValidationError."""
    # Isolate from ambient environment and .env file
    # Clear critical variables
    for var in [
        "ENVIRONMENT",
        "DATABASE_URL",
        "REDIS_URL",
        "SECRET_KEY",
        "CORS_ORIGINS",
        "CELERY_QUEUE",
        "DB_POOL_SIZE",
        "SCHEDULER_TICK_INTERVAL_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)

    # Creating Settings without env_file or required values must raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    missing_fields = {e["loc"][0] for e in errors if e["type"] == "missing"}

    # Assert required critical fields are reported as missing
    assert "database_url" in missing_fields
    assert "redis_url" in missing_fields
    assert "secret_key" in missing_fields
    assert "environment" in missing_fields
    assert "cors_origins" in missing_fields


def test_secret_key_minimum_length_validation():
    """Verifies that SECRET_KEY shorter than 32 characters raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            app_name="Tether",
            app_version="1.0.0",
            log_level="INFO",
            log_format="json",
            jwt_algorithm="HS256",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
            auth_rate_limit_per_minute=60,
            environment="development",
            database_url="postgresql+psycopg://user:pass@db:5432/test",
            redis_url="redis://cache:6379/0",
            secret_key="too-short-secret",
            cors_origins="http://localhost:3000",
            celery_queue="monitoring_jobs",
            db_pool_size=5,
            db_max_overflow=10,
            db_pool_timeout=30,
            db_pool_recycle=1800,
            scheduler_tick_interval_seconds=10,
            retry_initial_delay_seconds=2,
            retry_backoff_factor=2,
            retry_max_delay_seconds=60,
            target_lock_ttl_seconds=30,
            result_retention_days=30,
            job_retention_days=14,
            alert_retention_days=90,
            audit_log_retention_days=365,
        )

    errors = exc_info.value.errors()
    assert any("secret_key" in str(e["loc"]) for e in errors)


def test_database_url_normalization():
    """Verifies that postgresql:// is normalized to postgresql+psycopg://."""
    settings = Settings(
        _env_file=None,
        app_name="Tether",
        app_version="1.0.0",
        log_level="INFO",
        log_format="json",
        jwt_algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
        auth_rate_limit_per_minute=60,
        environment="development",
        database_url="postgresql://user:pass@db:5432/test",
        redis_url="redis://cache:6379/0",
        secret_key="a" * 32,
        cors_origins="http://localhost:3000",
        celery_queue="monitoring_jobs",
        db_pool_size=5,
        db_max_overflow=10,
        db_pool_timeout=30,
        db_pool_recycle=1800,
        scheduler_tick_interval_seconds=10,
        retry_initial_delay_seconds=2,
        retry_backoff_factor=2,
        retry_max_delay_seconds=60,
        target_lock_ttl_seconds=30,
        result_retention_days=30,
        job_retention_days=14,
        alert_retention_days=90,
        audit_log_retention_days=365,
    )
    assert settings.database_url.startswith("postgresql+psycopg://")

