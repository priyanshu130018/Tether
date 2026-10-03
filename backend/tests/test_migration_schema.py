import os
import tempfile
from alembic.config import Config
from alembic import command
import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import Base
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
    NotificationDelivery,
    Protocol,
    Role,
    Target,
    TargetStatus,
    Tenant,
    TenantMembership,
    User,
)


def test_alembic_upgrade_head_on_clean_db():
    """
    Schema verification test:
    1. Creates a clean isolated database.
    2. Runs alembic upgrade head programmatically.
    3. Verifies inspector finds all 13 tables with expected columns.
    4. Verifies application ORM operations can execute against the migrated schema.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        sqlite_url = f"sqlite:///{tmp_db_path}"
        engine = create_engine(sqlite_url)

        # Configure Alembic
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        alembic_ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))

        # Run Alembic upgrade head
        command.upgrade(alembic_cfg, "head")

        inspector = inspect(engine)
        migrated_tables = set(inspector.get_table_names())

        expected_tables = {
            "tenants",
            "users",
            "tenant_memberships",
            "refresh_tokens",
            "audit_logs",
            "targets",
            "monitoring_results",
            "jobs",
            "notification_channels",
            "alert_rules",
            "alert_rule_channels",
            "alert_events",
            "notification_deliveries",
            "alembic_version",
        }

        assert expected_tables.issubset(migrated_tables), (
            f"Missing migrated tables: {expected_tables - migrated_tables}"
        )

        # Verify key columns on critical tables to prevent model-migration drift
        target_cols = {c["name"] for c in inspector.get_columns("targets")}
        assert "hostname" in target_cols
        assert "interval_seconds" in target_cols
        assert "timeout_seconds" in target_cols
        assert "status" in target_cols

        result_cols = {c["name"] for c in inspector.get_columns("monitoring_results")}
        assert "timestamp" in result_cols
        assert "worker_id" in result_cols
        assert "latency_ms" in result_cols

        job_cols = {c["name"] for c in inspector.get_columns("jobs")}
        assert "completed_at" in job_cols
        assert "duration_ms" in job_cols
        assert "worker_id" in job_cols

        channel_cols = {c["name"] for c in inspector.get_columns("notification_channels")}
        assert "configuration" in channel_cols
        assert "enabled" in channel_cols

        rule_cols = {c["name"] for c in inspector.get_columns("alert_rules")}
        assert "last_alerted_at" in rule_cols
        assert "last_recovery_alerted_at" in rule_cols

        event_cols = {c["name"] for c in inspector.get_columns("alert_events")}
        assert "deduplication_key" in event_cols
        assert "extra_data" in event_cols
        assert "resolved_at" in event_cols

        # Verify ORM write and query operations against migrated database
        TestingSession = sessionmaker(bind=engine)
        with TestingSession() as session:
            tenant = Tenant(name="Test Corp", slug="test-corp")
            session.add(tenant)
            session.flush()

            user = User(
                email="admin@testcorp.com",
                password_hash="hash123",
                full_name="Admin User",
            )
            session.add(user)
            session.flush()

            membership = TenantMembership(
                user_id=user.id,
                tenant_id=tenant.id,
                role=Role.OWNER,
            )
            session.add(membership)

            target = Target(
                tenant_id=tenant.id,
                name="API Gateway",
                hostname="api.testcorp.com",
                port=443,
                protocol=Protocol.HTTPS,
                status=TargetStatus.UP,
            )
            session.add(target)
            session.flush()

            job = Job(
                target_id=target.id,
                tenant_id=tenant.id,
                task_type="https_check",
                status=JobStatus.SUCCESSFUL,
                worker_id="worker-node-1",
            )
            session.add(job)
            session.flush()

            result = MonitoringResult(
                target_id=target.id,
                tenant_id=tenant.id,
                protocol=Protocol.HTTPS,
                status=CheckStatus.UP,
                latency_ms=12.4,
                worker_id="worker-node-1",
            )
            session.add(result)

            channel = NotificationChannel(
                tenant_id=tenant.id,
                name="Ops Slack",
                type=ChannelType.SLACK,
                configuration={"webhook_url": "https://hooks.slack.com/services/test"},
            )
            session.add(channel)
            session.flush()

            rule = AlertRule(
                tenant_id=tenant.id,
                target_id=target.id,
                failure_threshold=3,
                cooldown_seconds=300,
            )
            rule.channels.append(channel)
            session.add(rule)
            session.flush()

            event = AlertEvent(
                tenant_id=tenant.id,
                target_id=target.id,
                alert_rule_id=rule.id,
                event_type=AlertEventType.OUTAGE,
                status=AlertEventStatus.PENDING,
                message="Service down",
                deduplication_key="test-dedup-key",
            )
            session.add(event)
            session.flush()

            delivery = NotificationDelivery(
                alert_event_id=event.id,
                channel_id=channel.id,
            )
            session.add(delivery)
            session.commit()

            # Verify query
            queried_target = session.scalars(select(Target).where(Target.id == target.id)).first()
            assert queried_target is not None
            assert queried_target.hostname == "api.testcorp.com"
            assert len(queried_target.jobs) == 1
            assert len(queried_target.results) == 1
            assert len(queried_target.alert_rules) == 1
            assert len(queried_target.alert_rules[0].channels) == 1

        engine.dispose()
    finally:
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except OSError:
                pass
