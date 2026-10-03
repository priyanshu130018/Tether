from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import sessionmaker

from app.models import CheckStatus, Job, JobStatus, MonitoringResult, Protocol, Target, TargetStatus
from app.monitoring.tcp import TcpCheckResult
from app.tasks.monitoring import run_tcp_check


def test_target_initial_state_unknown(db_engine) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Untested Target",
        hostname="10.0.0.1",
        port=80,
        protocol=Protocol.TCP,
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    assert target.status == TargetStatus.UNKNOWN
    assert target.consecutive_failures == 0
    assert target.consecutive_successes == 0
    assert target.last_checked_at is None
    session.close()


def test_successful_check_updates_status_and_counters(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Production Web",
        hostname="192.168.1.50",
        port=443,
        protocol=Protocol.TCP,
        interval_seconds=60,
        status=TargetStatus.UNKNOWN,
        consecutive_failures=3,  # Previous failures
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    job = Job(target_id=target.id, task_type="tcp", status=JobStatus.QUEUED)
    session.add(job)
    session.commit()
    session.refresh(job)

    successful_result = TcpCheckResult(success=True, latency_ms=42.5)

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.check_tcp", return_value=successful_result) as mock_tcp,
    ):
        output = run_tcp_check(target.id, job.id)
        assert output["status"] == "up"
        assert output["latency_ms"] == 42.5
        mock_tcp.assert_called_once_with("192.168.1.50", 443, 5.0)

    session.refresh(target)
    session.refresh(job)

    assert target.status == TargetStatus.UP
    assert target.consecutive_successes == 1
    assert target.consecutive_failures == 0
    assert target.last_successful_check_at is not None
    assert target.last_checked_at is not None
    assert target.next_check_at is not None

    assert job.status == JobStatus.SUCCESSFUL
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.duration_ms is not None
    assert job.worker_id is not None
    assert job.error_message is None

    results = session.query(MonitoringResult).filter(MonitoringResult.target_id == target.id).all()
    assert len(results) == 1
    assert results[0].status == CheckStatus.UP
    assert results[0].latency_ms == 42.5

    session.close()


def test_failed_check_retries_and_marks_down(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Flaky Server",
        hostname="192.168.1.99",
        port=8080,
        protocol=Protocol.TCP,
        interval_seconds=60,
        retry_count=3,
        status=TargetStatus.UP,
        consecutive_successes=5,
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    job = Job(target_id=target.id, task_type="tcp", status=JobStatus.QUEUED)
    session.add(job)
    session.commit()
    session.refresh(job)

    failed_result = TcpCheckResult(
        success=False,
        latency_ms=None,
        error_type="connection_refused",
        error_message="Connection refused by 192.168.1.99:8080",
    )

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.check_tcp", return_value=failed_result) as mock_tcp,
        patch("time.sleep") as mock_sleep,
    ):
        output = run_tcp_check(target.id, job.id)
        assert output["status"] == "down"
        assert output["error_type"] == "connection_refused"
        # Initial check (1) + 3 retries = 4 calls total
        assert mock_tcp.call_count == 4
        assert mock_sleep.call_count == 3

    session.refresh(target)
    session.refresh(job)

    assert target.status == TargetStatus.DOWN
    assert target.consecutive_failures == 1
    assert target.consecutive_successes == 0
    assert target.last_failed_check_at is not None

    assert job.status == JobStatus.FAILED
    assert job.error_message == "Connection refused by 192.168.1.99:8080"

    results = session.query(MonitoringResult).filter(MonitoringResult.target_id == target.id).all()
    assert len(results) == 1
    assert results[0].status == CheckStatus.DOWN
    assert results[0].error_type == "connection_refused"

    session.close()


def test_timeout_marks_job_timed_out(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Timing Out Server",
        hostname="10.255.255.1",
        port=80,
        protocol=Protocol.TCP,
        timeout_seconds=2.0,
        retry_count=0,
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    job = Job(target_id=target.id, task_type="tcp", status=JobStatus.QUEUED)
    session.add(job)
    session.commit()
    session.refresh(job)

    timeout_result = TcpCheckResult(
        success=False,
        latency_ms=None,
        error_type="timeout",
        error_message="Connection timed out after 2.0s",
    )

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.monitoring.check_tcp", return_value=timeout_result),
    ):
        output = run_tcp_check(target.id, job.id)
        assert output["status"] == "down"
        assert output["error_type"] == "timeout"

    session.refresh(target)
    session.refresh(job)

    assert target.status == TargetStatus.DOWN
    assert job.status == JobStatus.TIMED_OUT
    assert "timed out" in job.error_message.lower()

    session.close()
