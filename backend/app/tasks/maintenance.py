import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import (
    AlertEvent,
    AlertEventStatus,
    AuditLog,
    Job,
    JobStatus,
    MonitoringResult,
    RefreshToken,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.maintenance.cleanup_old_data")
def cleanup_old_data() -> dict[str, int]:
    """Periodic maintenance task to purge aged monitoring results, finished jobs, and expired tokens.
    Configurable retention windows ensure high-volume tables remain optimal.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    start_time = time.time()

    results_cutoff = now - timedelta(days=settings.result_retention_days)
    jobs_cutoff = now - timedelta(days=settings.job_retention_days)
    alerts_cutoff = now - timedelta(days=settings.alert_retention_days)
    audit_cutoff = now - timedelta(days=settings.audit_log_retention_days)

    db: Session = SessionLocal()
    purged_counts: dict[str, int] = {
        "monitoring_results": 0,
        "jobs": 0,
        "alert_events": 0,
        "refresh_tokens": 0,
        "audit_logs": 0,
    }

    try:
        # 1. Purge aged monitoring results
        res_stmt = delete(MonitoringResult).where(MonitoringResult.timestamp < results_cutoff)
        res_result = db.execute(res_stmt)
        purged_counts["monitoring_results"] = res_result.rowcount

        # 2. Purge old completed/failed jobs
        jobs_stmt = delete(Job).where(
            Job.created_at < jobs_cutoff,
            Job.status.in_([JobStatus.SUCCESSFUL, JobStatus.FAILED, JobStatus.TIMED_OUT]),
        )
        jobs_result = db.execute(jobs_stmt)
        purged_counts["jobs"] = jobs_result.rowcount

        # 3. Purge old resolved alerts
        alerts_stmt = delete(AlertEvent).where(
            AlertEvent.created_at < alerts_cutoff,
            AlertEvent.status.in_([AlertEventStatus.SENT, AlertEventStatus.SUPPRESSED, AlertEventStatus.FAILED]),
        )
        alerts_result = db.execute(alerts_stmt)
        purged_counts["alert_events"] = alerts_result.rowcount

        # 4. Purge expired or revoked refresh tokens
        tokens_stmt = delete(RefreshToken).where(
            (RefreshToken.expires_at < now) | (RefreshToken.revoked_at.is_not(None))
        )
        tokens_result = db.execute(tokens_stmt)
        purged_counts["refresh_tokens"] = tokens_result.rowcount

        # 5. Purge expired audit logs
        audit_stmt = delete(AuditLog).where(AuditLog.created_at < audit_cutoff)
        audit_result = db.execute(audit_stmt)
        purged_counts["audit_logs"] = audit_result.rowcount

        db.commit()

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Maintenance cleanup finished in %d ms: purged %s",
            elapsed_ms,
            purged_counts,
        )
        return purged_counts
    except Exception as exc:
        db.rollback()
        logger.error("Maintenance cleanup failed: %s", exc, exc_info=True)
        raise
    finally:
        db.close()
