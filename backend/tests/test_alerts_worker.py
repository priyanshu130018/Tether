from unittest.mock import MagicMock, patch
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    AlertRule,
    ChannelType,
    DeliveryStatus,
    NotificationChannel,
    NotificationDelivery,
    Protocol,
    Target,
    TargetStatus,
)
from app.tasks.alerts import deliver_alert_event, send_test_notification


def test_deliver_alert_event_success(db_engine):
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Worker Alert Target",
        hostname="api.internal",
        port=8080,
        protocol=Protocol.HTTP,
        status=TargetStatus.DOWN,
    )
    session.add(target)
    session.commit()

    channel = NotificationChannel(
        name="Team Slack",
        type=ChannelType.SLACK,
        enabled=True,
        configuration={"webhook_url": "https://hooks.slack.com/services/T00/B00/ABC"},
    )
    session.add(channel)
    session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        channels=[channel],
    )
    session.add(rule)
    session.commit()

    event = AlertEvent(
        target_id=target.id,
        alert_rule_id=rule.id,
        event_type=AlertEventType.OUTAGE,
        status=AlertEventStatus.PENDING,
        message="Target is unreachable",
        deduplication_key=f"outage:{target.id}:test",
        extra_data={"consecutive_failures": 3},
    )
    session.add(event)
    session.commit()
    event_id = event.id
    session.close()

    with (
        patch("app.tasks.alerts.SessionLocal", TestingSession),
        patch("app.notifications.slack.SlackNotificationSender.send", return_value=(True, None)) as mock_send,
    ):
        result = deliver_alert_event(event_id)
        assert result["status"] == "SENT"
        assert result["channels_count"] == 1
        mock_send.assert_called_once()

    check_session = TestingSession()
    updated_event = check_session.get(AlertEvent, event_id)
    assert updated_event is not None
    assert updated_event.status == AlertEventStatus.SENT

    stmt = select(NotificationDelivery).where(NotificationDelivery.alert_event_id == event_id)
    deliveries = list(check_session.scalars(stmt).all())
    assert len(deliveries) == 1
    assert deliveries[0].status == DeliveryStatus.SENT
    assert deliveries[0].channel_id == channel.id
    check_session.close()


def test_deliver_alert_event_failure(db_engine):
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Failing Channel Target",
        hostname="api.internal",
        port=8080,
        protocol=Protocol.HTTP,
        status=TargetStatus.DOWN,
    )
    session.add(target)
    session.commit()

    channel = NotificationChannel(
        name="Failing Webhook",
        type=ChannelType.WEBHOOK,
        enabled=True,
        configuration={"url": "https://invalid.endpoint/webhook"},
    )
    session.add(channel)
    session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        channels=[channel],
    )
    session.add(rule)
    session.commit()

    event = AlertEvent(
        target_id=target.id,
        alert_rule_id=rule.id,
        event_type=AlertEventType.OUTAGE,
        status=AlertEventStatus.PENDING,
        message="Target is unreachable",
    )
    session.add(event)
    session.commit()
    event_id = event.id
    session.close()

    with (
        patch("app.tasks.alerts.SessionLocal", TestingSession),
        patch(
            "app.notifications.webhook.WebhookNotificationSender.send",
            return_value=(False, "Connection refused: 502 Bad Gateway"),
        ),
    ):
        result = deliver_alert_event(event_id)
        assert result["status"] == "FAILED"

    check_session = TestingSession()
    updated_event = check_session.get(AlertEvent, event_id)
    assert updated_event is not None
    assert updated_event.status == AlertEventStatus.FAILED

    stmt = select(NotificationDelivery).where(NotificationDelivery.alert_event_id == event_id)
    deliveries = list(check_session.scalars(stmt).all())
    assert len(deliveries) == 1
    assert deliveries[0].status == DeliveryStatus.FAILED
    assert "502 Bad Gateway" in deliveries[0].last_error
    check_session.close()


def test_send_test_notification_task(db_engine):
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    channel = NotificationChannel(
        name="Test Task Channel",
        type=ChannelType.SLACK,
        enabled=True,
        configuration={"webhook_url": "https://hooks.slack.com/services/T00/B00/TEST"},
    )
    session.add(channel)
    session.commit()
    channel_id = channel.id
    session.close()

    with (
        patch("app.tasks.alerts.SessionLocal", TestingSession),
        patch("app.notifications.slack.SlackNotificationSender.send", return_value=(True, None)) as mock_send,
    ):
        res = send_test_notification(channel_id)
        assert res["success"] is True
        mock_send.assert_called_once()
