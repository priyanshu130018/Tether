from unittest.mock import patch, MagicMock
from app.models import Tenant, User, TenantMembership, Role
from app.core.security import create_access_token


def test_health_endpoint_healthy_state(client):
    """Verifies that /health returns 200 with healthy state when DB and Redis are working."""
    with patch("redis.Redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_from_url.return_value = mock_redis

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["healthy", "degraded"]
        assert data["database"] == "healthy"


def test_health_endpoint_degraded_when_database_fails(client):
    """Verifies that /health returns degraded/unhealthy status when database ping fails."""
    from app.main import app
    from app.core.db import get_db

    def mock_get_db():
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Database connection error")
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["database"] == "unhealthy"
        assert data["status"] in ["degraded", "unhealthy"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_endpoint_degraded_when_redis_fails(client):
    """Verifies that /health returns degraded status when redis ping fails."""
    with patch("redis.Redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Redis connection refused")
        mock_from_url.return_value = mock_redis

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["redis"] == "unhealthy"
        assert data["status"] in ["degraded", "unhealthy"]


def test_workers_endpoint_with_auth(client, db_session):
    """Verifies that /api/v1/workers returns live worker status without fake default fallbacks."""
    user = User(email="worker_checker@test.local", full_name="Worker Checker", password_hash="dummy")
    db_session.add(user)
    db_session.flush()

    tenant = Tenant(name="Worker Org", slug="worker-org")
    db_session.add(tenant)
    db_session.flush()

    membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, role=Role.ADMIN)
    db_session.add(membership)
    db_session.commit()

    token = create_access_token(data={"sub": str(user.id), "tenant_id": tenant.id, "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.tasks.celery_app.celery_app.control.inspect") as mock_inspect:
        mock_insp = MagicMock()
        mock_insp.ping.return_value = {
            "celery@node-alpha": {"ok": "pong"},
            "celery@node-beta": {"ok": "pong"},
        }
        mock_insp.active.return_value = {
            "celery@node-alpha": [1, 2],
            "celery@node-beta": [],
        }
        mock_insp.stats.return_value = {
            "celery@node-alpha": {"total": {"tasks.check": 50}},
            "celery@node-beta": {"total": {"tasks.check": 25}},
        }
        mock_inspect.return_value = mock_insp

        resp = client.get("/api/workers", headers=headers)
        assert resp.status_code == 200
        workers = resp.json()
        assert len(workers) == 2
        worker_ids = {w["worker_id"] for w in workers}
        assert "celery@node-alpha" in worker_ids
        assert "celery@node-beta" in worker_ids
