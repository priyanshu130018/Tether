import logging
from datetime import datetime, timezone
from typing import Any

from celery import Task
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.metrics import (
    NOTIFICATION_DELIVERIES_TOTAL,
    NOTIFICATION_DELIVERY_DURATION_SECONDS,
    NOTIFICATION_DELIVERY_FAILURES_TOTAL,
)
from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertRule,
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    Target,
)
from app.notifications.registry import default_notification_registry
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.alerts.deliver_alert_event",
)
def deliver_alert_event(self: Task, alert_event_id: int) -> dict[str, Any]:
    """
    Asynchronously delivers an alert event to all notification channels attached to its alert rule.
    Updates notification delivery records and event delivery status.
    """
    db = SessionLocal()
    try:
        event = db.get(AlertEvent, alert_event_id)
        if not event:
            logger.error("[AlertTask] AlertEvent %s not found", alert_event_id)
            return {"status": "not_found", "event_id": alert_event_id}

        target = db.get(Target, event.target_id)
        if not target:
            logger.error("[AlertTask] Target %s for AlertEvent %s not found", event.target_id, alert_event_id)
            return {"status": "target_not_found", "event_id": alert_event_id}

        # Gather channels from the associated alert rule, ensuring channel.tenant_id matches event.tenant_id
        channels: list[NotificationChannel] = []
        if event.alert_rule_id:
            rule = db.get(AlertRule, event.alert_rule_id)
            if rule and rule.tenant_id == event.tenant_id and rule.channels:
                channels = [c for c in rule.channels if c.enabled and c.tenant_id == event.tenant_id]

        if not channels:
            logger.info("[AlertTask] No enabled notification channels attached to AlertEvent %s", alert_event_id)
            event.status = AlertEventStatus.SENT
            db.commit()
            return {"status": "no_channels", "event_id": alert_event_id}

        event.status = AlertEventStatus.PROCESSING
        db.commit()

        protocol_str = (
            target.protocol.value.upper()
            if hasattr(target.protocol, "value")
            else str(target.protocol).upper()
        )
        event_type_str = (
            event.event_type.value
            if hasattr(event.event_type, "value")
            else str(event.event_type)
        )

        payload = {
            "event_id": event.id,
            "event_type": event_type_str,
            "target_id": target.id,
            "target_name": target.name,
            "target_host": target.hostname,
            "protocol": protocol_str,
            "timestamp": event.created_at.isoformat() if event.created_at else datetime.now(timezone.utc).isoformat(),
            "message": event.message,
            "metadata": event.extra_data or {},
        }

        any_succeeded = False
        all_failed = True

        for channel in channels:
            # Find or create delivery record
            stmt = select(NotificationDelivery).where(
                NotificationDelivery.alert_event_id == event.id,
                NotificationDelivery.channel_id == channel.id,
            )
            delivery = db.scalars(stmt).first()
            if not delivery:
                delivery = NotificationDelivery(
                    alert_event_id=event.id,
                    channel_id=channel.id,
                    status=DeliveryStatus.PENDING,
                    attempt_count=0,
                )
                db.add(delivery)
                db.flush()

            delivery.attempt_count += 1
            delivery.last_attempt_at = datetime.now(timezone.utc)

            channel_type_str = channel.type.value if hasattr(channel.type, "value") else str(channel.type)
            start_delivery = datetime.now(timezone.utc)
            try:
                sender = default_notification_registry.get(channel.type)
                success, error_msg = sender.send(channel.configuration, payload)
                elapsed_sec = (datetime.now(timezone.utc) - start_delivery).total_seconds()
                NOTIFICATION_DELIVERY_DURATION_SECONDS.labels(channel_type=channel_type_str).observe(elapsed_sec)
                if success:
                    delivery.status = DeliveryStatus.SENT
                    delivery.last_error = None
                    any_succeeded = True
                    all_failed = False
                    NOTIFICATION_DELIVERIES_TOTAL.labels(channel_type=channel_type_str, status="SENT").inc()
                else:
                    delivery.status = DeliveryStatus.FAILED
                    delivery.last_error = error_msg
                    NOTIFICATION_DELIVERIES_TOTAL.labels(channel_type=channel_type_str, status="FAILED").inc()
                    NOTIFICATION_DELIVERY_FAILURES_TOTAL.labels(channel_type=channel_type_str).inc()
            except Exception as exc:
                elapsed_sec = (datetime.now(timezone.utc) - start_delivery).total_seconds()
                NOTIFICATION_DELIVERY_DURATION_SECONDS.labels(channel_type=channel_type_str).observe(elapsed_sec)
                NOTIFICATION_DELIVERIES_TOTAL.labels(channel_type=channel_type_str, status="FAILED").inc()
                NOTIFICATION_DELIVERY_FAILURES_TOTAL.labels(channel_type=channel_type_str).inc()
                delivery.status = DeliveryStatus.FAILED
                delivery.last_error = str(exc)
                logger.warning(
                    "[AlertTask] Delivery error for channel %s (%s): %s",
                    channel.id,
                    channel.name,
                    exc,
                )

        if any_succeeded:
            event.status = AlertEventStatus.SENT
        elif all_failed and channels:
            event.status = AlertEventStatus.FAILED

        db.commit()
        return {
            "status": event.status.value if hasattr(event.status, "value") else str(event.status),
            "event_id": alert_event_id,
            "channels_count": len(channels),
        }

    except Exception as exc:
        db.rollback()
        logger.exception("[AlertTask] Unexpected error delivering alert %s: %s", alert_event_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.tasks.alerts.send_test_notification")
def send_test_notification(channel_id: int) -> dict[str, Any]:
    """
    Sends a test notification to a specific notification channel.
    """
    db = SessionLocal()
    try:
        channel = db.get(NotificationChannel, channel_id)
        if not channel:
            return {"success": False, "error": f"Channel {channel_id} not found"}

        test_payload = {
            "event_id": 0,
            "event_type": "TEST",
            "target_id": 0,
            "target_name": "Tether Health Test",
            "target_host": "tether.local",
            "protocol": "TCP",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"This is a test notification from Tether for notification channel '{channel.name}'.",
            "metadata": {"test": True},
        }

        sender = default_notification_registry.get(channel.type)
        success, error_msg = sender.send(channel.configuration, test_payload)
        return {"success": success, "error": error_msg}
    finally:
        db.close()
