from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Column,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Role(str, PyEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class Protocol(str, PyEnum):
    TCP = "tcp"
    HTTP = "http"
    HTTPS = "https"
    DNS = "dns"


class CheckStatus(str, PyEnum):
    UP = "up"
    DOWN = "down"


class TargetStatus(str, PyEnum):
    UNKNOWN = "UNKNOWN"
    UP = "UP"
    DOWN = "DOWN"


class JobStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class AlertEventType(str, PyEnum):
    OUTAGE = "OUTAGE"
    RECOVERY = "RECOVERY"


class AlertEventStatus(str, PyEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


class ChannelType(str, PyEnum):
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    WEBHOOK = "WEBHOOK"


class DeliveryStatus(str, PyEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


# Many-to-Many association table between AlertRule and NotificationChannel
alert_rule_channels = Table(
    "alert_rule_channels",
    Base.metadata,
    Column("alert_rule_id", Integer, ForeignKey("alert_rules.id", ondelete="CASCADE"), primary_key=True),
    Column("notification_channel_id", Integer, ForeignKey("notification_channels.id", ondelete="CASCADE"), primary_key=True),
)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    memberships: Mapped[list["TenantMembership"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    targets: Mapped[list["Target"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    notification_channels: Mapped[list["NotificationChannel"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    alert_rules: Mapped[list["AlertRule"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    alert_events: Mapped[list["AlertEvent"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_verified: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["TenantMembership"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        Index("ix_tenant_memberships_user_tenant", "user_id", "tenant_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role, native_enum=False), default=Role.MEMBER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant] = relationship(back_populates="audit_logs")
    user: Mapped[User | None] = relationship(back_populates="audit_logs")


class Target(Base):
    __tablename__ = "targets"
    __table_args__ = (
        Index("ix_targets_enabled_next_check", "enabled", "next_check_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), default=1, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    hostname: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer)
    protocol: Mapped[Protocol] = mapped_column(SAEnum(Protocol, native_enum=False), default=Protocol.TCP)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[float] = mapped_column(default=5.0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(default=True)
    status: Mapped[TargetStatus] = mapped_column(SAEnum(TargetStatus, native_enum=False), default=TargetStatus.UNKNOWN)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failed_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped[Tenant | None] = relationship(back_populates="targets")
    results: Mapped[list["MonitoringResult"]] = relationship(back_populates="target", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="target", cascade="all, delete-orphan")
    alert_rules: Mapped[list["AlertRule"]] = relationship(back_populates="target", cascade="all, delete-orphan")
    alert_events: Mapped[list["AlertEvent"]] = relationship(back_populates="target", cascade="all, delete-orphan")


class MonitoringResult(Base):
    __tablename__ = "monitoring_results"
    __table_args__ = (Index("ix_monitoring_results_target_timestamp", "target_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"))
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), default=1, nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    protocol: Mapped[Protocol] = mapped_column(SAEnum(Protocol, native_enum=False), default=Protocol.TCP)
    status: Mapped[CheckStatus] = mapped_column(SAEnum(CheckStatus, native_enum=False))
    latency_ms: Mapped[float | None] = mapped_column()
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text())
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(255))

    target: Mapped[Target] = relationship(back_populates="results")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_target_created_at", "target_id", "created_at"),
        Index("ix_jobs_target_status", "target_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"))
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), default=1, nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(80))
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus, native_enum=False), default=JobStatus.QUEUED)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column()
    error_message: Mapped[str | None] = mapped_column(Text())
    worker_id: Mapped[str | None] = mapped_column(String(255))

    target: Mapped[Target] = relationship(back_populates="jobs")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), default=1, nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType, native_enum=False))
    enabled: Mapped[bool] = mapped_column(default=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    tenant: Mapped[Tenant | None] = relationship(back_populates="notification_channels")
    alert_rules: Mapped[list["AlertRule"]] = relationship(
        secondary=alert_rule_channels,
        back_populates="channels",
    )
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        Index("ix_alert_rules_target_id", "target_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), default=1, nullable=True, index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"))
    enabled: Mapped[bool] = mapped_column(default=True)
    failure_threshold: Mapped[int] = mapped_column(Integer, default=3)
    recovery_enabled: Mapped[bool] = mapped_column(default=True)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    last_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_recovery_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    tenant: Mapped[Tenant | None] = relationship(back_populates="alert_rules")
    target: Mapped[Target] = relationship(back_populates="alert_rules")
    channels: Mapped[list[NotificationChannel]] = relationship(
        secondary=alert_rule_channels,
        back_populates="alert_rules",
    )
    events: Mapped[list["AlertEvent"]] = relationship(
        back_populates="alert_rule",
        cascade="all, delete-orphan",
    )


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_target_id", "target_id"),
        Index("ix_alert_events_dedup_key", "deduplication_key"),
        Index("ix_alert_events_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), default=1, nullable=True, index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("targets.id", ondelete="CASCADE"))
    alert_rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[AlertEventType] = mapped_column(SAEnum(AlertEventType, native_enum=False))
    status: Mapped[AlertEventStatus] = mapped_column(
        SAEnum(AlertEventStatus, native_enum=False),
        default=AlertEventStatus.PENDING,
    )
    message: Mapped[str] = mapped_column(Text())
    deduplication_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant | None] = relationship(back_populates="alert_events")
    target: Mapped[Target] = relationship(back_populates="alert_events")
    alert_rule: Mapped[AlertRule | None] = relationship(back_populates="events")
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="alert_event",
        cascade="all, delete-orphan",
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("ix_notification_deliveries_event_channel", "alert_event_id", "channel_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_event_id: Mapped[int] = mapped_column(ForeignKey("alert_events.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("notification_channels.id", ondelete="CASCADE"))
    status: Mapped[DeliveryStatus] = mapped_column(
        SAEnum(DeliveryStatus, native_enum=False),
        default=DeliveryStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    alert_event: Mapped[AlertEvent] = relationship(back_populates="deliveries")
    channel: Mapped[NotificationChannel] = relationship(back_populates="deliveries")
