import logging
from datetime import datetime, timedelta, timezone

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job, JobStatus

logger = logging.getLogger(__name__)

LOCK_KEY_PREFIX = "tether:lock:target"


def get_redis_client() -> redis.Redis | None:
    settings = get_settings()
    try:
        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        logger.warning("Could not initialize Redis client for locking: %s", exc)
        return None


def acquire_target_lock(
    redis_client: redis.Redis | None,
    target_id: int,
    ttl_seconds: int | None = None,
) -> bool:
    """
    Acquire a distributed lock for the target in Redis.
    Returns True if the lock was acquired, False if already locked.
    """
    if redis_client is None:
        return True

    if ttl_seconds is None:
        ttl_seconds = get_settings().target_lock_ttl_seconds

    key = f"{LOCK_KEY_PREFIX}:{target_id}"
    try:
        acquired = bool(redis_client.set(key, "1", nx=True, ex=ttl_seconds))
        return acquired
    except Exception as exc:
        logger.warning("Redis lock acquire failed for target %s: %s", target_id, exc)
        # If Redis is unavailable, rely on database-level checks
        return True


def release_target_lock(redis_client: redis.Redis | None, target_id: int) -> None:
    """
    Release the distributed lock for the target in Redis.
    """
    if redis_client is None:
        return

    key = f"{LOCK_KEY_PREFIX}:{target_id}"
    try:
        redis_client.delete(key)
    except Exception as exc:
        logger.warning("Redis lock release failed for target %s: %s", target_id, exc)


def is_target_locked(redis_client: redis.Redis | None, target_id: int) -> bool:
    """
    Check if the target lock currently exists in Redis.
    """
    if redis_client is None:
        return False

    key = f"{LOCK_KEY_PREFIX}:{target_id}"
    try:
        return bool(redis_client.exists(key))
    except Exception as exc:
        logger.warning("Redis lock existence check failed for target %s: %s", target_id, exc)
        return False


def has_active_job(db: Session, target_id: int, stale_timeout_minutes: int = 15) -> bool:
    """
    Check if there is an active (SCHEDULED, QUEUED, or RUNNING) job for this target in PostgreSQL.
    Automatically marks stale jobs (> 15 minutes without completion) as TIMED_OUT to prevent deadlock.
    """
    stmt = (
        select(Job)
        .where(
            Job.target_id == target_id,
            Job.status.in_([JobStatus.SCHEDULED, JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .order_by(Job.created_at.desc())
    )
    active_jobs = list(db.scalars(stmt).all())
    if not active_jobs:
        return False

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(minutes=stale_timeout_minutes)

    has_valid_active = False
    for job in active_jobs:
        job_time = job.started_at or job.created_at
        if job_time.tzinfo is None:
            job_time = job_time.replace(tzinfo=timezone.utc)

        if job_time < stale_cutoff:
            logger.warning(
                "Recovering stale job %s for target %s (in %s since %s)",
                job.id,
                target_id,
                job.status.value,
                job_time,
            )
            job.status = JobStatus.TIMED_OUT
            job.completed_at = now
            job.error_message = "Job timed out due to worker unresponsiveness (stale job recovery)"
            db.commit()
        else:
            has_valid_active = True

    return has_valid_active


def is_check_in_progress(db: Session, redis_client: redis.Redis | None, target_id: int) -> bool:
    """
    Combined check: returns True if an active check is running according to DB state or Redis lock.
    """
    if has_active_job(db, target_id):
        return True
    if is_target_locked(redis_client, target_id):
        return True
    return False
