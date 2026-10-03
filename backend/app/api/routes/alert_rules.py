import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    TenantContext,
    log_audit_event,
    require_role,
)
from app.core.db import get_db
from app.models import AlertRule, NotificationChannel, Role, Target
from app.schemas import AlertRuleCreate, AlertRuleRead, AlertRuleUpdate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alert-rules"])


@router.post("", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_alert_rule(
    payload: AlertRuleCreate,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> AlertRuleRead:
    target = db.scalars(
        select(Target).where(Target.id == payload.target_id, Target.tenant_id == ctx.tenant.id)
    ).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {payload.target_id} not found")

    channels: list[NotificationChannel] = []
    if payload.channel_ids:
        stmt = (
            select(NotificationChannel)
            .where(
                NotificationChannel.id.in_(payload.channel_ids),
                NotificationChannel.tenant_id == ctx.tenant.id,
            )
        )
        channels = list(db.scalars(stmt).all())
        if len(channels) != len(payload.channel_ids):
            found_ids = {c.id for c in channels}
            missing = set(payload.channel_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Notification channel(s) not found or belong to another organization: {sorted(missing)}",
            )

    rule = AlertRule(
        tenant_id=ctx.tenant.id,
        target_id=payload.target_id,
        enabled=payload.enabled,
        failure_threshold=payload.failure_threshold,
        recovery_enabled=payload.recovery_enabled,
        cooldown_seconds=payload.cooldown_seconds,
        channels=channels,
    )
    db.add(rule)
    db.flush()

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="ALERT_RULE_CREATED",
        resource_type="alert_rule",
        resource_id=str(rule.id),
        metadata={"target_id": rule.target_id, "failure_threshold": rule.failure_threshold},
    )
    db.commit()
    db.refresh(rule)
    return AlertRuleRead.from_model(rule)


@router.get("", response_model=list[AlertRuleRead])
@router.get("/", response_model=list[AlertRuleRead], include_in_schema=False)
def list_alert_rules(
    target_id: int | None = None,
    enabled_only: bool = False,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> list[AlertRuleRead]:
    stmt = (
        select(AlertRule)
        .where(AlertRule.tenant_id == ctx.tenant.id)
        .order_by(AlertRule.id.asc())
    )
    if target_id is not None:
        stmt = stmt.where(AlertRule.target_id == target_id)
    if enabled_only:
        stmt = stmt.where(AlertRule.enabled.is_(True))
    rules = list(db.scalars(stmt).all())
    return [AlertRuleRead.from_model(r) for r in rules]


@router.get("/{rule_id}", response_model=AlertRuleRead)
def get_alert_rule(
    rule_id: int,
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> AlertRuleRead:
    rule = db.scalars(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == ctx.tenant.id)
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert rule {rule_id} not found")
    return AlertRuleRead.from_model(rule)


@router.patch("/{rule_id}", response_model=AlertRuleRead)
@router.put("/{rule_id}", response_model=AlertRuleRead, include_in_schema=False)
def update_alert_rule(
    rule_id: int,
    payload: AlertRuleUpdate,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> AlertRuleRead:
    rule = db.scalars(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == ctx.tenant.id)
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert rule {rule_id} not found")

    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.failure_threshold is not None:
        rule.failure_threshold = payload.failure_threshold
    if payload.recovery_enabled is not None:
        rule.recovery_enabled = payload.recovery_enabled
    if payload.cooldown_seconds is not None:
        rule.cooldown_seconds = payload.cooldown_seconds
    if payload.channel_ids is not None:
        stmt = (
            select(NotificationChannel)
            .where(
                NotificationChannel.id.in_(payload.channel_ids),
                NotificationChannel.tenant_id == ctx.tenant.id,
            )
        )
        channels = list(db.scalars(stmt).all())
        if len(channels) != len(payload.channel_ids):
            found_ids = {c.id for c in channels}
            missing = set(payload.channel_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Notification channel(s) not found or belong to another organization: {sorted(missing)}",
            )
        rule.channels = channels

    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="ALERT_RULE_UPDATED",
        resource_type="alert_rule",
        resource_id=str(rule.id),
        metadata={"target_id": rule.target_id},
    )
    db.commit()
    db.refresh(rule)
    return AlertRuleRead.from_model(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert_rule(
    rule_id: int,
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    rule = db.scalars(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == ctx.tenant.id)
    ).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Alert rule {rule_id} not found")
    db.delete(rule)
    log_audit_event(
        db,
        tenant_id=ctx.tenant.id,
        user_id=ctx.user.id,
        action="ALERT_RULE_DELETED",
        resource_type="alert_rule",
        resource_id=str(rule_id),
        metadata={"target_id": rule.target_id},
    )
    db.commit()
