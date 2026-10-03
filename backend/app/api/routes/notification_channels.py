import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    TenantContext,
    log_audit_event,
    require_role,
)
from app.core.db import get_db
from app.models import NotificationChannel, Role
from app.notifications.registry import default_notification_registry
from app.schemas import (
    NotificationChannelCreate,
    NotificationChannelRead,
    NotificationChannelUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notification-channels"])


@router.post("", response_model=NotificationChannelRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=NotificationChannelRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_notification_channel(
    payload: NotificationChannelCreate,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> NotificationChannelRead:
    channel = NotificationChannel(
        tenant_id=ctx.tenant.id,
        name=payload.name,
        type=payload.type,
        enabled=payload.enabled,
        configuration=payload.configuration,
    )
    db.add(channel)
    db.flush()

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="NOTIFICATION_CHANNEL_CREATED",
        resource_type="notification_channel",
        resource_id=str(channel.id),
        metadata={"name": channel.name, "type": channel.type.value},
    )
    db.commit()
    db.refresh(channel)
    return NotificationChannelRead.model_validate(channel)


@router.get("", response_model=list[NotificationChannelRead])
@router.get("/", response_model=list[NotificationChannelRead], include_in_schema=False)
def list_notification_channels(
    enabled_only: bool = False,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[NotificationChannelRead]:
    stmt = (
        select(NotificationChannel)
        .where(NotificationChannel.tenant_id == ctx.tenant.id)
        .order_by(NotificationChannel.id.asc())
    )
    if enabled_only:
        stmt = stmt.where(NotificationChannel.enabled.is_(True))
    channels = list(db.scalars(stmt).all())
    return [NotificationChannelRead.model_validate(c) for c in channels]


@router.get("/{channel_id}", response_model=NotificationChannelRead)
def get_notification_channel(
    channel_id: int,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> NotificationChannelRead:
    channel = db.scalars(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == ctx.tenant.id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notification channel {channel_id} not found")
    return NotificationChannelRead.model_validate(channel)


@router.patch("/{channel_id}", response_model=NotificationChannelRead)
@router.put("/{channel_id}", response_model=NotificationChannelRead, include_in_schema=False)
def update_notification_channel(
    channel_id: int,
    payload: NotificationChannelUpdate,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> NotificationChannelRead:
    channel = db.scalars(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == ctx.tenant.id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notification channel {channel_id} not found")

    if payload.name is not None:
        channel.name = payload.name
    if payload.type is not None:
        channel.type = payload.type
    if payload.enabled is not None:
        channel.enabled = payload.enabled
    if payload.configuration is not None:
        channel.configuration = payload.configuration

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="NOTIFICATION_CHANNEL_UPDATED",
        resource_type="notification_channel",
        resource_id=str(channel.id),
        metadata={"name": channel.name},
    )
    db.commit()
    db.refresh(channel)
    return NotificationChannelRead.model_validate(channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification_channel(
    channel_id: int,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    channel = db.scalars(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == ctx.tenant.id,
        )
    ).first()
    if not channel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notification channel {channel_id} not found")
    db.delete(channel)
    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="NOTIFICATION_CHANNEL_DELETED",
        resource_type="notification_channel",
        resource_id=str(channel_id),
        metadata={"name": channel.name},
    )
    db.commit()


@router.post("/{channel_id}/test", status_code=status.HTTP_200_OK)
def test_notification_channel(
    channel_id: int,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.core.rate_limit import check_rate_limit
    from app.tasks.locks import get_redis_client
    redis_client = get_redis_client()
    if not check_rate_limit(f"test_channel:{ctx.tenant.id}:{channel_id}", limit=10, window_seconds=60, redis_client=redis_client):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many channel test requests. Please wait before testing again.",
        )

    channel = db.scalars(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == ctx.tenant.id,
        )
    ).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification channel {channel_id} not found",
        )

    sender = default_notification_registry.get(channel.type)
    test_payload = {
        "event_id": 0,
        "event_type": "TEST",
        "target_id": 0,
        "target_name": "Tether Health Test",
        "target_host": "tether.local",
        "protocol": "TCP",
        "timestamp": "2026-10-02T00:00:00Z",
        "message": f"This is a test notification from Tether for notification channel '{channel.name}'.",
        "metadata": {"test": True},
    }

    success, error_msg = sender.send(channel.configuration, test_payload)
    if not success:
        return {
            "success": False,
            "message": f"Test notification failed: {error_msg}",
            "error": error_msg,
        }

    return {
        "success": True,
        "message": f"Test notification successfully sent to {channel.name}",
    }
