# Tether — Architecture Decision Records (ADRs)

## Index of ADRs
- [ADR-001: Distributed Strategy-Based Protocol Monitoring Mesh](#adr-001-distributed-strategy-based-protocol-monitoring-mesh)
- [ADR-002: Celery Beat with Redis Distributed Locking for Deduplication](#adr-002-celery-beat-with-redis-distributed-locking-for-deduplication)
- [ADR-003: State Machine & Cooldown Alerting Engine](#adr-003-state-machine--cooldown-alerting-engine)
- [ADR-004: Multi-Tenant RBAC & Context-Driven Isolation](#adr-004-multi-tenant-rbac--context-driven-isolation)
- [ADR-005: Dual Sliding-Window Rate Limiting with In-Memory Degradation](#adr-005-dual-sliding-window-rate-limiting-with-in-memory-degradation)
- [ADR-006: Refresh Token Rotation with Anti-Replay Session Revocation](#adr-006-refresh-token-rotation-with-anti-replay-session-revocation)
- [ADR-007: Defense-in-Depth SSRF Protection with DNS Pre-Resolution](#adr-007-defense-in-depth-ssrf-protection-with-dns-pre-resolution)
- [ADR-008: Route-Level Lazy Loading for Frontend Observability Bundle](#adr-008-route-level-lazy-loading-for-frontend-observability-bundle)

---

### ADR-001: Distributed Strategy-Based Protocol Monitoring Mesh
- **Context**: Tether required monitoring across disparate protocols (TCP sockets, HTTP, HTTPS with SSL inspection, DNS lookups) without duplicating scheduling and tracking code.
- **Decision**: Implemented an extensible Strategy / Registry pattern (`BaseProbe` -> `TCPProbe`, `HTTPProbe`, `DNSProbe`). A single unified task `run_monitoring_check` delegates to the registry.
- **Consequences**: Adding new network protocols (e.g. UDP, ICMP, gRPC) requires only implementing `BaseProbe` without touching Celery Beat or alerting logic.

---

### ADR-002: Celery Beat with Redis Distributed Locking for Deduplication
- **Context**: When monitoring checks take longer than configured intervals or when multiple Celery Beat scheduler instances run, race conditions can cause duplicate checks for the same target.
- **Decision**: Implemented two-tiered concurrency protection:
  1. Redis distributed lock (`acquire_target_lock`) with short TTL.
  2. Database active job check (`has_active_job`) querying `jobs(target_id, status="IN_PROGRESS")`.
- **Consequences**: Zero duplicate checks occur even during transient network delays or burst dispatches.

---

### ADR-003: State Machine & Cooldown Alerting Engine
- **Context**: Network glitches or repeated failures should not flood on-call engineers with hundreds of notifications.
- **Decision**: Implemented threshold-driven state transitions (`consecutive_failures >= failure_threshold` -> `OUTAGE`, single success -> `RECOVERY`) combined with configurable cooldown windows and idempotency keys (`outage:{target_id}:{event_id}`).
- **Consequences**: Outages generate exactly one alert when the threshold is reached; subsequent failures are suppressed during cooldown; recovery generates a single clear event.

---

### ADR-004: Multi-Tenant RBAC & Context-Driven Isolation
- **Context**: Tether supports organizations and teams where users should only access their own targets, rules, and audit logs.
- **Decision**: Introduced JWT authentication coupled with `TenantContext` dependency injection and role hierarchy (`OWNER` > `ADMIN` > `MEMBER` > `VIEWER`). All SQL queries enforce tenant ID scoping.
- **Consequences**: Complete IDOR protection and clean tenant isolation across all endpoints.

---

### ADR-005: Dual Sliding-Window Rate Limiting with In-Memory Degradation
- **Context**: Sensitive endpoints (login, register, manual check, test notification) must be protected against abuse even when Redis is temporarily restarting or unconfigured.
- **Decision**: Implemented Redis sorted-set sliding window rate limiter using nanosecond-unique member IDs, backed by a thread-safe in-memory fallback.
- **Consequences**: Protection remains seamless in both clustered production environments and standalone test fixtures.

---

### ADR-006: Refresh Token Rotation with Anti-Replay Session Revocation
- **Context**: Stolen refresh tokens pose a severe risk if reused by adversaries.
- **Decision**: Enforced single-use refresh token rotation. If an already revoked token is presented for exchange, the auth engine flags replay theft and immediately revokes all active tokens for that user family.
- **Consequences**: Eliminates replay attacks and provides immediate account protection upon token compromise.

---

### ADR-007: Defense-in-Depth SSRF Protection with DNS Pre-Resolution
- **Context**: User-configured webhook notification URLs could target internal infrastructure or cloud metadata endpoints.
- **Decision**: Implemented strict URL scheme validation, forbidden hostname checking, direct IP literal classification (blocking private/loopback/cloud metadata CIDRs), and DNS pre-resolution with `socket.getaddrinfo`.
- **Consequences**: Webhook dispatches cannot be weaponized to probe internal RFC1918 subnets or cloud instance metadata.

---

### ADR-008: Route-Level Lazy Loading for Frontend Observability Bundle
- **Context**: Dashboard and target detail views include heavy charting and UI dependencies (`chart.js`, `lucide-react`), bloating the initial JavaScript bundle.
- **Decision**: Converted all application routes in `frontend/src/App.tsx` to `React.lazy` and `Suspense` code splitting.
- **Consequences**: Reduced main entry bundle from ~650 KB to 231 KB (gzip 72 KB), delivering fast First Contentful Paint times.
