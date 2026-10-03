import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
import redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.metrics import get_prometheus_metrics

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health & observability"])

START_TIME = time.time()


@router.get("/health/live", summary="Liveness Probe")
def liveness_probe() -> dict[str, str]:
    """Liveness probe to confirm FastAPI process is running.
    Does NOT fail if downstream dependencies (PostgreSQL/Redis) are degraded.
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready", summary="Readiness Probe")
def readiness_probe(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe verifying that PostgreSQL and Redis are both reachable and able to accept traffic."""
    settings = get_settings()
    errors: dict[str, str] = {}
    dependencies: dict[str, str] = {
        "database": "unhealthy",
        "redis": "unhealthy",
    }

    # 1. Test PostgreSQL connectivity
    try:
        db.execute(text("SELECT 1"))
        dependencies["database"] = "healthy"
    except Exception as exc:
        logger.warning("Readiness probe database check failed: %s", exc)
        errors["database"] = "Database query failed"

    # 2. Test Redis connectivity
    try:
        r = redis.Redis.from_url(settings.redis_url, socket_timeout=2.0)
        if r.ping():
            dependencies["redis"] = "healthy"
    except Exception as exc:
        logger.warning("Readiness probe Redis check failed: %s", exc)
        errors["redis"] = "Redis ping failed"

    if errors:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unready",
                "dependencies": dependencies,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {
        "status": "ready",
        "dependencies": dependencies,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health", summary="Detailed Health Status")
def detailed_health(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Provides high-level system health metrics and component statuses without exposing credentials."""
    settings = get_settings()
    uptime_seconds = int(time.time() - START_TIME)

    db_status = "unhealthy"
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as exc:
        logger.warning("Detailed health database check failed: %s", exc)

    redis_status = "unhealthy"
    try:
        r = redis.Redis.from_url(settings.redis_url, socket_timeout=2.0)
        if r.ping():
            redis_status = "healthy"
    except Exception as exc:
        logger.warning("Detailed health Redis check failed: %s", exc)

    if db_status == "healthy" and redis_status == "healthy":
        overall_status = "healthy"
    elif db_status == "healthy" or redis_status == "healthy":
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": uptime_seconds,
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/version", summary="Safe Version Info")
@router.get("/version", include_in_schema=False)
def version_info() -> dict[str, str]:
    """Return safe version information."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/metrics", summary="Prometheus Metrics")
def prometheus_metrics() -> Response:
    """Expose application and system metrics in standard Prometheus text format."""
    data, content_type = get_prometheus_metrics()
    return Response(content=data, media_type=content_type)
