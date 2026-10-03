from collections.abc import Generator
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.rate_limit import clear_rate_limits
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Role, Tenant, TenantMembership, User


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def set(self, name: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and name in self._store:
            return False
        self._store[name] = str(value)
        return True

    def get(self, name: str) -> str | None:
        return self._store.get(name)

    def delete(self, *names: str) -> int:
        count = 0
        for n in names:
            if n in self._store:
                del self._store[n]
                count += 1
        return count

    def exists(self, *names: str) -> int:
        return sum(1 for n in names if n in self._store)

    def flushall(self) -> None:
        self._store.clear()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    clear_rate_limits()
    yield
    clear_rate_limits()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    # Seed default tenant and owner user
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestingSession() as session:
        default_tenant = Tenant(id=1, name="Default Organization", slug="default-org")
        session.add(default_tenant)
        session.flush()

        default_user = User(
            id=1,
            email="owner@default.org",
            password_hash=hash_password("password123"),
            full_name="Default Owner",
            is_active=True,
            is_verified=True,
        )
        session.add(default_user)
        session.flush()

        membership = TenantMembership(
            id=1,
            user_id=default_user.id,
            tenant_id=default_tenant.id,
            role=Role.OWNER,
        )
        session.add(membership)
        session.commit()

    return engine


@pytest.fixture
def default_auth_token() -> str:
    return create_access_token({
        "sub": "1",
        "email": "owner@default.org",
        "tenant_id": 1,
        "role": "OWNER",
    })


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def unauthenticated_client(db_engine, fake_redis) -> Generator[TestClient, None, None]:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("app.main.engine", db_engine),
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.locks.get_redis_client", return_value=fake_redis),
        patch("app.api.routes.targets.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.run_monitoring_check.apply_async") as mock_apply,
        patch("app.tasks.monitoring.run_tcp_check.apply_async") as mock_apply_tcp,
        patch("app.tasks.alerts.deliver_alert_event.apply_async") as mock_apply_alert,
    ):
        mock_apply.return_value.id = "mock-task-id-123"
        mock_apply_tcp.return_value.id = "mock-task-id-123"
        mock_apply_alert.return_value.id = "mock-alert-task-id-123"
        with TestClient(app) as test_client:
            yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def client(unauthenticated_client, default_auth_token) -> TestClient:
    unauthenticated_client.headers.update({"Authorization": f"Bearer {default_auth_token}"})
    return unauthenticated_client
