from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.metrics import MONITORING_QUEUE_DELAY_SECONDS, MONITORING_EXECUTION_DURATION_SECONDS
from app.core.security import generate_refresh_token, hash_token
from app.models import ChannelType, Job, JobStatus, NotificationChannel, RefreshToken, Role, Target, TargetStatus
from app.notifications.webhook import validate_webhook_url, WebhookNotificationSender
from app.tasks.locks import acquire_target_lock, release_target_lock
from app.tasks.monitoring import run_monitoring_check


def test_refresh_token_rotation_and_reuse_invalidation(client: TestClient, db_session):
    """
    Test that refresh token rotation works and that replay/reuse of an already-used
    refresh token revokes all active tokens for the user (anti-replay attack).
    """
    # 1. Register a user to get initial tokens
    reg_res = client.post(
        "/api/auth/register",
        json={
            "email": "sec-test@example.com",
            "password": "SecurePassword123!",
            "full_name": "Security Test User",
            "tenant_name": "Sec Corp",
        },
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    user_id = reg_data["user"]["id"]
    initial_cookie = reg_res.cookies.get("refresh_token")
    assert initial_cookie is not None

    # 2. First refresh should succeed and rotate the token
    ref_res1 = client.post(
        "/api/auth/refresh",
        json={"refresh_token": initial_cookie},
    )
    assert ref_res1.status_code == 200
    rotated_cookie = ref_res1.cookies.get("refresh_token")
    assert rotated_cookie is not None
    assert rotated_cookie != initial_cookie

    # 3. REUSE ATTACK: Present the old/used initial token again
    reuse_res = client.post(
        "/api/auth/refresh",
        json={"refresh_token": initial_cookie},
    )
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["detail"].lower()

    # 4. Verify all active refresh tokens for this user have been revoked
    active_tokens = db_session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    ).all()
    assert len(active_tokens) == 0, "All tokens should be revoked after replay attempt"


def test_ssrf_protection_blocked_targets():
    """
    Verify SSRF validator blocks localhost, loopback, AWS/GCP metadata IPs, and private CIDRs.
    """
    blocked_urls = [
        "http://127.0.0.1:8000/hook",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.1/internal-api",
        "http://192.168.1.100/webhook",
        "http://172.16.0.50/metrics",
        "http://0.0.0.0:8080/drain",
    ]

    for url in blocked_urls:
        with pytest.raises(ValueError, match="SSRF protection"):
            validate_webhook_url(url, check_dns=False)

    sender = WebhookNotificationSender()
    for url in blocked_urls:
        success, err = sender.send({"url": url}, {"event_type": "OUTAGE"})
        assert not success
        assert "SSRF protection" in (err or "")


def test_manual_check_rate_limiting(client: TestClient, db_session):
    """
    Verify rate limiting prevents rapid spamming of manual checks (429 Too Many Requests).
    """
    target = Target(
        tenant_id=1,
        name="Rate Limit Target",
        hostname="example.com",
        port=80,
        protocol="HTTP",
        interval_seconds=60,
        status=TargetStatus.UNKNOWN,
        enabled=True,
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    # Exceed limit in rapid succession
    status_codes = []
    for _ in range(25):
        resp = client.post(f"/api/targets/{target.id}/check")
        status_codes.append(resp.status_code)

    assert 429 in status_codes, "Rate limiter should return 429 after 20 requests/minute"


def test_channel_test_rate_limiting(client: TestClient, db_session):
    """
    Verify rate limiting prevents flooding notification endpoints with test dispatches.
    """
    channel = NotificationChannel(
        tenant_id=1,
        name="Rate Limit Webhook Channel",
        type="WEBHOOK",
        configuration={"url": "https://example.com/alerts"},
        enabled=True,
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)

    with patch.object(WebhookNotificationSender, "send", return_value=(True, None)):
        status_codes = []
        for _ in range(20):
            resp = client.post(f"/api/notification-channels/{channel.id}/test")
            status_codes.append(resp.status_code)

        assert 429 in status_codes, f"Channel test rate limiter should return 429 after limit. Got: {status_codes}"


def test_pagination_and_query_bounding(client: TestClient):
    """
    Verify that query limits are bounded and cannot cause denial-of-service via unbounded scans.
    """
    # Requesting a massive limit should fail validation with 422
    res = client.get("/api/targets?limit=50000")
    assert res.status_code == 422, "Query with limit > 1000 should fail schema validation with 422"

    res_valid = client.get("/api/targets?limit=50&offset=0")
    assert res_valid.status_code == 200


def test_concurrent_distributed_locking_safety(fake_redis):
    """
    Verify that distributed locking prevents two concurrent worker threads from executing the same target.
    """
    target_id = 999
    # Acquire first lock
    locked_first = acquire_target_lock(fake_redis, target_id, ttl_seconds=10)
    assert locked_first is True

    # Attempt to acquire duplicate lock for same target
    locked_second = acquire_target_lock(fake_redis, target_id, ttl_seconds=10)
    assert locked_second is False, "Second acquire must fail while first lock is held"

    # Release lock
    release_target_lock(fake_redis, target_id)

    # Now it should be acquirable again
    locked_third = acquire_target_lock(fake_redis, target_id, ttl_seconds=10)
    assert locked_third is True
    release_target_lock(fake_redis, target_id)


def test_resilience_notification_graceful_degradation():
    """
    Verify that notification delivery failure does not crash the alert engine or monitoring jobs.
    """
    sender = WebhookNotificationSender()
    # Unreachable external webhook with connection failure
    with patch("app.notifications.webhook.httpx.Client.post", side_effect=Exception("Connection refused / timed out")):
        success, err = sender.send({"url": "https://example.com/unavailable-hook"}, {"event_type": "OUTAGE"})
        assert not success
        assert "Connection refused" in (err or "")
