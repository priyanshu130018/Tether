export type Protocol = 'tcp' | 'http' | 'https' | 'dns';

export type TargetStatus = 'UNKNOWN' | 'UP' | 'DOWN';

export type JobStatus = 'scheduled' | 'queued' | 'running' | 'successful' | 'failed' | 'timed_out';

export type CheckStatus = 'up' | 'down';

export type AlertEventType = 'OUTAGE' | 'RECOVERY';

export type AlertEventStatus = 'PENDING' | 'PROCESSING' | 'SENT' | 'FAILED' | 'SUPPRESSED';

export type ChannelType = 'EMAIL' | 'SLACK' | 'WEBHOOK';

export type DeliveryStatus = 'PENDING' | 'SENT' | 'FAILED';

export interface HttpConfig {
  method?: string;
  path?: string;
  expected_status_codes?: number[];
  verify_ssl?: boolean;
  follow_redirects?: boolean;
  headers?: Record<string, string>;
}

export interface DnsConfig {
  record_type?: string;
  expected_records?: string[];
  nameserver?: string;
}

export interface Target {
  id: number;
  name: string;
  hostname: string;
  host?: string;
  port: number;
  protocol: Protocol;
  interval_seconds: number;
  timeout_seconds: number;
  retry_count: number;
  enabled: boolean;
  status: TargetStatus;
  config?: Record<string, any>;
  consecutive_failures: number;
  consecutive_successes: number;
  last_checked_at?: string;
  next_check_at?: string;
  last_successful_check_at?: string;
  last_failed_check_at?: string;
  created_at: string;
}

export interface TargetCreate {
  name: string;
  hostname?: string;
  host?: string;
  port?: number;
  protocol?: Protocol;
  interval_seconds?: number;
  timeout_seconds?: number;
  retry_count?: number;
  enabled?: boolean;
  config?: Record<string, any>;
}

export interface TargetUpdate {
  name?: string;
  hostname?: string;
  host?: string;
  port?: number;
  protocol?: Protocol;
  interval_seconds?: number;
  timeout_seconds?: number;
  retry_count?: number;
  enabled?: boolean;
  config?: Record<string, any>;
}

export interface Job {
  id: number;
  celery_task_id?: string;
  target_id: number;
  task_type: string;
  status: JobStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  error_message?: string;
  worker_id?: string;
}

export interface MonitoringResult {
  id: number;
  target_id: number;
  timestamp: string;
  protocol: Protocol;
  status: CheckStatus;
  latency_ms?: number;
  status_code?: number;
  error_type?: string;
  error_message?: string;
  extra_data?: Record<string, any>;
  metadata?: Record<string, any>;
  worker_id?: string;
}

export interface LatencyPoint {
  timestamp: string;
  latency_ms?: number;
  status: CheckStatus;
  status_code?: number;
}

export interface NotificationChannel {
  id: number;
  name: string;
  type: ChannelType;
  enabled: boolean;
  configuration: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface NotificationChannelCreate {
  name: string;
  type: ChannelType;
  enabled?: boolean;
  configuration: Record<string, any>;
}

export interface AlertRule {
  id: number;
  target_id: number;
  enabled: boolean;
  failure_threshold: number;
  recovery_enabled: boolean;
  cooldown_seconds: number;
  last_alerted_at?: string;
  last_recovery_alerted_at?: string;
  channel_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface AlertRuleCreate {
  target_id: number;
  enabled?: boolean;
  failure_threshold?: number;
  recovery_enabled?: boolean;
  cooldown_seconds?: number;
  channel_ids?: number[];
}

export interface AlertRuleUpdate {
  enabled?: boolean;
  failure_threshold?: number;
  recovery_enabled?: boolean;
  cooldown_seconds?: number;
  channel_ids?: number[];
}

export interface NotificationDelivery {
  id: number;
  channel_id: number;
  status: DeliveryStatus;
  attempt_count: number;
  last_attempt_at?: string;
  last_error?: string;
  created_at: string;
}

export interface AlertEvent {
  id: number;
  target_id: number;
  alert_rule_id?: number;
  event_type: AlertEventType;
  status: AlertEventStatus;
  message: string;
  deduplication_key?: string;
  extra_data?: Record<string, any>;
  created_at: string;
  resolved_at?: string;
  deliveries?: NotificationDelivery[];
}

export interface DashboardSummary {
  targets: number;
  up: number;
  down: number;
  unknown: number;
  active_alerts: number;
  running_jobs: number;
  total_jobs: number;
  active_workers: number;
}

export interface WorkerStatus {
  worker_id: string;
  status: string;
  active_jobs: number;
  processed_jobs: number;
  failed_jobs: number;
  last_seen?: string;
}

// ==========================================
// Authentication & Multi-Tenancy (Phase 6)
// ==========================================

export type Role = 'OWNER' | 'ADMIN' | 'MEMBER' | 'VIEWER';

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at?: string;
}

export interface Tenant {
  id: number;
  name: string;
  slug: string;
  created_at: string;
  role?: Role;
}

export interface TenantMembership {
  id: number;
  user_id: number;
  tenant_id: number;
  role: Role;
  user?: User;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
  active_tenant: Tenant;
  role: Role;
}

export interface TokenRefreshResponse {
  access_token: string;
  token_type: string;
}

export interface UserProfileResponse {
  user: User;
  active_tenant: Tenant;
  role: Role;
  memberships: TenantMembership[];
}

export interface MemberInvite {
  email: string;
  role: Role;
  full_name?: string;
}

export interface MemberRoleUpdate {
  role: Role;
}

export interface AuditLog {
  id: number;
  tenant_id: number;
  user_id?: number;
  action: string;
  resource_type: string;
  resource_id?: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface SystemHealth {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  uptime_seconds: number;
  database: string;
  redis: string;
  timestamp: string;
}


