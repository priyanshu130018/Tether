from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    TenantContext,
    require_role,
)
from app.core.db import get_db
from app.models import Job, JobStatus, Role, Target
from app.schemas import JobRead

router = APIRouter(tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    target_id: int | None = Query(default=None, description="Filter by target ID"),
    status: JobStatus | None = Query(default=None, description="Filter by job status"),
    task_type: str | None = Query(default=None, description="Filter by task type"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of jobs to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[Job]:
    stmt = (
        select(Job)
        .join(Target, Job.target_id == Target.id)
        .where(Target.tenant_id == ctx.tenant.id)
        .order_by(Job.created_at.desc())
    )
    if target_id is not None:
        stmt = stmt.where(Job.target_id == target_id)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    if task_type is not None:
        stmt = stmt.where(Job.task_type == task_type)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Job:
    stmt = (
        select(Job)
        .join(Target, Job.target_id == Target.id)
        .where(Job.id == job_id, Target.tenant_id == ctx.tenant.id)
    )
    job = db.scalars(stmt).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
