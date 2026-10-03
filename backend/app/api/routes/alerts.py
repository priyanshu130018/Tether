import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.auth import (
    TenantContext,
    require_role,
)
from app.core.db import get_db
from app.models import AlertEvent, AlertEventStatus, AlertEventType, Role
from app.schemas import AlertEventRead

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts"])


@router.get("", response_model=list[AlertEventRead])
@router.get("/", response_model=list[AlertEventRead], include_in_schema=False)
def list_alerts(
    target_id: int | None = None,
    event_type: AlertEventType | None = None,
    status: AlertEventStatus | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[AlertEventRead]:
    stmt = (
        select(AlertEvent)
        .options(joinedload(AlertEvent.deliveries))
        .where(AlertEvent.tenant_id == ctx.tenant.id)
        .order_by(AlertEvent.created_at.desc(), AlertEvent.id.desc())
    )
    if target_id is not None:
        stmt = stmt.where(AlertEvent.target_id == target_id)
    if event_type is not None:
        stmt = stmt.where(AlertEvent.event_type == event_type)
    if status is not None:
        stmt = stmt.where(AlertEvent.status == status)

    stmt = stmt.offset(offset).limit(limit)
    events = list(db.scalars(stmt).unique().all())
    return [AlertEventRead.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=AlertEventRead)
def get_alert(
    event_id: int,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> AlertEventRead:
    stmt = (
        select(AlertEvent)
        .options(joinedload(AlertEvent.deliveries))
        .where(AlertEvent.id == event_id, AlertEvent.tenant_id == ctx.tenant.id)
    )
    event = db.scalars(stmt).unique().first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert event {event_id} not found")
    return AlertEventRead.model_validate(event)
