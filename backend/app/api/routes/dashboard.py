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
from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    Job,
    JobStatus,
    Role,
    Target,
    TargetStatus,
)
from app.schemas import DashboardSummaryRead

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead)
@router.get("", response_model=DashboardSummaryRead, include_in_schema=False)
def get_dashboard_summary(
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> DashboardSummaryRead:
    # Target status metrics for active tenant
    targets_total = (
        db.scalar(select(func.count(Target.id)).where(Target.tenant_id == ctx.tenant.id)) or 0
    )
    targets_up = (
        db.scalar(
            select(func.count(Target.id)).where(
                Target.tenant_id == ctx.tenant.id,
                Target.status == TargetStatus.UP,
            )
        )
        or 0
    )
    targets_down = (
        db.scalar(
            select(func.count(Target.id)).where(
                Target.tenant_id == ctx.tenant.id,
                Target.status == TargetStatus.DOWN,
            )
        )
        or 0
    )
    targets_unknown = (
        db.scalar(
            select(func.count(Target.id)).where(
                Target.tenant_id == ctx.tenant.id,
                Target.status == TargetStatus.UNKNOWN,
            )
        )
        or 0
    )

    # Active alerts (unresolved outages) for active tenant
    active_alerts = (
        db.scalar(
            select(func.count(AlertEvent.id)).where(
                AlertEvent.tenant_id == ctx.tenant.id,
                AlertEvent.event_type == AlertEventType.OUTAGE,
                AlertEvent.resolved_at.is_(None),
                AlertEvent.status.in_([AlertEventStatus.PENDING, AlertEventStatus.PROCESSING, AlertEventStatus.SENT]),
            )
        )
        or 0
    )

    # Job metrics for active tenant
    running_jobs = (
        db.scalar(
            select(func.count(Job.id))
            .join(Target, Job.target_id == Target.id)
            .where(
                Target.tenant_id == ctx.tenant.id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SCHEDULED]),
            )
        )
        or 0
    )
    total_jobs = (
        db.scalar(
            select(func.count(Job.id))
            .join(Target, Job.target_id == Target.id)
            .where(Target.tenant_id == ctx.tenant.id)
        )
        or 0
    )

    # Active workers seen within the last 15 minutes
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    recent_workers = (
        db.scalar(
            select(func.count(distinct(Job.worker_id))).where(
                Job.worker_id.is_not(None),
                Job.created_at >= cutoff,
            )
        )
        or 0
    )
    active_workers = max(1, recent_workers) if total_jobs > 0 else 1

    return DashboardSummaryRead(
        targets=targets_total,
        up=targets_up,
        down=targets_down,
        unknown=targets_unknown,
        active_alerts=active_alerts,
        running_jobs=running_jobs,
        total_jobs=total_jobs,
        active_workers=active_workers,
    )
