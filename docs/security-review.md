# Tether — Security Review & Hardening Report

## 1. Executive Summary & Threat Model
Tether operates in multi-tenant environments where organizations monitor mission-critical internal and external network infrastructure. Security hardening guarantees tenant isolation, protects internal networks against Server-Side Request Forgery (SSRF), prevents authentication replay attacks, and mitigates denial-of-service attempts.

---

## 2. Implemented Security Controls

### 2.1 SSRF (Server-Side Request Forgery) Protection
- **Vulnerability**: Attackers configuring webhook URLs or probe targets to scan internal services (`localhost`, `127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`, `169.254.169.254`, `metadata.google.internal`).
- **Mitigation Architecture** (`app/notifications/webhook.py`):
  1. **Scheme Validation**: Whitelist restricts protocols strictly to `http://` and `https://`.
  2. **Direct IP Literal Inspection**: Uses Python `ipaddress.ip_address` to block private, loopback, link-local, multicast, and cloud metadata ranges.
  3. **DNS Pre-Flight Resolution**: Resolves target hostnames via `socket.getaddrinfo` and inspects resolved IP addresses before any outbound HTTP dispatch.
  4. **Strict URL Parsing**: Rejects malformed hostnames, credentials in authority segments (`http://user:pass@host`), and relative paths.

### 2.2 Refresh Token Rotation & Anti-Replay Attack Protection
- **Vulnerability**: Stolen refresh token used concurrently by an attacker.
- **Mitigation Architecture** (`app/api/routes/auth.py`):
  1. **Single-Use Rotation**: Every successful `/api/auth/refresh` request revokes the presented refresh token and issues a new cryptographically secure token.
  2. **Replay / Reuse Detection**: If an already revoked refresh token is presented for exchange, Tether detects token theft and **immediately revokes all active sessions/tokens for that user family**, logging a high-priority security audit event (`SECURITY_ALERT_REFRESH_TOKEN_REUSE`).
  3. **HttpOnly Cookies**: Refresh tokens are stored in `HttpOnly`, `SameSite=Lax` cookies to prevent access from malicious client-side JavaScript.

### 2.3 Rate Limiting & Denial-of-Service Mitigation
- **Vulnerability**: Abuse of manual check triggers (`/check`) or webhook notification test endpoints to saturate worker queues or outbound network capacity.
- **Mitigation Architecture** (`app/core/rate_limit.py`):
  1. **Sliding Window Rate Limiter**: Implemented using Redis Sorted Sets with high-resolution unique member keys (`timestamp:nanoseconds`).
  2. **Scoped Limits**:
     - Auth Endpoints (`/login`, `/register`): 10 requests / minute / IP.
     - Manual Check Dispatch (`/targets/{id}/check`): 20 requests / minute / target.
     - Notification Test (`/notification-channels/{id}/test`): 10 requests / minute / channel.
  3. **In-Memory Fallback**: Thread-safe in-memory sliding window ensures continuous protection if Redis is temporarily offline.

### 2.4 Multi-Tenant Authorization & IDOR Protection
- **Vulnerability**: Insecure Direct Object References (IDOR) where User from Tenant A accesses or alters resources belonging to Tenant B.
- **Mitigation Architecture**:
  1. **Dependency Injection & JWT Scoping**: Every authenticated request resolves `TenantContext` containing verified `user_id`, `tenant_id`, and `role`.
  2. **Enforced Tenant Filtering**: All SQLAlchemy queries explicitly filter by `Target.tenant_id == ctx.tenant.id`, `AlertEvent.tenant_id == ctx.tenant.id`, and `NotificationChannel.tenant_id == ctx.tenant.id`.
  3. **Role-Based Access Control (RBAC)**: Fine-grained permissions enforced at route level:
     - `OWNER`: Full organization administration, membership deletion, tenant renaming.
     - `ADMIN`: Target creation/deletion, notification channel management, alert rule configuration.
     - `MEMBER`: Target editing, manual check dispatching, rule toggling.
     - `VIEWER`: Read-only access to dashboard, target statuses, latency charts, and alert logs.

### 2.5 Query Bounding & Pagination Security
- **Vulnerability**: Requesting unbounded query limits (e.g. `limit=1000000`) leading to memory exhaustion.
- **Mitigation Architecture**:
  1. FastAPI `Query(ge=1, le=1000)` enforces schema-level bounds.
  2. Oversized query parameters return HTTP `422 Unprocessable Entity`.

### 2.6 Credential Masking & Audit Logging
- **Vulnerability**: Accidental leakage of SMTP passwords, Slack webhook tokens, or API secrets in logs or responses.
- **Mitigation Architecture**:
  1. `mask_sensitive_config()` replaces all secret keys (`password`, `auth_token`, `webhook_url`, `secret`) with masked values (`********`) before API serialization and audit log persistence.
  2. Audit logs capture `(tenant_id, user_id, action, resource_type, resource_id, timestamp)` for security traceability without plain-text credential retention.
