from datetime import datetime, timezone, timedelta
from app.models import Target, MonitoringResult, TargetStatus, CheckStatus, Protocol, Tenant, User, TenantMembership, Role


def test_target_latency_history_ranges_and_downsampling(client, db_session):
    """Verifies target latency history endpoint filters correct time range and preserves chronological order."""
    # Create test user and tenant
    user = User(email="latency_tester@test.local", full_name="Latency Tester", password_hash="dummy")
    db_session.add(user)
    db_session.flush()

    tenant = Tenant(name="Latency Org", slug="latency-org")
    db_session.add(tenant)
    db_session.flush()

    membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, role=Role.ADMIN)
    db_session.add(membership)
    db_session.flush()

    target = Target(
        tenant_id=tenant.id,
        name="Latency Test Target",
        protocol=Protocol.HTTPS,
        hostname="latency.example.com",
        port=443,
        interval_seconds=60,
        timeout_seconds=5,
        status=TargetStatus.UP,
    )
    db_session.add(target)
    db_session.flush()

    now = datetime.now(timezone.utc)

    # Insert historical results across 5 days
    # Results within 30 mins (fits in 1h, 6h, 24h, 7d)
    for i in range(10):
        t = now - timedelta(minutes=i * 3)
        res = MonitoringResult(
            target_id=target.id,
            tenant_id=tenant.id,
            protocol=Protocol.HTTPS,
            status=CheckStatus.UP,
            latency_ms=20.0 + i,
            timestamp=t,
        )
        db_session.add(res)

    # Result at 3 hours ago (fits in 6h, 24h, 7d)
    res_3h = MonitoringResult(
        target_id=target.id,
        tenant_id=tenant.id,
        protocol=Protocol.HTTPS,
        status=CheckStatus.DOWN,
        latency_ms=0.0,
        timestamp=now - timedelta(hours=3),
    )
    db_session.add(res_3h)

    # Result at 18 hours ago (fits in 24h, 7d)
    res_18h = MonitoringResult(
        target_id=target.id,
        tenant_id=tenant.id,
        protocol=Protocol.HTTPS,
        status=CheckStatus.UP,
        latency_ms=35.0,
        timestamp=now - timedelta(hours=18),
    )
    db_session.add(res_18h)

    # Result at 3 days ago (fits in 7d only)
    res_3d = MonitoringResult(
        target_id=target.id,
        tenant_id=tenant.id,
        protocol=Protocol.HTTPS,
        status=CheckStatus.UP,
        latency_ms=40.0,
        timestamp=now - timedelta(days=3),
    )
    db_session.add(res_3d)

    # Result at 10 days ago (outside 7d)
    res_10d = MonitoringResult(
        target_id=target.id,
        tenant_id=tenant.id,
        protocol=Protocol.HTTPS,
        status=CheckStatus.UP,
        latency_ms=100.0,
        timestamp=now - timedelta(days=10),
    )
    db_session.add(res_10d)
    db_session.commit()

    # Get auth token
    from app.core.security import create_access_token
    token = create_access_token(data={"sub": str(user.id), "tenant_id": tenant.id, "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test 1h range
    resp_1h = client.get(f"/api/targets/{target.id}/latency?range=1h", headers=headers)
    assert resp_1h.status_code == 200
    data_1h = resp_1h.json()
    assert len(data_1h) == 10
    # Ensure chronological order (oldest first)
    timestamps_1h = [p["timestamp"] for p in data_1h]
    assert timestamps_1h == sorted(timestamps_1h)

    # 2. Test 6h range (must include the 3h ago down result)
    resp_6h = client.get(f"/api/targets/{target.id}/latency?range=6h", headers=headers)
    assert resp_6h.status_code == 200
    data_6h = resp_6h.json()
    assert len(data_6h) == 11
    down_points = [p for p in data_6h if str(p["status"]).upper() == "DOWN"]
    assert len(down_points) == 1

    # 3. Test 24h range
    resp_24h = client.get(f"/api/targets/{target.id}/latency?range=24h", headers=headers)
    assert resp_24h.status_code == 200
    data_24h = resp_24h.json()
    assert len(data_24h) == 12

    # 4. Test 7d range (must include 3d ago but exclude 10d ago)
    resp_7d = client.get(f"/api/targets/{target.id}/latency?range=7d", headers=headers)
    assert resp_7d.status_code == 200
    data_7d = resp_7d.json()
    assert len(data_7d) == 13
    assert not any(p["latency_ms"] == 100.0 for p in data_7d)
