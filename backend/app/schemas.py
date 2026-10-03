from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
from app.notifications.base import mask_sensitive_config

VALID_HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}
VALID_DNS_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "TXT", "NS"}


class HttpConfig(BaseModel):
    method: str = Field(default="GET")
    path: str = Field(default="/")
    expected_status_codes: list[int] = Field(default_factory=lambda: [200])
    verify_ssl: bool = True
    follow_redirects: bool = True
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        upper_v = v.upper()
        if upper_v not in VALID_HTTP_METHODS:
            raise ValueError(f"Invalid HTTP method '{v}'. Must be one of {sorted(VALID_HTTP_METHODS)}")
        return upper_v

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v.startswith("/"):
            return f"/{v}"
        return v


class DnsConfig(BaseModel):
    record_type: str = Field(default="A")
    expected_records: list[str] | None = None
    nameserver: str | None = None

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        upper_v = v.upper().strip()
        if upper_v not in VALID_DNS_RECORD_TYPES:
            raise ValueError(
                f"Invalid DNS record type '{v}'. Must be one of {sorted(VALID_DNS_RECORD_TYPES)}"
            )
        return upper_v


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol: Protocol = Protocol.TCP
    interval_seconds: int = Field(default=60, ge=10)
    timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    retry_count: int = Field(default=0, ge=0, le=5)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def validate_payload(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        # Sync host and hostname
        h = data.get("host")
        hn = data.get("hostname")
        if hn and not h:
            data["host"] = hn
        elif h and not hn:
            data["hostname"] = h
        elif not h and not hn:
            raise ValueError("Either 'host' or 'hostname' must be provided")

        # Default port based on protocol if not provided
        proto_str = str(data.get("protocol", "tcp")).lower()
        if data.get("port") is None:
            if proto_str == "http":
                data["port"] = 80
            elif proto_str == "https":
                data["port"] = 443
            elif proto_str == "dns":
                data["port"] = 53
            else:
                data["port"] = 80

        # Validate protocol-specific configuration
        raw_config = data.get("config") or {}
        if proto_str in ("http", "https"):
            validated_http = HttpConfig(**raw_config)
            data["config"] = validated_http.model_dump()
        elif proto_str == "dns":
            validated_dns = DnsConfig(**raw_config)
            data["config"] = validated_dns.model_dump()

        return data


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    protocol: Protocol | None = None
    interval_seconds: int | None = Field(default=None, ge=10)
    timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    retry_count: int | None = Field(default=None, ge=0, le=5)
    enabled: bool | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_update(cls, data: object) -> object:
        if isinstance(data, dict):
            h = data.get("host")
            hn = data.get("hostname")
            if hn and not h:
                data["host"] = hn
            elif h and not hn:
                data["hostname"] = h

            proto = data.get("protocol")
            raw_config = data.get("config")
            if raw_config is not None and proto:
                proto_str = str(proto).lower()
                if proto_str in ("http", "https"):
                    data["config"] = HttpConfig(**raw_config).model_dump()
                elif proto_str == "dns":
                    data["config"] = DnsConfig(**raw_config).model_dump()
        return data


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hostname: str
    host: str | None = None
    port: int
    protocol: Protocol
    interval_seconds: int
    timeout_seconds: float
    retry_count: int
    enabled: bool
    status: TargetStatus
    config: dict[str, Any] | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None
    last_successful_check_at: datetime | None = None
    last_failed_check_at: datetime | None = None
    created_at: datetime

    @model_validator(mode="after")
    def sync_host(self) -> "TargetRead":
        if self.host is None and self.hostname is not None:
            self.host = self.hostname
        return self


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    celery_task_id: str | None
    target_id: int
    task_type: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: float | None
    error_message: str | None
    worker_id: str | None


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    timestamp: datetime
    protocol: Protocol = Protocol.TCP
    status: CheckStatus
    latency_ms: float | None
    status_code: int | None = None
    error_type: str | None = None
    error_message: str | None
    extra_data: dict[str, Any] | None = None
    worker_id: str | None

    @model_validator(mode="before")
    @classmethod
    def extract_from_orm(cls, data: Any) -> Any:
        if hasattr(data, "__dict__") and hasattr(data, "__tablename__"):
            return {
                "id": getattr(data, "id", None),
                "target_id": getattr(data, "target_id", None),
                "timestamp": getattr(data, "timestamp", None),
                "protocol": getattr(data, "protocol", Protocol.TCP),
                "status": getattr(data, "status", None),
                "latency_ms": getattr(data, "latency_ms", None),
                "status_code": getattr(data, "status_code", None),
                "error_type": getattr(data, "error_type", None),
                "error_message": getattr(data, "error_message", None),
                "extra_data": getattr(data, "extra_data", None),
                "worker_id": getattr(data, "worker_id", None),
            }
        return data


# ==========================================
# Alerting & Notification Schemas (Phase 4)
# ==========================================


class NotificationChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: ChannelType
    enabled: bool = True
    configuration: dict[str, Any] = Field(default_factory=dict)


class NotificationChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: ChannelType | None = None
    enabled: bool | None = None
    configuration: dict[str, Any] | None = None


class NotificationChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: ChannelType
    enabled: bool
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def mask_config_secrets(self) -> "NotificationChannelRead":
        if self.configuration:
            self.configuration = mask_sensitive_config(self.configuration)
        return self


class AlertRuleCreate(BaseModel):
    target_id: int
    enabled: bool = True
    failure_threshold: int = Field(default=3, ge=1)
    recovery_enabled: bool = True
    cooldown_seconds: int = Field(default=1800, ge=0)
    channel_ids: list[int] = Field(default_factory=list)


class AlertRuleUpdate(BaseModel):
    enabled: bool | None = None
    failure_threshold: int | None = Field(default=None, ge=1)
    recovery_enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0)
    channel_ids: list[int] | None = None


class AlertRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    enabled: bool
    failure_threshold: int
    recovery_enabled: bool
    cooldown_seconds: int
    last_alerted_at: datetime | None = None
    last_recovery_alerted_at: datetime | None = None
    channel_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, rule: Any) -> "AlertRuleRead":
        c_ids = [c.id for c in rule.channels] if hasattr(rule, "channels") and rule.channels else []
        return cls(
            id=rule.id,
            target_id=rule.target_id,
            enabled=rule.enabled,
            failure_threshold=rule.failure_threshold,
            recovery_enabled=rule.recovery_enabled,
            cooldown_seconds=rule.cooldown_seconds,
            last_alerted_at=rule.last_alerted_at,
            last_recovery_alerted_at=rule.last_recovery_alerted_at,
            channel_ids=c_ids,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )


class NotificationDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    status: DeliveryStatus
    attempt_count: int
    last_attempt_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime


class AlertEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    alert_rule_id: int | None = None
    event_type: AlertEventType
    status: AlertEventStatus
    message: str
    deduplication_key: str | None = None
    extra_data: dict[str, Any] | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    deliveries: list[NotificationDeliveryRead] = Field(default_factory=list)


# ==========================================
# Dashboard & Observability Schemas (Phase 5)
# ==========================================


class DashboardSummaryRead(BaseModel):
    targets: int
    up: int
    down: int
    unknown: int
    active_alerts: int
    running_jobs: int
    total_jobs: int
    active_workers: int


class LatencyPointRead(BaseModel):
    timestamp: datetime
    latency_ms: float | None
    status: CheckStatus
    status_code: int | None = None


class WorkerStatusRead(BaseModel):
    worker_id: str
    status: str
    active_jobs: int
    processed_jobs: int
    failed_jobs: int
    last_seen: datetime | None = None


# ==========================================
# Authentication & Multi-Tenancy (Phase 6)
# ==========================================


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)
    tenant_name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if "@" not in clean or "." not in clean:
            raise ValueError("Invalid email address format")
        return clean


class UserLogin(BaseModel):
    email: str
    password: str
    tenant_id: int | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    role: Role | None = None


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=120)


class TenantMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    tenant_id: int
    role: Role
    user: UserRead | None = None
    created_at: datetime


class MemberInvite(BaseModel):
    email: str
    role: Role = Role.MEMBER
    full_name: str | None = None


class MemberRoleUpdate(BaseModel):
    role: Role


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
    active_tenant: TenantRead
    role: Role


class TokenRefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    user: UserRead
    active_tenant: TenantRead
    role: Role
    memberships: list[TenantMembershipRead] = Field(default_factory=list)


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    user_id: int | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    metadata_json: dict[str, Any] | None = Field(default=None, alias="metadata")
    created_at: datetime

