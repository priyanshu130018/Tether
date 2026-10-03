from datetime import datetime, timedelta, timezone

from app.alerts.engine import evaluate_target_alerts
from app.models import (
    AlertEventType,
    AlertRule,
    CheckStatus,
    MonitoringResult,
    Protocol,
    Target,
    TargetStatus,
)


def test_alert_engine_no_rule_generates_no_events(db_session):
    target = Target(
        name="Target Without Rule",
        hostname="example.com",
        port=80,
        protocol=Protocol.HTTP,
        status=TargetStatus.DOWN,
        consecutive_failures=3,
    )
    db_session.add(target)
    db_session.commit()

    result = MonitoringResult(
        target_id=target.id,
        status=CheckStatus.DOWN,
        error_type="timeout",
        error_message="Connection timed out",
    )
    db_session.add(result)
    db_session.commit()

    events = evaluate_target_alerts(db_session, target, result)
    assert len(events) == 0


def test_alert_engine_disabled_rule_generates_no_events(db_session):
    target = Target(
        name="Target With Disabled Rule",
        hostname="example.com",
        port=80,
        protocol=Protocol.HTTP,
        status=TargetStatus.DOWN,
        consecutive_failures=3,
    )
    db_session.add(target)
    db_session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=False,
        failure_threshold=3,
    )
    db_session.add(rule)
    db_session.commit()

    result = MonitoringResult(
        target_id=target.id,
        status=CheckStatus.DOWN,
        error_type="connection_refused",
        error_message="Port closed",
    )
    db_session.add(result)
    db_session.commit()

    events = evaluate_target_alerts(db_session, target, result)
    assert len(events) == 0


def test_alert_engine_threshold_trigger(db_session):
    target = Target(
        name="Threshold Target",
        hostname="app.service.internal",
        port=443,
        protocol=Protocol.HTTPS,
        status=TargetStatus.DOWN,
        consecutive_failures=1,
    )
    db_session.add(target)
    db_session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        cooldown_seconds=1800,
    )
    db_session.add(rule)
    db_session.commit()

    res = MonitoringResult(
        target_id=target.id,
        status=CheckStatus.DOWN,
        error_type="http_status_500",
        error_message="Internal Server Error",
    )

    # 1st failure - below threshold
    target.consecutive_failures = 1
    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 0
    assert rule.last_alerted_at is None

    # 2nd failure - below threshold
    target.consecutive_failures = 2
    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 0
    assert rule.last_alerted_at is None

    # 3rd failure - reaches threshold -> trigger outage alert!
    target.consecutive_failures = 3
    target.last_failed_check_at = datetime.now(timezone.utc)
    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == AlertEventType.OUTAGE
    assert event.target_id == target.id
    assert event.alert_rule_id == rule.id
    assert "DOWN" in event.message
    assert rule.last_alerted_at is not None


def test_alert_engine_cooldown_and_suppression(db_session):
    now = datetime.now(timezone.utc)
    target = Target(
        name="Cooldown Target",
        hostname="db.local",
        port=5432,
        protocol=Protocol.TCP,
        status=TargetStatus.DOWN,
        consecutive_failures=4,
        last_failed_check_at=now,
    )
    db_session.add(target)
    db_session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        cooldown_seconds=600,
        last_alerted_at=now - timedelta(seconds=100),  # Alerted 100s ago, cooldown is 600s
    )
    db_session.add(rule)
    db_session.commit()

    res = MonitoringResult(
        target_id=target.id,
        status=CheckStatus.DOWN,
        error_type="timeout",
        error_message="Timeout",
    )

    # Within cooldown: should be suppressed
    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 0

    # Simulate time passing beyond cooldown (700 seconds)
    rule.last_alerted_at = now - timedelta(seconds=700)
    db_session.commit()

    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 1
    assert events[0].event_type == AlertEventType.OUTAGE
    assert "STILL DOWN" in events[0].message


def test_alert_engine_recovery_trigger(db_session):
    now = datetime.now(timezone.utc)
    target = Target(
        name="Recovery Target",
        hostname="api.example.com",
        port=443,
        protocol=Protocol.HTTPS,
        status=TargetStatus.UP,
        consecutive_successes=1,
        consecutive_failures=0,
        last_successful_check_at=now,
    )
    db_session.add(target)
    db_session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        recovery_enabled=True,
        last_alerted_at=now - timedelta(minutes=5),  # Was in outage
    )
    db_session.add(rule)
    db_session.commit()

    res = MonitoringResult(
        target_id=target.id,
        status=CheckStatus.UP,
        latency_ms=42.5,
    )

    # 1st success after outage -> triggers RECOVERY event
    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == AlertEventType.RECOVERY
    assert "RECOVERED" in event.message
    assert rule.last_alerted_at is None
    assert rule.last_recovery_alerted_at is not None

    # 2nd success (UP -> UP) -> no duplicate recovery event
    target.consecutive_successes = 2
    events2 = evaluate_target_alerts(db_session, target, res)
    assert len(events2) == 0


def test_alert_engine_recovery_disabled_no_event(db_session):
    now = datetime.now(timezone.utc)
    target = Target(
        name="Recovery Disabled Target",
        hostname="api.example.com",
        port=443,
        protocol=Protocol.HTTPS,
        status=TargetStatus.UP,
        consecutive_successes=1,
        consecutive_failures=0,
        last_successful_check_at=now,
    )
    db_session.add(target)
    db_session.commit()

    rule = AlertRule(
        target_id=target.id,
        enabled=True,
        failure_threshold=3,
        recovery_enabled=False,
        last_alerted_at=now - timedelta(minutes=5),
    )
    db_session.add(rule)
    db_session.commit()

    res = MonitoringResult(
        target_id=target.id,
        status=CheckStatus.UP,
        latency_ms=12.0,
    )

    events = evaluate_target_alerts(db_session, target, res)
    assert len(events) == 0
    assert rule.last_alerted_at is None
