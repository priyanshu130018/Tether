"""Initial production schema synchronized with current SQLAlchemy models

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-10-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models import (
    AlertEventStatus,
    AlertEventType,
    ChannelType,
    CheckStatus,
    DeliveryStatus,
    JobStatus,
    Protocol,
    Role,
    TargetStatus,
)

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tenants
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # 2. Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 3. Tenant Memberships
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Enum(Role, native_enum=False), nullable=False, server_default=Role.MEMBER.value),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])
    op.create_index("ix_tenant_memberships_user_tenant", "tenant_memberships", ["user_id", "tenant_id"], unique=True)

    # 4. Refresh Tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    # 5. Audit Logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"])

    # 6. Targets
    op.create_table(
        "targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.Enum(Protocol, native_enum=False), nullable=False, server_default=Protocol.TCP.value),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("timeout_seconds", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.Enum(TargetStatus, native_enum=False), nullable=False, server_default=TargetStatus.UNKNOWN.value),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_targets_tenant_id", "targets", ["tenant_id"])
    op.create_index("ix_targets_enabled_next_check", "targets", ["enabled", "next_check_at"])

    # 7. Monitoring Results
    op.create_table(
        "monitoring_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("protocol", sa.Enum(Protocol, native_enum=False), nullable=False, server_default=Protocol.TCP.value),
        sa.Column("status", sa.Enum(CheckStatus, native_enum=False), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_results_tenant_id", "monitoring_results", ["tenant_id"])
    op.create_index("ix_monitoring_results_target_timestamp", "monitoring_results", ["target_id", "timestamp"])

    # 8. Jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.Enum(JobStatus, native_enum=False), nullable=False, server_default=JobStatus.QUEUED.value),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("celery_task_id"),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_target_created_at", "jobs", ["target_id", "created_at"])
    op.create_index("ix_jobs_target_status", "jobs", ["target_id", "status"])

    # 9. Notification Channels
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.Enum(ChannelType, native_enum=False), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_channels_tenant_id", "notification_channels", ["tenant_id"])

    # 10. Alert Rules
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("failure_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("recovery_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="1800"),
        sa.Column("last_alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_recovery_alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_rules_tenant_id", "alert_rules", ["tenant_id"])
    op.create_index("ix_alert_rules_target_id", "alert_rules", ["target_id"])

    # 11. Alert Rule Channels (Association Table)
    op.create_table(
        "alert_rule_channels",
        sa.Column("alert_rule_id", sa.Integer(), nullable=False),
        sa.Column("notification_channel_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["alert_rule_id"], ["alert_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["notification_channel_id"], ["notification_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("alert_rule_id", "notification_channel_id"),
    )

    # 12. Alert Events
    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("alert_rule_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.Enum(AlertEventType, native_enum=False), nullable=False),
        sa.Column("status", sa.Enum(AlertEventStatus, native_enum=False), nullable=False, server_default=AlertEventStatus.PENDING.value),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["alert_rule_id"], ["alert_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_events_tenant_id", "alert_events", ["tenant_id"])
    op.create_index("ix_alert_events_target_id", "alert_events", ["target_id"])
    op.create_index("ix_alert_events_dedup_key", "alert_events", ["deduplication_key"])
    op.create_index("ix_alert_events_created_at", "alert_events", ["created_at"])

    # 13. Notification Deliveries
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_event_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum(DeliveryStatus, native_enum=False), nullable=False, server_default=DeliveryStatus.PENDING.value),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["alert_event_id"], ["alert_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["notification_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_deliveries_event_channel", "notification_deliveries", ["alert_event_id", "channel_id"])


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("alert_events")
    op.drop_table("alert_rule_channels")
    op.drop_table("alert_rules")
    op.drop_table("notification_channels")
    op.drop_table("jobs")
    op.drop_table("monitoring_results")
    op.drop_table("targets")
    op.drop_table("audit_logs")
    op.drop_table("refresh_tokens")
    op.drop_table("tenant_memberships")
    op.drop_table("users")
    op.drop_table("tenants")
