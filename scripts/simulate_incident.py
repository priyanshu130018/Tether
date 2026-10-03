"""Tether Incident Lifecycle Simulator
Simulates: Target UP -> Outage (Threshold reached) -> DOWN -> Outage Alert -> Target Recovers -> Recovery Alert.
"""

from pathlib import Path
import sys
import time
from datetime import datetime, timezone

# Ensure backend app package is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.alerts.engine import evaluate_target_alerts
from app.core.config import get_settings
from app.core.db import Base
from app.models import (
    AlertEventType,
    AlertRule,
    ChannelType,
    CheckStatus,
    MonitoringResult,
    NotificationChannel,
    Protocol,
    Target,
    TargetStatus,
    Tenant,
)


def simulate_incident_lifecycle():
    print("=" * 75)
    print("TETHER INCIDENT LIFECYCLE SIMULATION")
    print("=" * 75)

    # In-memory test engine for isolated repeatable simulation
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 1. Provision Tenant
        tenant = Tenant(id=1, name="Production Ops", slug="production-ops")
        db.add(tenant)
        db.flush()

        # 2. Configure Monitored Target
        target = Target(
            id=101,
            tenant_id=1,
            name="Primary API Gateway",
            hostname="gateway.internal.corp",
            port=443,
            protocol=Protocol.HTTPS,
            status=TargetStatus.UP,
            interval_seconds=30,
            timeout_seconds=3.0,
            consecutive_failures=0,
            consecutive_successes=15,
        )
        db.add(target)

        # 3. Configure Alert Rule & Channel
        channel = NotificationChannel(
            id=1,
            tenant_id=1,
            name="DevOps Slack",
            type=ChannelType.SLACK,
            configuration={"webhook_url": "https://hooks.slack.com/services/SIMULATED/KEY"},
        )
        db.add(channel)
        db.flush()

        rule = AlertRule(
            id=1,
            tenant_id=1,
            target_id=target.id,
            failure_threshold=3,
            recovery_enabled=True,
            cooldown_seconds=300,
            channels=[channel],
        )
        db.add(rule)
        db.commit()

        print(f"\n[INIT] Target '{target.name}' is healthy (Status: {target.status.value}, Successes: {target.consecutive_successes})")
        print(f"[CONFIG] Alert Rule active: Failure Threshold = {rule.failure_threshold}, Recovery Enabled = {rule.recovery_enabled}")

        # --- Phase A: Initial Failures (Below Threshold) ---
        print("\n--- Phase A: First 2 Check Failures (Below Threshold 3) ---")
        for attempt in (1, 2):
            target.consecutive_failures = attempt
            target.consecutive_successes = 0
            target.status = TargetStatus.DOWN
            res = MonitoringResult(
                tenant_id=1,
                target_id=target.id,
                protocol=Protocol.HTTPS,
                status=CheckStatus.DOWN,
                error_type="connect_timeout",
                error_message="TCP connection to gateway.internal.corp:443 timed out after 3.0s",
                timestamp=datetime.now(timezone.utc),
            )
            db.add(res)
            db.flush()

            events = evaluate_target_alerts(db, target, res)
            print(f"  Attempt {attempt}: Status={target.status.value}, Failures={target.consecutive_failures} -> Alerts Generated: {len(events)}")
            assert len(events) == 0, "No alerts should trigger before reaching failure threshold"

        # --- Phase B: Third Failure (Threshold Reached -> Outage Triggered) ---
        print("\n--- Phase B: 3rd Consecutive Failure (Threshold Reached) ---")
        target.consecutive_failures = 3
        target.status = TargetStatus.DOWN
        target.last_failed_check_at = datetime.now(timezone.utc)
        res3 = MonitoringResult(
            tenant_id=1,
            target_id=target.id,
            protocol=Protocol.HTTPS,
            status=CheckStatus.DOWN,
            error_type="connect_timeout",
            error_message="TCP connection to gateway.internal.corp:443 timed out after 3.0s",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(res3)
        db.flush()

        events = evaluate_target_alerts(db, target, res3)
        print(f"  Attempt 3: Status={target.status.value}, Failures={target.consecutive_failures} -> Outage Alerts Generated: {len(events)}")
        assert len(events) == 1, "Expected 1 Outage alert event"
        outage_event = events[0]
        assert outage_event.event_type == AlertEventType.OUTAGE
        print(f"  [ALERT FIRED] Event ID {outage_event.id}: '{outage_event.message}'")

        # --- Phase C: Fourth Failure (Suppressed by Deduplication) ---
        print("\n--- Phase C: 4th Failure while already DOWN (Cooldown Active) ---")
        target.consecutive_failures = 4
        res4 = MonitoringResult(
            tenant_id=1,
            target_id=target.id,
            protocol=Protocol.HTTPS,
            status=CheckStatus.DOWN,
            error_type="connect_timeout",
            error_message="TCP connection timed out",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(res4)
        db.flush()

        events = evaluate_target_alerts(db, target, res4)
        print(f"  Attempt 4: Status={target.status.value}, Failures={target.consecutive_failures} -> Alerts Generated: {len(events)} (Suppressed)")
        assert len(events) == 0, "Repeated outage alert should be suppressed by cooldown"

        # --- Phase D: Target Recovers -> Recovery Alert Fired ---
        print("\n--- Phase D: Target Recovers Successfully ---")
        target.status = TargetStatus.UP
        target.consecutive_successes = 1
        target.consecutive_failures = 0
        target.last_successful_check_at = datetime.now(timezone.utc)
        res5 = MonitoringResult(
            tenant_id=1,
            target_id=target.id,
            protocol=Protocol.HTTPS,
            status=CheckStatus.UP,
            latency_ms=28.4,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(res5)
        db.flush()

        events = evaluate_target_alerts(db, target, res5)
        print(f"  Recovery Check: Status={target.status.value}, Successes={target.consecutive_successes} -> Recovery Alerts: {len(events)}")
        assert len(events) == 1, "Expected 1 Recovery alert event"
        rec_event = events[0]
        assert rec_event.event_type == AlertEventType.RECOVERY
        print(f"  [RECOVERY FIRED] Event ID {rec_event.id}: '{rec_event.message}'")

        print("\n" + "=" * 75)
        print("SIMULATION SUCCESS: Full Outage & Recovery State Machine Verified!")
        print("=" * 75)

    finally:
        db.close()


if __name__ == "__main__":
    simulate_incident_lifecycle()
