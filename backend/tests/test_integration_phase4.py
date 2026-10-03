from unittest.mock import patch
from sqlalchemy.orm import sessionmaker

from app.models import (
    AlertEvent,
    AlertEventType,
    AlertRule,
    ChannelType,
    CheckStatus,
    Job,
    JobStatus,
    NotificationChannel,
    Protocol,
    Target,
    TargetStatus,
)
from app.monitoring.base import ProbeResult
from app.tasks.monitoring import run_monitoring_check


def test_end_to_end_monitoring_alert_lifecycle(db_engine, fake_redis):
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    # 1. Setup Target, Channel, and AlertRule
    target = Target(
        name="Critical API",
        hostname="api.critical.internal",
        port=443,
        protocol=Protocol.HTTPS,
        status=TargetStatus.UNKNOWN,
        interval_seconds=60,
        retry_count=0,
    )
    session.add(target)
    session.commit()

    channel = NotificationChannel(
        name="Slack Outages",
        type=ChannelType.SLACK,
        enabled=True,
        configuration={"webhook_url": "https://hooks.slack.com/services/T00/B00/VALID"},
    )
    session.add(channel)
    session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        recovery_enabled=True,
        cooldown_seconds=1800,
        channels=[channel],
    )
    session.add(rule)
    session.commit()

    target_id = target.id
    session.close()

    # Define failing probe result
    failing_probe = ProbeResult(
        success=False,
        latency_ms=None,
        error_type="timeout",
        error_message="Connection timed out after 5.0s",
    )

    # Define successful probe result
    success_probe = ProbeResult(
        success=True,
        latency_ms=35.2,
        status_code=200,
    )

    dispatched_alert_events = []

    def mock_apply_async(args=None, **kwargs):
        if args:
            dispatched_alert_events.append(args[0])

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.tasks.locks.get_redis_client", return_value=fake_redis),
        patch("app.tasks.alerts.deliver_alert_event.apply_async", side_effect=mock_apply_async),
    ):
        # 1st Failure
        s1 = TestingSession()
        j1 = Job(target_id=target_id, task_type="https_check", status=JobStatus.QUEUED)
        s1.add(j1)
        s1.commit()
        j1_id = j1.id
        s1.close()

        with patch("app.monitoring.http.HttpProbe.check", return_value=failing_probe):
            run_monitoring_check(target_id, j1_id)

        s1_check = TestingSession()
        t1 = s1_check.get(Target, target_id)
        assert t1.consecutive_failures == 1
        assert t1.status == TargetStatus.DOWN
        assert len(dispatched_alert_events) == 0  # No alert yet (threshold=3)
        s1_check.close()

        # 2nd Failure
        s2 = TestingSession()
        j2 = Job(target_id=target_id, task_type="https_check", status=JobStatus.QUEUED)
        s2.add(j2)
        s2.commit()
        j2_id = j2.id
        s2.close()

        with patch("app.monitoring.http.HttpProbe.check", return_value=failing_probe):
            run_monitoring_check(target_id, j2_id)

        s2_check = TestingSession()
        t2 = s2_check.get(Target, target_id)
        assert t2.consecutive_failures == 2
        assert len(dispatched_alert_events) == 0  # Still no alert
        s2_check.close()

        # 3rd Failure -> Outage alert should be generated!
        s3 = TestingSession()
        j3 = Job(target_id=target_id, task_type="https_check", status=JobStatus.QUEUED)
        s3.add(j3)
        s3.commit()
        j3_id = j3.id
        s3.close()

        with patch("app.monitoring.http.HttpProbe.check", return_value=failing_probe):
            run_monitoring_check(target_id, j3_id)

        s3_check = TestingSession()
        t3 = s3_check.get(Target, target_id)
        assert t3.consecutive_failures == 3
        assert len(dispatched_alert_events) == 1
        event_id = dispatched_alert_events[0]
        event = s3_check.get(AlertEvent, event_id)
        assert event.event_type == AlertEventType.OUTAGE
        assert "DOWN" in event.message
        s3_check.close()

        # 4th Failure -> Cooldown active, suppressed
        s4 = TestingSession()
        j4 = Job(target_id=target_id, task_type="https_check", status=JobStatus.QUEUED)
        s4.add(j4)
        s4.commit()
        j4_id = j4.id
        s4.close()

        with patch("app.monitoring.http.HttpProbe.check", return_value=failing_probe):
            run_monitoring_check(target_id, j4_id)

        assert len(dispatched_alert_events) == 1  # No duplicate alert!

        # 5th Check -> Recovery!
        s5 = TestingSession()
        j5 = Job(target_id=target_id, task_type="https_check", status=JobStatus.QUEUED)
        s5.add(j5)
        s5.commit()
        j5_id = j5.id
        s5.close()

        with patch("app.monitoring.http.HttpProbe.check", return_value=success_probe):
            run_monitoring_check(target_id, j5_id)

        s5_check = TestingSession()
        t5 = s5_check.get(Target, target_id)
        assert t5.status == TargetStatus.UP
        assert t5.consecutive_successes == 1
        assert t5.consecutive_failures == 0
        assert len(dispatched_alert_events) == 2  # Recovery alert triggered!
        rec_event = s5_check.get(AlertEvent, dispatched_alert_events[1])
        assert rec_event.event_type == AlertEventType.RECOVERY
        assert "RECOVERED" in rec_event.message
        s5_check.close()
