# Tether — Security Architecture & Threat Defense

## 1. Security Overview & Threat Model
Tether operates in multi-tenant environments where organizations monitor mission-critical internal and external network infrastructure. Security hardening guarantees tenant isolation, protects internal networks against Server-Side Request Forgery (SSRF), prevents authentication replay attacks, and mitigates denial-of-service attempts through a zero-trust, defense-in-depth model across authentication, tenant isolation, network dispatching, and audit logging.

```text
                                [Client Request]
                                       │
                                       ▼
                     [Nginx Security Headers & Rate Limits]
                                       │
                                       ▼
                     [FastAPI JWT Bearer Verification]
                                       │
                                       ▼
                       [Tenant Context Resolution]
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
          [Role Authorization]                 [Tenant Scoped Query]
        (OWNER, ADMIN, MEMBER, VIEWER)        (WHERE tenant_id = ctx.tenant.id)
                    │                                     │
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                           [SSRF Inspection Guard]
                     (IP Literal & Pre-Flight DNS Checks)
                                       │
                                       ▼
                        [Secret Redacted Audit Log]
```

---

## 2. Implemented Security Controls & Mitigations

### 2.1 Authentication & Token Lifecycle
- **Password Hashing**: Bcrypt with work factor 12. Plaintext passwords are never logged or stored.
- **JWT Access Tokens**: Short-lived (15 minutes), signed with HMAC-SHA256 using a high-entropy secret key ($\ge 256$ bits / 32 characters minimum).
- **Refresh Token Rotation**:
  - Refresh tokens are single-use cryptographically random tokens (64 bytes).
  - Stored in `HttpOnly`, `SameSite=Lax` cookies to prevent access from malicious client-side JavaScript.
  - Stored in the database as SHA-256 hashes (`token_hash`) so compromised database dumps cannot be leveraged directly.
  - Upon use (`POST /api/auth/refresh`), the current token is revoked, and a fresh token is issued.
- **Anti-Replay Attack Defense**:
  - If an already revoked or rotated refresh token is presented for exchange, Tether detects token theft/reuse.
  - **Action**: All active sessions and refresh tokens for that user family are immediately revoked, and an audit security event (`SECURITY_ALERT_REFRESH_TOKEN_REUSE`) is logged.

---

### 2.2 Multi-Tenant Isolation & IDOR Protection
- **Tenant Scoping**: All database models (`targets`, `alert_rules`, `notification_channels`, `alert_events`, `jobs`, `audit_logs`) carry a foreign key `tenant_id`.
- **Query Injection & IDOR Prevention**: Database queries resolve `ctx.tenant.id` through FastAPI dependency injection (`get_current_tenant_context`). All SQLAlchemy queries explicitly enforce `WHERE tenant_id = ctx.tenant.id`. Even if an attacker guesses the integer ID of a target or alert rule belonging to another organization, the database query returns `404 Not Found`.
- **Role-Based Access Control (RBAC)**:
  - `OWNER`: Full organization administration, membership removal, tenant settings.
  - `ADMIN`: Target creation/deletion, notification channel CRUD, alert rule editing.
  - `MEMBER`: Target editing, manual check dispatch, notification tests.
  - `VIEWER`: Read-only access to dashboard metrics, target latency, and alerts.

---

### 2.3 SSRF (Server-Side Request Forgery) Protection
Outbound webhook notifications and probes cannot be weaponized to scan or attack private infrastructure (`app/notifications/webhook.py`):
1. **Protocol Whitelist**: Only `http://` and `https://` are permitted.
2. **Forbidden Hostnames**: Explicitly blocks `localhost`, `127.0.0.1`, `0.0.0.0`, `metadata.google.internal`, `169.254.169.254`, `instance-data`.
3. **IP Range Restrictions**: Rejects private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`, `fe80::/10`), and multicast addresses.
4. **Pre-Flight DNS Resolution**: Resolves hostnames to IP addresses via `socket.getaddrinfo` prior to socket connection to prevent DNS rebinding attacks.
5. **Strict URL Parsing**: Rejects malformed hostnames, credentials in authority segments (`http://user:pass@host`), and relative paths.

---

### 2.4 Rate Limiting & DoS Protection
- **Sliding Window Algorithm**: Redis sorted sets track request timestamps with nanosecond precision (`{now:perf_counter_ns()}`).
- **Endpoint Limits**:
  - Auth (`/login`, `/register`): 10 requests / min / IP.
  - Manual Probes (`/targets/{id}/check`): 20 requests / min / target.
  - Channel Test (`/notification-channels/{id}/test`): 10 requests / min / channel.
- **In-Memory Fallback**: Thread-safe in-memory sliding window provides uninterrupted rate limiting when Redis is unavailable.

---

### 2.5 Query Bounding & Pagination Security
- **Parameter Validation**: FastAPI `Query(ge=1, le=1000)` enforces schema-level bounds on all listing endpoints.
- **Oversized Queries**: Oversized limit or offset parameters return HTTP `422 Unprocessable Entity`, preventing memory exhaustion.

---

### 2.6 Credential Masking & Security Headers
- **Secret Redaction**: `mask_sensitive_config()` automatically masks sensitive fields (`password`, `auth_token`, `webhook_url`, `secret`) with `********` before API output or database audit logging.
- **Security Headers Injected via Nginx & Middleware**:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `X-Request-ID`: Correlation identifier injected into all responses.
