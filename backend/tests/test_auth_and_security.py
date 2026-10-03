from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    AlertRule,
    ChannelType,
    CheckStatus,
    Job,
    JobStatus,
    MonitoringResult,
    NotificationChannel,
    Protocol,
    Role,
    Target,
    TargetStatus,
    Tenant,
    TenantMembership,
    User,
)
from app.tasks.alerts import deliver_alert_event


def create_user_with_tenant(
    db: Session,
    email: str,
    password: str = "password123",
    full_name: str = "Test User",
    role: Role = Role.OWNER,
    tenant_name: str = "Test Tenant",
    tenant_slug: str | None = None,
) -> tuple[User, Tenant, str]:
    """Helper to create a user and tenant and return a signed JWT token."""
    slug = tenant_slug or f"org-{email.split('@')[0]}"
    tenant = Tenant(name=tenant_name, slug=slug)
    db.add(tenant)
    db.flush()

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant.id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": tenant.id,
        "role": role.value,
    })
    return user, tenant, token


def test_auth_registration_and_login_flow(unauthenticated_client: TestClient, db_session: Session):
    # 1. Register a new user
    reg_payload = {
        "email": "alice@security.local",
        "password": "SuperSecretPassword123!",
        "full_name": "Alice Wonderland",
        "tenant_name": "Alice Security Corp",
    }
    reg_res = unauthenticated_client.post("/api/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == "alice@security.local"
    assert reg_data["active_tenant"]["name"] == "Alice Security Corp"
    assert reg_data["role"] == "OWNER"

    # Verify HttpOnly refresh_token cookie was set
    assert "refresh_token" in reg_res.cookies

    # 2. Duplicate registration should fail
    dup_res = unauthenticated_client.post("/api/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 3. Password too short validation
    short_pwd_res = unauthenticated_client.post("/api/auth/register", json={
        "email": "bob@short.local",
        "password": "short",
        "full_name": "Bob Short",
    })
    assert short_pwd_res.status_code == 422

    # 4. Login with valid credentials
    login_res = unauthenticated_client.post("/api/auth/login", json={
        "email": "alice@security.local",
        "password": "SuperSecretPassword123!",
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == "alice@security.local"
    token = login_data["access_token"]

    # 5. Login with invalid password
    bad_login_res = unauthenticated_client.post("/api/auth/login", json={
        "email": "alice@security.local",
        "password": "WrongPassword999!",
    })
    assert bad_login_res.status_code == 401
    assert "Invalid email or password" in bad_login_res.json()["detail"]

    # 6. GET /auth/me with authenticated token
    me_res = unauthenticated_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["email"] == "alice@security.local"
    assert me_data["role"] == "OWNER"
    assert len(me_data["memberships"]) == 1

    # 7. Token refresh
    refresh_cookie = login_res.cookies.get("refresh_token")
    ref_res = unauthenticated_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_cookie},
    )
    assert ref_res.status_code == 200
    assert "access_token" in ref_res.json()

    # 8. Logout revokes token
    logout_res = unauthenticated_client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_cookie},
    )
    assert logout_res.status_code == 200

    # Refresh after logout should fail
    ref_after_logout = unauthenticated_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_cookie},
    )
    assert ref_after_logout.status_code == 401


def test_inactive_user_cannot_authenticate(unauthenticated_client: TestClient, db_session: Session):
    user, tenant, token = create_user_with_tenant(db_session, "inactive@test.local", password="password123")
    user.is_active = False
    db_session.commit()

    # Login fails
    res = unauthenticated_client.post("/api/auth/login", json={
        "email": "inactive@test.local",
        "password": "password123",
    })
    assert res.status_code == 403

    # Authenticated request fails
    me_res = unauthenticated_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 403


def test_rbac_role_permissions(unauthenticated_client: TestClient, db_session: Session):
    # Setup Tenant and users with different roles
    tenant = Tenant(name="Acme Corp", slug="acme-corp")
    db_session.add(tenant)
    db_session.flush()

    def make_user(email: str, role: Role) -> str:
        u = User(email=email, password_hash=hash_password("password123"), full_name=email, is_active=True)
        db_session.add(u)
        db_session.flush()
        m = TenantMembership(user_id=u.id, tenant_id=tenant.id, role=role)
        db_session.add(m)
        db_session.commit()
        return create_access_token({"sub": str(u.id), "email": u.email, "tenant_id": tenant.id, "role": role.value})

    owner_token = make_user("owner@acme.com", Role.OWNER)
    admin_token = make_user("admin@acme.com", Role.ADMIN)
    member_token = make_user("member@acme.com", Role.MEMBER)
    viewer_token = make_user("viewer@acme.com", Role.VIEWER)

    # 1. VIEWER tests:
    # Viewer can view targets
    res = unauthenticated_client.get("/api/targets", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res.status_code == 200

    # Viewer CANNOT create a target
    res = unauthenticated_client.post(
        "/api/targets",
        json={"name": "Viewer Target", "hostname": "1.1.1.1", "port": 80},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res.status_code == 403

    # Viewer CANNOT create a notification channel
    res = unauthenticated_client.post(
        "/api/notification-channels",
        json={"name": "Slack", "type": "SLACK", "configuration": {"webhook_url": "https://hooks.slack.com/services/123"}},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res.status_code == 403

    # 2. MEMBER tests:
    # Member CAN create target
    res = unauthenticated_client.post(
        "/api/targets",
        json={"name": "Member Target", "hostname": "1.1.1.1", "port": 80},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 201
    created_target_id = res.json()["id"]

    # Member CAN run check
    res = unauthenticated_client.post(
        f"/api/targets/{created_target_id}/check",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 202

    # Member CANNOT delete target
    res = unauthenticated_client.delete(
        f"/api/targets/{created_target_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 403

    # Member CANNOT create notification channel
    res = unauthenticated_client.post(
        "/api/notification-channels",
        json={"name": "Slack", "type": "SLACK", "configuration": {"webhook_url": "https://hooks.slack.com/services/123"}},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 403

    # 3. ADMIN tests:
    # Admin CAN create notification channel
    res = unauthenticated_client.post(
        "/api/notification-channels",
        json={"name": "Admin Slack", "type": "SLACK", "configuration": {"webhook_url": "https://hooks.slack.com/services/123"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201
    admin_channel_id = res.json()["id"]

    # Admin CAN create alert rule
    res = unauthenticated_client.post(
        "/api/alert-rules",
        json={"target_id": created_target_id, "channel_ids": [admin_channel_id]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 201

    # Admin CAN delete target
    res = unauthenticated_client.delete(
        f"/api/targets/{created_target_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 204

    # 4. OWNER tests & Audit Logs:
    # Owner CAN view audit logs
    res = unauthenticated_client.get("/api/audit-logs", headers={"Authorization": f"Bearer {owner_token}"})
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0


def test_multi_tenancy_and_idor_isolation(unauthenticated_client: TestClient, db_session: Session):
    # Setup Tenant A and Tenant B with Owners
    user_a, tenant_a, token_a = create_user_with_tenant(db_session, "alice@tenanta.com", tenant_name="Tenant A")
    user_b, tenant_b, token_b = create_user_with_tenant(db_session, "bob@tenantb.com", tenant_name="Tenant B")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Tenant A creates a target
    res_a = unauthenticated_client.post(
        "/api/targets",
        json={"name": "Tenant A Secret Database", "hostname": "db.tenanta.internal", "port": 5432, "protocol": "tcp"},
        headers=headers_a,
    )
    assert res_a.status_code == 201
    target_a_id = res_a.json()["id"]

    # 2. Tenant B creates a target
    res_b = unauthenticated_client.post(
        "/api/targets",
        json={"name": "Tenant B Web App", "hostname": "app.tenantb.internal", "port": 443, "protocol": "https"},
        headers=headers_b,
    )
    assert res_b.status_code == 201
    target_b_id = res_b.json()["id"]

    # 3. List targets isolation
    list_a = unauthenticated_client.get("/api/targets", headers=headers_a).json()
    list_b = unauthenticated_client.get("/api/targets", headers=headers_b).json()

    assert any(t["id"] == target_a_id for t in list_a)
    assert not any(t["id"] == target_b_id for t in list_a)

    assert any(t["id"] == target_b_id for t in list_b)
    assert not any(t["id"] == target_a_id for t in list_b)

    # 4. IDOR on GET /targets/{id}
    # Tenant B tries to access Tenant A's target -> Must return 404 (prevent IDOR information leakage)
    idor_get = unauthenticated_client.get(f"/api/targets/{target_a_id}", headers=headers_b)
    assert idor_get.status_code == 404

    # 5. IDOR on PATCH /targets/{id}
    # Tenant B tries to modify Tenant A's target -> 404
    idor_patch = unauthenticated_client.patch(
        f"/api/targets/{target_a_id}",
        json={"name": "Hacked by Tenant B"},
        headers=headers_b,
    )
    assert idor_patch.status_code == 404

    # 6. IDOR on DELETE /targets/{id}
    # Tenant B tries to delete Tenant A's target -> 404
    idor_del = unauthenticated_client.delete(f"/api/targets/{target_a_id}", headers=headers_b)
    assert idor_del.status_code == 404

    # 7. IDOR on manual check /targets/{id}/check
    idor_check = unauthenticated_client.post(f"/api/targets/{target_a_id}/check", headers=headers_b)
    assert idor_check.status_code == 404

    # 8. Notification Channels Isolation
    # Tenant A creates a notification channel
    chan_a_res = unauthenticated_client.post(
        "/api/notification-channels",
        json={"name": "Tenant A Slack", "type": "SLACK", "configuration": {"webhook_url": "https://hooks.slack.com/services/AAA"}},
        headers=headers_a,
    )
    assert chan_a_res.status_code == 201
    chan_a_id = chan_a_res.json()["id"]

    # Tenant B tries to view or test Tenant A's channel -> 404
    assert unauthenticated_client.get(f"/api/notification-channels/{chan_a_id}", headers=headers_b).status_code == 404
    assert unauthenticated_client.post(f"/api/notification-channels/{chan_a_id}/test", headers=headers_b).status_code == 404
    assert unauthenticated_client.delete(f"/api/notification-channels/{chan_a_id}", headers=headers_b).status_code == 404

    # 9. Cross-Tenant Alert Rule Protection
    # Tenant B tries to create an alert rule on Tenant A's target -> 404
    rule_x_target = unauthenticated_client.post(
        "/api/alert-rules",
        json={"target_id": target_a_id, "channel_ids": []},
        headers=headers_b,
    )
    assert rule_x_target.status_code == 404

    # Tenant B tries to create an alert rule for target B using Tenant A's channel -> 400
    rule_x_channel = unauthenticated_client.post(
        "/api/alert-rules",
        json={"target_id": target_b_id, "channel_ids": [chan_a_id]},
        headers=headers_b,
    )
    assert rule_x_channel.status_code == 400

    # 10. Dashboard Summary Isolation
    summary_a = unauthenticated_client.get("/api/dashboard/summary", headers=headers_a).json()
    summary_b = unauthenticated_client.get("/api/dashboard/summary", headers=headers_b).json()

    assert summary_a["targets"] == 1
    assert summary_b["targets"] == 1


def test_team_management_members_and_roles(unauthenticated_client: TestClient, db_session: Session):
    owner, tenant, owner_token = create_user_with_tenant(db_session, "owner@teamcorp.local", tenant_name="Team Corp")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 1. Invite a new member
    invite_res = unauthenticated_client.post(
        "/api/tenants/members",
        json={"email": "newbie@teamcorp.local", "role": "MEMBER", "full_name": "Newbie Dev"},
        headers=owner_headers,
    )
    assert invite_res.status_code == 201
    membership_id = invite_res.json()["id"]

    # 2. List members
    members_res = unauthenticated_client.get("/api/tenants/members", headers=owner_headers)
    assert members_res.status_code == 200
    members = members_res.json()
    assert len(members) == 2

    # 3. Promote member to ADMIN
    patch_res = unauthenticated_client.patch(
        f"/api/tenants/members/{membership_id}",
        json={"role": "ADMIN"},
        headers=owner_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["role"] == "ADMIN"

    # 4. Remove member
    del_res = unauthenticated_client.delete(f"/api/tenants/members/{membership_id}", headers=owner_headers)
    assert del_res.status_code == 204

    # 5. Verify member removed
    members_after = unauthenticated_client.get("/api/tenants/members", headers=owner_headers).json()
    assert len(members_after) == 1


def test_worker_alert_delivery_tenant_boundary_enforcement(db_session: Session):
    # Setup Tenant A with target, rule, alert event
    user_a, tenant_a, _ = create_user_with_tenant(db_session, "worker_a@tenant.local", tenant_slug="tenant-a-worker")
    user_b, tenant_b, _ = create_user_with_tenant(db_session, "worker_b@tenant.local", tenant_slug="tenant-b-worker")

    target_a = Target(name="Target A", hostname="a.com", port=80, tenant_id=tenant_a.id)
    db_session.add(target_a)
    db_session.flush()

    # Channel belonging to Tenant B (foreign channel)
    foreign_channel = NotificationChannel(
        tenant_id=tenant_b.id,
        name="Tenant B Channel",
        type=ChannelType.WEBHOOK,
        configuration={"url": "https://api.tenantb.com/webhook"},
    )
    db_session.add(foreign_channel)
    db_session.flush()

    # Alert rule referencing foreign channel
    rule = AlertRule(
        tenant_id=tenant_a.id,
        target_id=target_a.id,
        channels=[foreign_channel],
    )
    db_session.add(rule)
    db_session.flush()

    event = AlertEvent(
        tenant_id=tenant_a.id,
        target_id=target_a.id,
        alert_rule_id=rule.id,
        event_type=AlertEventType.OUTAGE,
        status=AlertEventStatus.PENDING,
        message="Outage on target A",
    )
    db_session.add(event)
    db_session.commit()

    with patch("app.tasks.alerts.SessionLocal", return_value=db_session):
        # Deliver alert event
        res = deliver_alert_event(event.id)
        # Worker must detect mismatch: foreign channel belonging to tenant B will not be sent
        assert res["status"] in ("no_channels", "SENT")
        assert res.get("channels_count", 0) == 0
