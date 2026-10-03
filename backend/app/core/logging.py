import contextvars
import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings

# Context variable holding correlation ID for the active request / background task
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# Regex pattern for sanitizing potential sensitive keys in logs
SENSITIVE_PATTERNS = [
    re.compile(r"(password|token|secret|authorization|bearer|cookie|webhook_url)", re.IGNORECASE),
]


def get_request_id() -> str:
    return request_id_ctx.get()


def set_request_id(req_id: str) -> None:
    request_id_ctx.set(req_id)


def sanitize_sensitive_data(data: Any) -> Any:
    """Recursively mask sensitive values in dictionaries and lists."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(p.search(str(k)) for p in SENSITIVE_PATTERNS):
                sanitized[k] = "********"
            else:
                sanitized[k] = sanitize_sensitive_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_sensitive_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    """Production JSON log formatter conforming to standard observability schema."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "tether-api",
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject correlation ID if present
        req_id = get_request_id()
        if req_id:
            log_entry["request_id"] = req_id

        # Include custom extra fields
        if hasattr(record, "event"):
            log_entry["event"] = record.event
        if hasattr(record, "target_id"):
            log_entry["target_id"] = record.target_id
        if hasattr(record, "protocol"):
            log_entry["protocol"] = record.protocol
        if hasattr(record, "status"):
            log_entry["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_entry.update(sanitize_sensitive_data(record.extra_fields))

        # Include exception trace if present (safely formatted)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class TextFormatter(logging.Formatter):
    """Human-readable text log formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        req_id = get_request_id()
        prefix = f"[{req_id}] " if req_id else ""
        record.msg = f"{prefix}{record.msg}"
        return super().format(record)


def setup_logging() -> None:
    """Initialize structured logging based on environment configuration."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    if settings.log_format == "json" or settings.environment == "production":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            TextFormatter(fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )

    root_logger.addHandler(console_handler)

    # Suppress excessive verbosity from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
