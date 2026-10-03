import asyncio
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401
from app.api.routes.alert_rules import router as alert_rules_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.notification_channels import router as notification_channels_router
from app.api.routes.targets import router as targets_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.workers import router as workers_router
from app.core.config import get_settings
from app.core.db import engine, init_db
from app.core.logging import set_request_id, setup_logging
from app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_FAILED_TOTAL,
    HTTP_REQUESTS_TOTAL,
)
from app.core.telemetry import setup_telemetry

# Initialize structured logging and telemetry
setup_logging()
setup_telemetry()

logger = logging.getLogger("tether.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log startup metadata
    logger.info(
        "Starting Tether API service",
        extra={"extra_fields": {"environment": settings.environment, "version": settings.app_version}},
    )
    yield
    logger.info("Shutting down Tether API service cleanly.")


app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    description="Distributed multi-protocol network monitoring platform, alerting engine, and multi-tenant security architecture.",
    lifespan=lifespan,
)

# Regex to sanitize/validate client-provided X-Request-ID
SAFE_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


def normalize_route_path(path: str) -> str:
    """Normalize parameterized API paths to prevent high-cardinality Prometheus labels."""
    # Replace numeric IDs and UUIDs with :id placeholder
    path = re.sub(r"/\d+(?=/|$)", "/:id", path)
    path = re.sub(r"/[0-9a-fA-F-]{36}(?=/|$)", "/:id", path)
    return path


@app.middleware("http")
async def correlation_and_metrics_middleware(request: Request, call_next):
    # 1. Resolve or generate Request Correlation ID
    client_req_id = request.headers.get("X-Request-ID", "")
    if client_req_id and SAFE_REQUEST_ID_REGEX.match(client_req_id):
        req_id = client_req_id
    else:
        req_id = str(uuid.uuid4())

    set_request_id(req_id)
    start_time = time.time()
    method = request.method
    raw_path = request.url.path
    normalized_path = normalize_route_path(raw_path)

    # 2. Process Request
    try:
        response: Response = await call_next(request)
    except Exception as exc:
        duration = time.time() - start_time
        HTTP_REQUESTS_FAILED_TOTAL.labels(
            method=method,
            path=normalized_path,
            error_type=exc.__class__.__name__,
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method,
            path=normalized_path,
        ).observe(duration)

        logger.error(
            "Unhandled server exception on %s %s: %s",
            method,
            raw_path,
            exc.__class__.__name__,
            exc_info=True,
            extra={"extra_fields": {"method": method, "path": raw_path, "duration_ms": int(duration * 1000)}},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred.", "request_id": req_id},
            headers={"X-Request-ID": req_id},
        )

    duration = time.time() - start_time
    status_code = str(response.status_code)

    # 3. Record Prometheus Metrics (skip raw /metrics scrape itself to avoid skewing)
    if raw_path != "/metrics":
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            path=normalized_path,
            status_code=status_code,
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method,
            path=normalized_path,
        ).observe(duration)
        if response.status_code >= 500:
            HTTP_REQUESTS_FAILED_TOTAL.labels(
                method=method,
                path=normalized_path,
                error_type=f"HTTP_{status_code}",
            ).inc()

    # 4. Inject Response Headers
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# Configure CORS strictly from configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Health & Metrics endpoints
app.include_router(health_router)

# Auth endpoints
app.include_router(auth_router, prefix="/api/auth")
app.include_router(auth_router, prefix="/auth", include_in_schema=False)

# Tenant & Team endpoints
app.include_router(tenants_router, prefix="/api/tenants")
app.include_router(tenants_router, prefix="/tenants", include_in_schema=False)

# Audit Logs endpoints
app.include_router(audit_logs_router, prefix="/api/audit-logs")
app.include_router(audit_logs_router, prefix="/audit-logs", include_in_schema=False)

# Dashboard Summary endpoints
app.include_router(dashboard_router, prefix="/api/dashboard")
app.include_router(dashboard_router, prefix="/dashboard", include_in_schema=False)

# Targets endpoints
app.include_router(targets_router, prefix="/api/targets")
app.include_router(targets_router, prefix="/targets", include_in_schema=False)

# Jobs endpoints
app.include_router(jobs_router, prefix="/api/jobs")
app.include_router(jobs_router, prefix="/jobs", include_in_schema=False)

# Workers endpoints
app.include_router(workers_router, prefix="/api/workers")
app.include_router(workers_router, prefix="/workers", include_in_schema=False)

# Notification Channels endpoints
app.include_router(notification_channels_router, prefix="/api/notification-channels")
app.include_router(notification_channels_router, prefix="/notification-channels", include_in_schema=False)

# Alert Rules endpoints
app.include_router(alert_rules_router, prefix="/api/alert-rules")
app.include_router(alert_rules_router, prefix="/alert-rules", include_in_schema=False)

# Alert Events endpoints
app.include_router(alerts_router, prefix="/api/alerts")
app.include_router(alerts_router, prefix="/alerts", include_in_schema=False)
