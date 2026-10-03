import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import (
    ALERTS_CREATED_TOTAL,
    ALERTS_RECOVERED_TOTAL,
)
from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    AlertRule,
    MonitoringResult,
    Target,
    TargetStatus,
)

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def evaluate_target_alerts(
    db: Session,
    target: Target,
    latest_result: MonitoringResult,
) -> list[AlertEvent]:
    """
    Evaluates alert rules for a target following a monitoring check.
    Implements the Alert State Machine:
    - UNKNOWN -> UP: No alert.
    - UNKNOWN -> DOWN or UP -> DOWN: Triggers OUTAGE alert once consecutive_failures == failure_threshold.
    - DOWN -> DOWN: Suppresses repeated alerts unless cooldown_seconds has elapsed.
    - DOWN -> UP: Triggers RECOVERY alert if recovery_enabled is True and an outage alert was active.
    - UP -> UP: No alert.
    """
    stmt = select(AlertRule).where(AlertRule.target_id == target.id, AlertRule.enabled.is_(True))
    rules = list(db.scalars(stmt).all())
    if not rules:
        return []

    now = datetime.now(timezone.utc)
    protocol_str = (
        target.protocol.value.upper()
        if hasattr(target.protocol, "value")
        else str(target.protocol).upper()
    )
    generated_events: list[AlertEvent] = []

    for rule in rules:
        if target.status == TargetStatus.DOWN:
            # Check if we hit the failure threshold exactly
            if target.consecutive_failures == rule.failure_threshold:
                dedup_key = f"outage:{target.id}:{target.last_failed_check_at.isoformat() if target.last_failed_check_at else int(now.timestamp())}"
                
                # Check for existing event with this dedup key
                existing = db.scalars(
                    select(AlertEvent).where(AlertEvent.deduplication_key == dedup_key)
                ).first()

                if not existing:
                    err_detail = latest_result.error_message or latest_result.error_type or "Connection failed"
                    message = (
                        f"Target '{target.name}' ({protocol_str}://{target.hostname}:{target.port}) is DOWN. "
                        f"Failure threshold reached ({target.consecutive_failures} consecutive failures). "
                        f"Reason: {err_detail}"
                    )
                    event = AlertEvent(
                        tenant_id=target.tenant_id,
                        target_id=target.id,
                        alert_rule_id=rule.id,
                        event_type=AlertEventType.OUTAGE,
                        status=AlertEventStatus.PENDING,
                        message=message,
                        deduplication_key=dedup_key,
                        extra_data={
                            "protocol": protocol_str,
                            "host": target.hostname,
                            "port": target.port,
                            "consecutive_failures": target.consecutive_failures,
                            "error_type": latest_result.error_type,
                            "error_message": latest_result.error_message,
                            "latency_ms": latest_result.latency_ms,
                        },
                        created_at=now,
                    )
                    db.add(event)
                    rule.last_alerted_at = now
                    generated_events.append(event)
                    ALERTS_CREATED_TOTAL.labels(event_type="OUTAGE").inc()
                    logger.warning(
                        "[AlertEngine] Generated OUTAGE alert for target %s (Rule %s)",
                        target.id,
                        rule.id,
                    )

            elif target.consecutive_failures > rule.failure_threshold:
                # Target continues to be down; check cooldown policy
                last_alerted = _ensure_utc(rule.last_alerted_at)
                if rule.cooldown_seconds > 0 and last_alerted is not None:
                    elapsed = (now - last_alerted).total_seconds()
                    if elapsed >= rule.cooldown_seconds:
                        cooldown_bucket = int(now.timestamp() // (rule.cooldown_seconds or 1))
                        dedup_key = f"outage:{target.id}:cooldown:{cooldown_bucket}"

                        existing = db.scalars(
                            select(AlertEvent).where(AlertEvent.deduplication_key == dedup_key)
                        ).first()

                        if not existing:
                            err_detail = latest_result.error_message or latest_result.error_type or "Connection failed"
                            message = (
                                f"Target '{target.name}' ({protocol_str}://{target.hostname}:{target.port}) is STILL DOWN. "
                                f"Consecutive failures: {target.consecutive_failures}. "
                                f"Reason: {err_detail}"
                            )
                            event = AlertEvent(
                                tenant_id=target.tenant_id,
                                target_id=target.id,
                                alert_rule_id=rule.id,
                                event_type=AlertEventType.OUTAGE,
                                status=AlertEventStatus.PENDING,
                                message=message,
                                deduplication_key=dedup_key,
                                extra_data={
                                    "protocol": protocol_str,
                                    "host": target.hostname,
                                    "port": target.port,
                                    "consecutive_failures": target.consecutive_failures,
                                    "error_type": latest_result.error_type,
                                    "error_message": latest_result.error_message,
                                    "latency_ms": latest_result.latency_ms,
                                    "cooldown_repeat": True,
                                },
                                created_at=now,
                            )
                            db.add(event)
                            rule.last_alerted_at = now
                            generated_events.append(event)
                            ALERTS_CREATED_TOTAL.labels(event_type="OUTAGE").inc()
                            logger.warning(
                                "[AlertEngine] Generated repeat OUTAGE alert (cooldown elapsed) for target %s",
                                target.id,
                            )

        elif target.status == TargetStatus.UP:
            # Check for recovery: target had previously triggered an outage alert and now succeeded
            if target.consecutive_successes == 1 and rule.last_alerted_at is not None:
                if rule.recovery_enabled:
                    dedup_key = f"recovery:{target.id}:{target.last_successful_check_at.isoformat() if target.last_successful_check_at else int(now.timestamp())}"
                    
                    existing = db.scalars(
                        select(AlertEvent).where(AlertEvent.deduplication_key == dedup_key)
                    ).first()

                    if not existing:
                        latency_text = f"{latest_result.latency_ms:.1f}ms" if latest_result.latency_ms is not None else "N/A"
                        message = (
                            f"Target '{target.name}' ({protocol_str}://{target.hostname}:{target.port}) has RECOVERED. "
                            f"Latency: {latency_text}."
                        )
                        event = AlertEvent(
                            tenant_id=target.tenant_id,
                            target_id=target.id,
                            alert_rule_id=rule.id,
                            event_type=AlertEventType.RECOVERY,
                            status=AlertEventStatus.PENDING,
                            message=message,
                            deduplication_key=dedup_key,
                            extra_data={
                                "protocol": protocol_str,
                                "host": target.hostname,
                                "port": target.port,
                                "consecutive_successes": target.consecutive_successes,
                                "latency_ms": latest_result.latency_ms,
                            },
                            created_at=now,
                            resolved_at=now,
                        )
                        db.add(event)
                        rule.last_recovery_alerted_at = now
                        generated_events.append(event)
                        ALERTS_CREATED_TOTAL.labels(event_type="RECOVERY").inc()
                        ALERTS_RECOVERED_TOTAL.inc()
                        logger.info(
                            "[AlertEngine] Generated RECOVERY alert for target %s (Rule %s)",
                            target.id,
                            rule.id,
                        )

                # Reset last_alerted_at so subsequent outages will alert properly
                rule.last_alerted_at = None

    if generated_events:
        db.commit()
        for event in generated_events:
            db.refresh(event)

    return generated_events
