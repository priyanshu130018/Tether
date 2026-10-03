import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.db import Base, create_db_engine
from app.core.logging import JSONFormatter
from app.core.metrics import (
    ALERTS_CREATED_TOTAL,
    HTTP_REQUESTS_TOTAL,
    MONITORING_CHECKS_TOTAL,
    get_prometheus_metrics,
)
from app.main import app
from app.models import (
    AlertEvent,
    AlertEventType,
    AuditLog,
    CheckStatus,
    Job,
    JobStatus,
    MonitoringResult,
    Protocol,
    RefreshToken,
    Target,
    TargetStatus,
    Tenant,
    User,
)
from app.tasks.maintenance import cleanup_old_data


def test_liveness_probe(client: TestClient):
    """GET /health/live returns 200 OK regardless of downstream DB state."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_readiness_probe_success(client: TestClient):
    """GET /health/ready returns 200 when database and Redis are reachable."""
    with patch("redis.Redis.from_url") as mock_redis_cls:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis_cls.return_value = mock_redis

        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["database"] == "healthy"
        assert data["dependencies"]["redis"] == "healthy"


def test_readiness_probe_redis_failure(client: TestClient):
    """GET /health/ready returns 503 when Redis is down."""
    with patch("redis.Redis.from_url") as mock_redis_cls:
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = ConnectionError("Redis connection refused")
        mock_redis_cls.return_value = mock_redis

        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["status"] == "unready"
        assert data["dependencies"]["redis"] == "unhealthy"


def test_detailed_health_endpoint(client: TestClient):
    """GET /health provides service metadata without exposing internal credentials."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "Tether"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "database" in data
    assert "redis" in data
    # Ensure credentials/secrets are not leaked
    assert "database_url" not in data
    assert "secret_key" not in data


def test_version_endpoint(client: TestClient):
    """GET /api/version returns safe version info."""
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tether"
    assert "version" in data
    assert "environment" in data


def test_prometheus_metrics_endpoint(client: TestClient):
    """GET /metrics exports standard Prometheus text payload."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    content = response.text
    assert "http_requests_total" in content
    assert "monitoring_checks_total" in content
    assert "alerts_created_total" in content


def test_correlation_id_middleware(client: TestClient):
    """Incoming requests without X-Request-ID generate a UUID; provided valid IDs are preserved."""
    # 1. Generated Request ID
    resp1 = client.get("/health/live")
    assert "X-Request-ID" in resp1.headers
    assert len(resp1.headers["X-Request-ID"]) > 10

    # 2. Custom Valid Request ID
    custom_id = "req-custom-trace-12345"
    resp2 = client.get("/health/live", headers={"X-Request-ID": custom_id})
    assert resp2.headers["X-Request-ID"] == custom_id


def test_json_log_formatter():
    """Structured JSON formatter formats logs to JSON and redacts sensitive keys."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User authenticated",
        args=(),
        exc_info=None,
    )
    record.extra_fields = {
        "user_email": "admin@tether.local",
        "password": "supersecretpassword",
        "auth_token": "jwt-token-val",
    }

    formatted = formatter.format(record)
    log_dict = json.loads(formatted)

    assert log_dict["service"] == "tether-api"
    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "User authenticated"
    assert log_dict["user_email"] == "admin@tether.local"
    # Verify sensitive fields are masked
    assert log_dict["password"] == "********"
    assert log_dict["auth_token"] == "********"


def test_production_secret_validation():
    """Settings model validator rejects weak or default secrets when ENVIRONMENT=production."""
    # 1. Insecure default secret key rejected
    with pytest.raises(ValueError, match="SECRET_KEY must be a cryptographically strong secret"):
        Settings(
            environment="production",
            secret_key="tether-insecure-dev-secret-key-12345",
            database_url="postgresql+psycopg://prod_user:StrongPass123!@db:5432/prod_db",
        )

    # 2. Default database password rejected
    with pytest.raises(ValueError, match="DATABASE_URL must not contain default development credentials"):
        Settings(
            environment="production",
            secret_key="a" * 64,
            database_url="postgresql+psycopg://netwatch:change-me@localhost:5432/netwatch",
        )

    # 3. Valid production configuration passes
    valid_settings = Settings(
        environment="production",
        secret_key="a" * 64,
        database_url="postgresql+psycopg://prod_user:StrongSecurePassword456!@db:5432/prod_db",
    )
    assert valid_settings.environment == "production"
    assert valid_settings.log_format == "json"


def test_data_retention_cleanup_task(db_session):
    """Maintenance task purges expired monitoring results, jobs, alerts, and tokens according to retention limits."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=60)
    recent_time = now - timedelta(days=2)

    # Create old and recent records
    res_old = MonitoringResult(
        tenant_id=1,
        target_id=1,
        protocol=Protocol.TCP,
        status=CheckStatus.UP,
        timestamp=old_time,
    )
    res_recent = MonitoringResult(
        tenant_id=1,
        target_id=1,
        protocol=Protocol.TCP,
        status=CheckStatus.UP,
        timestamp=recent_time,
    )
    db_session.add_all([res_old, res_recent])

    # Old job
    job_old = Job(
        tenant_id=1,
        target_id=1,
        task_type="scheduled_check",
        status=JobStatus.SUCCESSFUL,
        created_at=old_time,
    )
    job_recent = Job(
        tenant_id=1,
        target_id=1,
        task_type="scheduled_check",
        status=JobStatus.SUCCESSFUL,
        created_at=recent_time,
    )
    db_session.add_all([job_old, job_recent])

    # Expired token
    token_old = RefreshToken(
        user_id=1,
        token_hash="hash_old",
        expires_at=old_time,
        created_at=old_time,
    )
    token_valid = RefreshToken(
        user_id=1,
        token_hash="hash_valid",
        expires_at=now + timedelta(days=7),
        created_at=now,
    )
    db_session.add_all([token_old, token_valid])
    db_session.commit()

    with patch("app.tasks.maintenance.SessionLocal", return_value=db_session):
        purged = cleanup_old_data()
        assert purged["monitoring_results"] >= 1
        assert purged["jobs"] >= 1
        assert purged["refresh_tokens"] >= 1
