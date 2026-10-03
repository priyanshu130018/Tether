from unittest.mock import MagicMock, patch

from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    AlertRule,
    ChannelType,
    NotificationChannel,
    Protocol,
    Target,
    TargetStatus,
)


def test_notification_channels_crud_and_masking(client):
    # 1. Create Email Channel
    res = client.post(
        "/api/notification-channels",
        json={
            "name": "DevOps Email",
            "type": "EMAIL",
            "enabled": True,
            "configuration": {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "username": "devops@example.com",
                "password": "super-secret-password",
                "to_emails": "oncall@example.com",
            },
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "DevOps Email"
    assert data["type"] == "EMAIL"
    # Verify password is masked in response!
    assert data["configuration"]["password"] == "********"
    channel_id = data["id"]

    # 2. Get Channel by ID -> verify secret is masked
    res_get = client.get(f"/api/notification-channels/{channel_id}")
    assert res_get.status_code == 200
    assert res_get.json()["configuration"]["password"] == "********"

    # 3. List Channels
    res_list = client.get("/api/notification-channels")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # 4. Update Channel
    res_update = client.patch(
        f"/api/notification-channels/{channel_id}",
        json={"name": "DevOps Email Updated"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["name"] == "DevOps Email Updated"

    # 5. Delete Channel
    res_del = client.delete(f"/api/notification-channels/{channel_id}")
    assert res_del.status_code == 204

    # Verify deleted
    res_get_404 = client.get(f"/api/notification-channels/{channel_id}")
    assert res_get_404.status_code == 404


def test_notification_channel_test_endpoint(client):
    res = client.post(
        "/api/notification-channels",
        json={
            "name": "Ops Slack",
            "type": "SLACK",
            "enabled": True,
            "configuration": {
                "webhook_url": "https://hooks.slack.com/services/T00/B00/SECRET",
            },
        },
    )
    assert res.status_code == 201
    channel_id = res.json()["id"]

    with patch("app.notifications.slack.SlackNotificationSender.send", return_value=(True, None)) as mock_send:
        test_res = client.post(f"/api/notification-channels/{channel_id}/test")
        assert test_res.status_code == 200
        assert test_res.json()["success"] is True
        mock_send.assert_called_once()


def test_alert_rules_crud_and_validation(client):
    # Create target
    target_res = client.post(
        "/api/targets",
        json={
            "name": "Production API",
            "hostname": "api.production.com",
            "port": 443,
            "protocol": "https",
        },
    )
    assert target_res.status_code == 201
    target_id = target_res.json()["id"]

    # Create notification channel
    chan_res = client.post(
        "/api/notification-channels",
        json={
            "name": "Webhook Channel",
            "type": "WEBHOOK",
            "configuration": {"url": "https://webhook.site/test"},
        },
    )
    assert chan_res.status_code == 201
    chan_id = chan_res.json()["id"]

    # 1. Create Alert Rule with channel
    rule_res = client.post(
        "/api/alert-rules",
        json={
            "target_id": target_id,
            "enabled": True,
            "failure_threshold": 3,
            "recovery_enabled": True,
            "cooldown_seconds": 1800,
            "channel_ids": [chan_id],
        },
    )
    assert rule_res.status_code == 201
    rule_data = rule_res.json()
    assert rule_data["target_id"] == target_id
    assert rule_data["failure_threshold"] == 3
    assert rule_data["channel_ids"] == [chan_id]
    rule_id = rule_data["id"]

    # 2. Get Alert Rule
    get_res = client.get(f"/api/alert-rules/{rule_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == rule_id

    # 3. List Alert Rules
    list_res = client.get(f"/api/alert-rules?target_id={target_id}")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 4. Update Alert Rule
    update_res = client.patch(
        f"/api/alert-rules/{rule_id}",
        json={"failure_threshold": 5, "cooldown_seconds": 3600},
    )
    assert update_res.status_code == 200
    assert update_res.json()["failure_threshold"] == 5
    assert update_res.json()["cooldown_seconds"] == 3600

    # 5. Non-existent channel validation
    bad_rule_res = client.post(
        "/api/alert-rules",
        json={
            "target_id": target_id,
            "channel_ids": [9999],
        },
    )
    assert bad_rule_res.status_code == 400

    # 6. Delete Alert Rule
    del_res = client.delete(f"/api/alert-rules/{rule_id}")
    assert del_res.status_code == 204


def test_alerts_history_api(client, db_session):
    # Seed alert event
    target = Target(
        name="Event Target",
        hostname="svc.local",
        port=80,
        protocol=Protocol.HTTP,
        status=TargetStatus.DOWN,
    )
    db_session.add(target)
    db_session.commit()

    event = AlertEvent(
        target_id=target.id,
        event_type=AlertEventType.OUTAGE,
        status=AlertEventStatus.SENT,
        message="Target is down",
        deduplication_key=f"outage:{target.id}:123",
        extra_data={"consecutive_failures": 3},
    )
    db_session.add(event)
    db_session.commit()

    # List alerts
    res = client.get(f"/api/alerts?target_id={target.id}")
    assert res.status_code == 200
    events = res.json()
    assert len(events) == 1
    assert events[0]["event_type"] == "OUTAGE"
    assert events[0]["status"] == "SENT"

    # Get single alert
    res_single = client.get(f"/api/alerts/{event.id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == event.id
