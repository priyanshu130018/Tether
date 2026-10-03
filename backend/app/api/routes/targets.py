from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    TenantContext,
    log_audit_event,
    require_role,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Job, JobStatus, MonitoringResult, Protocol, Role, Target, TargetStatus
from app.schemas import JobRead, ResultRead, TargetCreate, TargetRead, TargetUpdate
from app.tasks.locks import acquire_target_lock, get_redis_client, is_check_in_progress
from app.tasks.monitoring import run_monitoring_check

router = APIRouter(tags=["targets"])


@router.post("", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
def create_target(
    payload: TargetCreate,
    ctx: TenantContext = Depends(require_role(Role.MEMBER)),
    db: Session = Depends(get_db),
) -> Target:
    now = datetime.now(timezone.utc)
    target = Target(
        tenant_id=ctx.tenant.id,
        name=payload.name,
        hostname=payload.hostname or payload.host or "",
        port=payload.port or 80,
        protocol=payload.protocol,
        interval_seconds=payload.interval_seconds,
        timeout_seconds=payload.timeout_seconds,
        retry_count=payload.retry_count,
        enabled=payload.enabled,
        status=TargetStatus.UNKNOWN,
        config=payload.config,
        next_check_at=now if payload.enabled else None,
    )
    db.add(target)
    db.flush()

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="TARGET_CREATED",
        resource_type="target",
        resource_id=str(target.id),
        metadata={"name": target.name, "protocol": target.protocol.value},
    )
    db.commit()
    db.refresh(target)
    return target


@router.get("", response_model=list[TargetRead])
def list_targets(
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    protocol: Protocol | None = Query(default=None, description="Filter by protocol"),
    limit: int = Query(default=200, ge=1, le=1000, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[Target]:
    stmt = select(Target).where(Target.tenant_id == ctx.tenant.id).order_by(Target.id).offset(offset).limit(limit)
    if enabled is not None:
        stmt = stmt.where(Target.enabled == enabled)
    if protocol is not None:
        stmt = stmt.where(Target.protocol == protocol)
    return list(db.scalars(stmt).all())


@router.get("/{target_id}", response_model=TargetRead)
def get_target(
    target_id: int,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> Target:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return target


@router.patch("/{target_id}", response_model=TargetRead)
def update_target(
    target_id: int,
    payload: TargetUpdate,
    ctx: TenantContext = Depends(require_role(Role.MEMBER)),
    db: Session = Depends(get_db),
) -> Target:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "host" in update_data and "hostname" not in update_data:
        update_data["hostname"] = update_data["host"]
    update_data.pop("host", None)

    for field, value in update_data.items():
        setattr(target, field, value)

    if "enabled" in update_data:
        if update_data["enabled"]:
            target.next_check_at = datetime.now(timezone.utc)
        else:
            target.next_check_at = None

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="TARGET_UPDATED",
        resource_type="target",
        resource_id=str(target.id),
        metadata={"fields": list(update_data.keys())},
    )
    db.commit()
    db.refresh(target)
    return target


@router.post("/{target_id}/enable", response_model=TargetRead)
def enable_target(
    target_id: int,
    ctx: TenantContext = Depends(require_role(Role.MEMBER)),
    db: Session = Depends(get_db),
) -> Target:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    target.enabled = True
    target.next_check_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(target)
    return target


@router.post("/{target_id}/disable", response_model=TargetRead)
def disable_target(
    target_id: int,
    ctx: TenantContext = Depends(require_role(Role.MEMBER)),
    db: Session = Depends(get_db),
) -> Target:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    target.enabled = False
    target.next_check_at = None
    db.commit()
    db.refresh(target)
    return target


@router.post("/{target_id}/check", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_check(
    target_id: int,
    ctx: TenantContext = Depends(require_role(Role.MEMBER)),
    db: Session = Depends(get_db),
) -> Job:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

    redis_client = get_redis_client()
    from app.core.rate_limit import check_rate_limit
    if not check_rate_limit(f"manual_check:{ctx.tenant.id}:{target_id}", limit=20, window_seconds=60, redis_client=redis_client):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many manual check requests. Please wait before triggering another check.",
        )

    if is_check_in_progress(db, redis_client, target.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Monitoring check is already in progress for target {target_id}",
        )

    acquire_target_lock(redis_client, target.id)

    now = datetime.now(timezone.utc)
    protocol_name = target.protocol.value if hasattr(target.protocol, "value") else str(target.protocol)
    job = Job(
        target_id=target.id,
        tenant_id=ctx.tenant.id,
        task_type=f"{protocol_name}_check",
        status=JobStatus.QUEUED,
        created_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Advance next_check_at to respect interval
    target.next_check_at = now + timedelta(seconds=target.interval_seconds)
    db.commit()

    async_result = run_monitoring_check.apply_async(
        args=[target.id, job.id],
        queue=get_settings().celery_queue,
    )
    job.celery_task_id = async_result.id
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: int,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    db.delete(target)
    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="TARGET_DELETED",
        resource_type="target",
        resource_id=str(target_id),
        metadata={"name": target.name},
    )
    db.commit()


@router.get("/{target_id}/results", response_model=list[ResultRead])
def list_results(
    target_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[MonitoringResult]:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

    return list(
        db.scalars(
            select(MonitoringResult)
            .where(MonitoringResult.target_id == target_id)
            .order_by(MonitoringResult.timestamp.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )


@router.get("/{target_id}/latency", response_model=list[dict])
def get_target_latency_history(
    target_id: int,
    range: str = Query(default="24h", description="Time range: 1h, 6h, 24h, 7d"),
    limit: int = Query(default=200, ge=1, le=1000),
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[dict]:
    target = db.scalars(
        select(Target).where(Target.id == target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

    now = datetime.now(timezone.utc)
    normalized_range = range.lower().strip()
    delta_map = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }
    time_delta = delta_map.get(normalized_range, timedelta(hours=24))
    since = now - time_delta

    stmt = (
        select(MonitoringResult)
        .where(
            MonitoringResult.target_id == target_id,
            MonitoringResult.timestamp >= since,
            MonitoringResult.timestamp <= now,
        )
        .order_by(MonitoringResult.timestamp.asc())
    )
    raw_results = list(db.scalars(stmt).all())

    if not raw_results:
        return []

    # If count is small or 1h range, return raw chronological points
    max_desired_points = 120
    if len(raw_results) <= max_desired_points or normalized_range == "1h":
        return [
            {
                "timestamp": r.timestamp.isoformat() if r.timestamp else now.isoformat(),
                "latency_ms": r.latency_ms,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "status_code": r.status_code,
            }
            for r in raw_results
        ]

    # Server-side downsampling / bucketing for larger ranges
    total_seconds = time_delta.total_seconds()
    bucket_count = min(max_desired_points, len(raw_results))
    bucket_size_seconds = total_seconds / bucket_count

    buckets: dict[int, list[MonitoringResult]] = {}
    since_ts = since.timestamp()

    for r in raw_results:
        if not r.timestamp:
            continue
        ts = r.timestamp.timestamp() if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc).timestamp()
        bucket_idx = int((ts - since_ts) / bucket_size_seconds)
        bucket_idx = max(0, min(bucket_idx, bucket_count - 1))
        if bucket_idx not in buckets:
            buckets[bucket_idx] = []
        buckets[bucket_idx].append(r)

    downsampled: list[dict] = []
    for bucket_idx in sorted(buckets.keys()):
        bucket_items = buckets[bucket_idx]
        if not bucket_items:
            continue

        # Check if ANY item in bucket is down/failed to preserve outage visibility
        has_down = any(
            (r.status.value if hasattr(r.status, "value") else str(r.status)).lower() == "down"
            for r in bucket_items
        )

        valid_latencies = [r.latency_ms for r in bucket_items if r.latency_ms is not None]
        avg_latency = round(sum(valid_latencies) / len(valid_latencies), 1) if valid_latencies else None

        # Pick latest timestamp and status_code in this bucket
        latest_item = bucket_items[-1]
        bucket_timestamp = latest_item.timestamp.isoformat() if latest_item.timestamp else now.isoformat()
        status_code = latest_item.status_code

        downsampled.append(
            {
                "timestamp": bucket_timestamp,
                "latency_ms": avg_latency,
                "status": "down" if has_down else "up",
                "status_code": status_code,
            }
        )

    return downsampled
