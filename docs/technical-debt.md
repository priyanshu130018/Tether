# Tether — Technical Debt & Limitations Register

This document provides a transparent, engineering-grade register of current architectural constraints, design trade-offs, and scalability boundaries within Tether v1.0.0.

---

## 1. Architectural Constraints & Trade-Offs

### 1.1 Single-Instance Celery Beat Scheduler
- **Current State**: Celery Beat runs as a single logical process to prevent duplicate task dispatch storms.
- **Limitation**: If the Celery Beat container crashes, automatic periodic check scheduling pauses until the container restart policy or orchestrator restarts the process. Manual API checks (`/targets/{id}/check`) continue to function normally.
- **Future Solution**: Migrate from standard Celery Beat to a distributed leader-election scheduler (e.g. `RedBeat` with distributed Redis locks or Raft-based scheduler coordination).

---

### 1.2 In-Process / Local Benchmark Limitations
- **Current State**: Benchmark metrics recorded in Phase 8 (`373.48 req/s`, $p_{50}=41.9\text{ms}$) were executed locally with in-process ASGI transports.
- **Limitation**: These numbers measure raw framework overhead, serialization, and database I/O, but do NOT account for physical network interface latency, TLS termination handshakes at scale, or WAN routing jitter.
- **Future Solution**: Conduct multi-region distributed load tests across physical clusters with geographically distributed agents.

---

### 1.3 Exact Notification Delivery Semantics
- **Current State**: Outage and recovery notifications are delivered with **at-least-once** semantics with a retry limit of 3 attempts.
- **Limitation**: In cases of external network partitions where a third-party webhook server receives the HTTP request but drops the connection before returning the 200 OK header, Tether may retry and deliver a duplicate alert.
- **Future Solution**: Include an idempotency header (`X-Tether-Event-ID`) in outbound webhooks so receiving endpoints can deduplicate on their end.

---

### 1.4 Single Database Write Primary
- **Current State**: All monitoring results and status counters write directly to the primary PostgreSQL database.
- **Limitation**: At massive scale ($> 100,000$ targets with 10-second intervals), continuous time-series inserts ($10,000\text{ writes/sec}$) will place heavy I/O pressure on a single PostgreSQL instance.
- **Future Solution**: Partition `monitoring_results` by range (daily/weekly tables), adopt a specialized time-series storage engine (e.g. TimescaleDB, ClickHouse, or VictoriaMetrics) for raw probe metrics, and retain PostgreSQL for relational configuration and metadata.

---

## 2. Explicit Non-Features (Out of Scope for v1.0.0)
The following capabilities were intentionally excluded to maintain a high-quality, focused, and maintainable core platform:
1. **Kubernetes Operators / Helm Charts**: Tether provides production Docker Compose and standalone container definitions.
2. **Enterprise SAML / OAuth2 SSO**: Authentication uses standard JWT + RBAC without external enterprise identity providers (e.g. Okta, Azure AD).
3. **Mobile Native Apps**: Tether provides a responsive web application designed for mobile and desktop browsers.
4. **Active Synthetic User Flows**: Tether focuses on protocol availability (TCP/HTTP/DNS) rather than full browser automation (Selenium/Playwright).
