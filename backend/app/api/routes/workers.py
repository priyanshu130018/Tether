import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.auth import (
    TenantContext,
    require_role,
)
from app.core.db import get_db
from app.models import Job, JobStatus, Role
from app.schemas import WorkerStatusRead
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workers"])


@router.get("", response_model=list[WorkerStatusRead])
@router.get("/", response_model=list[WorkerStatusRead], include_in_schema=False)
def list_workers(
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[WorkerStatusRead]:
    now = datetime.now(timezone.utc)
    worker_map: dict[str, WorkerStatusRead] = {}

    # 1. Query distinct worker IDs from jobs table
    stmt = select(distinct(Job.worker_id)).where(Job.worker_id.is_not(None))
    job_worker_ids = [w for w in db.scalars(stmt).all() if w]

    # 2. Check live Celery workers via inspect ping if available
    try:
        inspect = celery_app.control.inspect(timeout=0.5)
        live_workers = inspect.ping() if inspect else None
        if live_workers:
            for wid in live_workers.keys():
                if wid not in worker_map:
                    worker_map[wid] = WorkerStatusRead(
                        worker_id=str(wid),
                        status="active",
                        active_jobs=0,
                        processed_jobs=0,
                        failed_jobs=0,
                        last_seen=now,
                    )
    except Exception as exc:
        logger.debug("Could not inspect live Celery workers: %s", exc)

    for wid in job_worker_ids:
        active_jobs = (
            db.scalar(
                select(func.count(Job.id)).where(
                    Job.worker_id == wid,
                    Job.status == JobStatus.RUNNING,
                )
            )
            or 0
        )

        processed_jobs = (
            db.scalar(
                select(func.count(Job.id)).where(
                    Job.worker_id == wid,
                    Job.status == JobStatus.SUCCESSFUL,
                )
            )
            or 0
        )

        failed_jobs = (
            db.scalar(
                select(func.count(Job.id)).where(
                    Job.worker_id == wid,
                    Job.status.in_([JobStatus.FAILED, JobStatus.TIMED_OUT]),
                )
            )
            or 0
        )

        last_completed = db.scalar(
            select(func.max(Job.completed_at)).where(Job.worker_id == wid)
        )
        last_started = db.scalar(
            select(func.max(Job.started_at)).where(Job.worker_id == wid)
        )
        last_created = db.scalar(
            select(func.max(Job.created_at)).where(Job.worker_id == wid)
        )

        candidates = [t for t in (last_completed, last_started, last_created) if t is not None]
        last_seen = max(candidates) if candidates else None

        is_recent = False
        if last_seen:
            dt = last_seen.replace(tzinfo=timezone.utc) if last_seen.tzinfo is None else last_seen
            is_recent = (now - dt) <= timedelta(minutes=10)

        status_str = "active" if (active_jobs > 0 or is_recent) else "idle"

        worker_map[str(wid)] = WorkerStatusRead(
            worker_id=str(wid),
            status=status_str,
            active_jobs=active_jobs,
            processed_jobs=processed_jobs,
            failed_jobs=failed_jobs,
            last_seen=last_seen or (now if wid in worker_map else None),
        )

    return sorted(list(worker_map.values()), key=lambda w: w.worker_id)
