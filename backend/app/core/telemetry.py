import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def setup_telemetry() -> None:
    """Safely initialize optional error tracking (Sentry) and OpenTelemetry tracing."""
    settings = get_settings()

    # 1. Optional Sentry Integration
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.fastapi import FastApiIntegration
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                release=f"{settings.app_name}@{settings.app_version}",
                traces_sample_rate=0.1 if settings.environment == "production" else 1.0,
                integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            )
            logger.info("Sentry error tracking initialized successfully.")
        except ImportError:
            logger.warning("SENTRY_DSN provided but 'sentry-sdk' is not installed. Skipping Sentry setup.")
        except Exception as e:
            logger.warning("Failed to initialize Sentry: %s", e)

    # 2. Optional OpenTelemetry Tracing
    if settings.enable_tracing or settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

            resource = Resource.create(
                {
                    "service.name": settings.app_name.lower(),
                    "service.version": settings.app_version,
                    "deployment.environment": settings.environment,
                }
            )
            provider = TracerProvider(resource=resource)

            if settings.otel_exporter_otlp_endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
                    provider.add_span_processor(BatchSpanProcessor(exporter))
                except Exception:
                    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            else:
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

            trace.set_tracer_provider(provider)
            logger.info("OpenTelemetry tracing initialized successfully.")
        except ImportError:
            logger.debug("OpenTelemetry packages not installed. Tracing is disabled.")
        except Exception as e:
            logger.warning("Failed to initialize OpenTelemetry: %s", e)


def get_tracer(name: str = "tether") -> Any:
    """Helper to retrieve an active tracer or a no-op fallback."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except Exception:
        class NoOpSpan:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass
            def set_attribute(self, key, value):
                pass

        class NoOpTracer:
            def start_as_current_span(self, name, *args, **kwargs):
                return NoOpSpan()

        return NoOpTracer()
