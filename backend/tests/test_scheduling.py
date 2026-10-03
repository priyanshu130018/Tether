from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import sessionmaker

from app.models import Job, JobStatus, Protocol, Target, TargetStatus
from app.tasks.locks import acquire_target_lock
from app.tasks.monitoring import schedule_due_targets


def test_scheduling_enabled_target(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    now = datetime.now(timezone.utc)
    target = Target(
        name="Enabled Target",
        hostname="192.168.1.1",
        port=80,
        protocol=Protocol.TCP,
        interval_seconds=60,
        enabled=True,
        next_check_at=now - timedelta(seconds=10),
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.run_monitoring_check.apply_async") as mock_apply,
    ):
        mock_apply.return_value.id = "mock-celery-1"
        result = schedule_due_targets()

        assert result["scheduled_count"] == 1
        assert target.id in result["scheduled_targets"]
        mock_apply.assert_called_once()

    session.refresh(target)
    next_check = target.next_check_at
    if next_check and next_check.tzinfo is None:
        next_check = next_check.replace(tzinfo=timezone.utc)
    assert next_check > now
    jobs = session.query(Job).filter(Job.target_id == target.id).all()
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.QUEUED
    assert jobs[0].celery_task_id == "mock-celery-1"
    session.close()


def test_scheduling_disabled_target_is_skipped(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    now = datetime.now(timezone.utc)
    target = Target(
        name="Disabled Target",
        hostname="192.168.1.2",
        port=80,
        protocol=Protocol.TCP,
        interval_seconds=60,
        enabled=False,
        next_check_at=now - timedelta(seconds=10),
    )
    session.add(target)
    session.commit()

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.run_monitoring_check.apply_async") as mock_apply,
    ):
        result = schedule_due_targets()

        assert result["scheduled_count"] == 0
        mock_apply.assert_not_called()

    jobs = session.query(Job).filter(Job.target_id == target.id).all()
    assert len(jobs) == 0
    session.close()


def test_scheduling_respects_interval(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    now = datetime.now(timezone.utc)
    # Target not due yet (next check in 120 seconds)
    target = Target(
        name="Future Target",
        hostname="192.168.1.3",
        port=80,
        protocol=Protocol.TCP,
        interval_seconds=300,
        enabled=True,
        next_check_at=now + timedelta(seconds=120),
    )
    session.add(target)
    session.commit()

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.run_monitoring_check.apply_async") as mock_apply,
    ):
        result = schedule_due_targets()
        assert result["scheduled_count"] == 0
        mock_apply.assert_not_called()

    jobs = session.query(Job).filter(Job.target_id == target.id).all()
    assert len(jobs) == 0
    session.close()


def test_scheduling_duplicate_protection_active_job(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    now = datetime.now(timezone.utc)
    target = Target(
        name="Running Target",
        hostname="192.168.1.4",
        port=80,
        protocol=Protocol.TCP,
        interval_seconds=60,
        enabled=True,
        next_check_at=now - timedelta(seconds=10),
    )
    session.add(target)
    session.commit()

    # Existing active job in RUNNING state
    active_job = Job(
        target_id=target.id,
        task_type="tcp",
        status=JobStatus.RUNNING,
        started_at=now - timedelta(seconds=5),
    )
    session.add(active_job)
    session.commit()

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.run_monitoring_check.apply_async") as mock_apply,
    ):
        result = schedule_due_targets()
        assert result["scheduled_count"] == 0
        mock_apply.assert_not_called()

    session.close()


def test_scheduling_duplicate_protection_redis_lock(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    now = datetime.now(timezone.utc)
    target = Target(
        name="Locked Target",
        hostname="192.168.1.5",
        port=80,
        protocol=Protocol.TCP,
        interval_seconds=60,
        enabled=True,
        next_check_at=now - timedelta(seconds=10),
    )
    session.add(target)
    session.commit()

    # Pre-lock target in fake Redis
    acquire_target_lock(fake_redis, target.id)

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.run_monitoring_check.apply_async") as mock_apply,
    ):
        result = schedule_due_targets()
        assert result["scheduled_count"] == 0
        mock_apply.assert_not_called()

    session.close()
