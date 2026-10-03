import logging
import socket
import time
from datetime import datetime, timedelta, timezone
from time import perf_counter

from celery import Task
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import CheckStatus, Job, JobStatus, MonitoringResult, Target, TargetStatus
from app.monitoring.base import ProbeResult
from app.monitoring.registry import default_probe_registry
from app.monitoring.tcp import check_tcp
from app.core.metrics import (
    CELERY_TASK_DURATION_SECONDS,
    CELERY_TASKS_COMPLETED_TOTAL,
    MONITORING_CHECK_DURATION_SECONDS,
    MONITORING_CHECKS_FAILURE_TOTAL,
    MONITORING_CHECKS_SUCCESS_TOTAL,
    MONITORING_CHECKS_TOTAL,
    MONITORING_EXECUTION_DURATION_SECONDS,
    MONITORING_QUEUE_DELAY_SECONDS,
)
from app.tasks.celery_app import celery_app
from app.tasks.locks import (
    acquire_target_lock,
    get_redis_client,
    has_active_job,
    release_target_lock,
)

logger = logging.getLogger(__name__)


def calculate_backoff(attempt: int, initial_delay: float, factor: float, max_delay: float) -> float:
    return min(initial_delay * (factor ** (attempt - 1)), max_delay)


class DatabaseTask(Task):
    abstract = True


@celery_app.task(bind=True, base=DatabaseTask, name="app.tasks.monitoring.run_monitoring_check")
def run_monitoring_check(self: Task, target_id: int, job_id: int) -> dict[str, object]:
    """
    Unified monitoring check task. Dispatches to the appropriate protocol probe (TCP, HTTP, HTTPS, DNS)
    using the strategy registry, and manages retries, job states, target statuses, and persistence.
    """
    settings = get_settings()
    redis_client = get_redis_client()
    db = SessionLocal()

    try:
        job = db.get(Job, job_id)
        target = db.get(Target, target_id)
        if job is None or target is None:
            raise ValueError(f"Target or job not found: target_id={target_id}, job_id={job_id}")

        started = perf_counter()
        now_utc = datetime.now(timezone.utc)

        # Calculate and record queue delay (job creation -> execution start)
        if job.created_at:
            created_at_utc = job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=timezone.utc)
            queue_delay_sec = max(0.0, (now_utc - created_at_utc).total_seconds())
            MONITORING_QUEUE_DELAY_SECONDS.labels(task_type=job.task_type or "scheduled_check").observe(queue_delay_sec)

        job.status = JobStatus.RUNNING
        job.started_at = now_utc
        job.worker_id = socket.gethostname()
        db.commit()

        protocol_name = target.protocol.value if hasattr(target.protocol, "value") else str(target.protocol)
        logger.info("[Worker] Received check_target(%s)", target.id)
        logger.info(
            "[Worker] Checking %s://%s:%s (%s)",
            protocol_name,
            target.hostname,
            target.port,
            target.name,
        )

        def execute_check() -> ProbeResult:
            if protocol_name == "tcp":
                tcp_res = check_tcp(target.hostname, target.port, target.timeout_seconds)
                return ProbeResult(
                    success=tcp_res.success,
                    latency_ms=tcp_res.latency_ms,
                    error_type=tcp_res.error_type,
                    error_message=tcp_res.error_message,
                    metadata={"port": target.port, "host": target.hostname},
                )
            else:
                probe = default_probe_registry.get(protocol_name)
                return probe.check(target.hostname, target.port, target.timeout_seconds, target.config)

        # Retry behavior (Section 8 & 16)
        max_retries = max(0, target.retry_count)
        attempt = 1
        result = execute_check()

        while not result.success and attempt <= max_retries:
            logger.warning(
                "[Worker] Target %s (%s) DOWN - %s",
                target.id,
                protocol_name,
                result.error_type or "failed",
            )
            logger.info("[Worker] Retry %s/%s", attempt, max_retries)

            backoff_delay = calculate_backoff(
                attempt,
                settings.retry_initial_delay_seconds,
                settings.retry_backoff_factor,
                settings.retry_max_delay_seconds,
            )
            time.sleep(backoff_delay)

            attempt += 1
            result = execute_check()

        completed_at = datetime.now(timezone.utc)
        duration_ms = (perf_counter() - started) * 1000

        # Create MonitoringResult entry
        monitoring_result = MonitoringResult(
            target_id=target.id,
            timestamp=completed_at,
            protocol=target.protocol,
            status=CheckStatus.UP if result.success else CheckStatus.DOWN,
            latency_ms=result.latency_ms,
            status_code=result.status_code,
            error_type=result.error_type,
            error_message=result.error_message,
            extra_data=result.metadata,
            worker_id=job.worker_id,
        )
        db.add(monitoring_result)

        # Update Job
        if result.success:
            job.status = JobStatus.SUCCESSFUL
            job.error_message = None
        else:
            job.status = JobStatus.TIMED_OUT if result.error_type == "timeout" else JobStatus.FAILED
            job.error_message = result.error_message

        job.completed_at = completed_at
        job.duration_ms = round(duration_ms, 2)

        # Update Target status & consecutive failure tracking (Section 11 & 12)
        if result.success:
            target.status = TargetStatus.UP
            target.consecutive_successes += 1
            target.consecutive_failures = 0
            target.last_successful_check_at = completed_at
            logger.info(
                "[Worker] Target %s UP - %.1fms",
                target.id,
                result.latency_ms or 0.0,
            )
            logger.info("[Worker] Job %s completed", job.id)
            MONITORING_CHECKS_TOTAL.labels(protocol=protocol_name, status="UP").inc()
            MONITORING_CHECKS_SUCCESS_TOTAL.labels(protocol=protocol_name).inc()
        else:
            target.status = TargetStatus.DOWN
            target.consecutive_failures += 1
            target.consecutive_successes = 0
            target.last_failed_check_at = completed_at
            logger.warning(
                "[Worker] Target %s DOWN - %s",
                target.id,
                result.error_type or "failed",
            )
            logger.info("[Worker] Job %s completed with status %s", job.id, job.status.value)
            MONITORING_CHECKS_TOTAL.labels(protocol=protocol_name, status="DOWN").inc()
            MONITORING_CHECKS_FAILURE_TOTAL.labels(protocol=protocol_name, error_type=result.error_type or "unknown").inc()

        duration_sec = duration_ms / 1000.0
        MONITORING_CHECK_DURATION_SECONDS.labels(protocol=protocol_name).observe(duration_sec)
        MONITORING_EXECUTION_DURATION_SECONDS.labels(protocol=protocol_name).observe(duration_sec)
        CELERY_TASKS_COMPLETED_TOTAL.labels(task_name="run_monitoring_check").inc()
        CELERY_TASK_DURATION_SECONDS.labels(task_name="run_monitoring_check").observe(duration_sec)

        # Update Target next run scheduling timestamps (Section 6)
        target.last_checked_at = completed_at
        target.next_check_at = completed_at + timedelta(seconds=target.interval_seconds)

        db.commit()

        # Evaluate alert rules and trigger async notification tasks if state transition warrants an alert
        try:
            from app.alerts.engine import evaluate_target_alerts
            from app.tasks.alerts import deliver_alert_event

            alert_events = evaluate_target_alerts(db, target, monitoring_result)
            for evt in alert_events:
                deliver_alert_event.apply_async(
                    args=[evt.id],
                    queue=settings.celery_queue,
                )
        except Exception as alert_exc:
            logger.exception("[Worker] Alert evaluation error for target %s: %s", target.id, alert_exc)

        return result.to_dict()

    except Exception as exc:
        db.rollback()
        completed_at = datetime.now(timezone.utc)
        if "job" in locals() and job is not None:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            job.completed_at = completed_at
            if "started" in locals():
                job.duration_ms = round((perf_counter() - started) * 1000, 2)
            db.commit()
        logger.exception("[Worker] Unexpected failure during monitoring check for target_id=%s", target_id)
        raise
    finally:
        release_target_lock(redis_client, target_id)
        db.close()


@celery_app.task(bind=True, base=DatabaseTask, name="app.tasks.monitoring.run_tcp_check")
def run_tcp_check(self: Task, target_id: int, job_id: int) -> dict[str, object]:
    """
    Backward-compatible entry point for TCP checks.
    """
    return run_monitoring_check(target_id, job_id)


@celery_app.task(name="app.tasks.monitoring.schedule_due_targets")
def schedule_due_targets() -> dict[str, object]:
    """
    Periodic scheduler task run by Celery Beat.
    Determines which enabled targets need checking, applies duplicate job protection,
    and dispatches check jobs to Celery workers.
    """
    settings = get_settings()
    redis_client = get_redis_client()
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    scheduled_targets: list[int] = []

    try:
        stmt = (
            select(Target)
            .where(
                Target.enabled.is_(True),
                or_(Target.next_check_at.is_(None), Target.next_check_at <= now),
            )
            .order_by(Target.next_check_at.nulls_first(), Target.id)
        )
        due_targets = list(db.scalars(stmt).all())

        for target in due_targets:
            if not target.enabled:
                continue

            if has_active_job(db, target.id):
                logger.info(
                    "[Beat] Target %s has an active check in progress, skipping duplicate job",
                    target.id,
                )
                continue

            if not acquire_target_lock(redis_client, target.id):
                logger.info(
                    "[Beat] Target %s is locked in Redis, skipping duplicate job",
                    target.id,
                )
                continue

            protocol_name = target.protocol.value if hasattr(target.protocol, "value") else str(target.protocol)
            logger.info(
                "[Beat] Scheduling target %s (%s://%s:%s)",
                target.id,
                protocol_name,
                target.hostname,
                target.port,
            )

            job = Job(
                target_id=target.id,
                task_type=f"{protocol_name}_check",
                status=JobStatus.QUEUED,
                created_at=now,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Advance next_check_at to avoid re-triggering while task is queued
            target.next_check_at = now + timedelta(seconds=target.interval_seconds)
            db.commit()

            async_result = run_monitoring_check.apply_async(
                args=[target.id, job.id],
                queue=settings.celery_queue,
            )
            job.celery_task_id = async_result.id
            db.commit()

            scheduled_targets.append(target.id)

        return {
            "scheduled_count": len(scheduled_targets),
            "scheduled_targets": scheduled_targets,
            "timestamp": now.isoformat(),
        }
    finally:
        db.close()
