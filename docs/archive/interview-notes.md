# Tether — Technical Interview & Architecture Defense

This document provides concise, technically rigorous answers to common systems design and engineering questions regarding the Tether architecture.

---

### Q1: Why use Celery for background monitoring?
**Answer**: Network monitoring tasks are I/O-bound and inherently unpredictable in duration due to timeouts and network lag. Running probes directly inside FastAPI request threads would exhaust ASGI worker pools and block incoming HTTP requests. Celery provides a distributed, message-driven worker mesh that decouples request handling from network I/O, supports horizontal worker autoscaling, and manages retry backoff natively.

---

### Q2: Why is Celery Beat configured as a single logical instance?
**Answer**: Celery Beat is a stateful logical clock that calculates next execution times and enqueues tasks into Redis. If multiple Celery Beat processes run simultaneously against the same Redis broker without distributed leader election, each Beat instance will independently fire scheduled checks, generating duplicate monitoring job floods that overwhelm workers, queues, and monitored targets.

---

### Q3: How does Tether prevent duplicate monitoring checks for the same target?
**Answer**: Tether uses a two-tiered deduplication mechanism:
1. **Redis Distributed Lock (`acquire_target_lock`)**: When a worker begins executing a check, it acquires an atomic lock `tether:lock:target:{target_id}` using `SET key 1 NX EX 30`. If another worker dequeues a duplicate task for that target while the lock is held, it terminates immediately.
2. **Database Active Job Check (`has_active_job`)**: During Beat dispatch, Tether checks if any job with status `IN_PROGRESS` already exists for that target.

---

### Q4: How does the alert threshold state machine prevent alert storms?
**Answer**:
1. **Consecutive Failure Threshold**: Tether does not alert on single intermittent network blips. An outage alert is only generated when `consecutive_failures == failure_threshold` (e.g. 3 consecutive failures).
2. **State Tracking**: Once the threshold is reached, the target state transitions from `UP` to `DOWN`, and exactly one `OUTAGE` event is fired.
3. **Cooldown Suppression**: As long as the target remains `DOWN`, subsequent failed checks are suppressed during the configured `cooldown_seconds` window.
4. **Recovery Notification**: The first successful check transitions the state back to `UP`, resets the failure counter, and dispatches a single `RECOVERY` alert.

---

### Q5: How does tenant isolation protect against Insecure Direct Object References (IDOR)?
**Answer**: Every authenticated request passes through the `get_current_tenant_context` dependency, which validates the user's JWT bearer token, confirms active tenant membership, and yields a `TenantContext`. All database queries explicitly filter by `Target.tenant_id == ctx.tenant.id` and `AlertEvent.tenant_id == ctx.tenant.id`. Even if an attacker guesses the integer ID of a target belonging to another organization, PostgreSQL returns `404 Not Found`.

---

### Q6: How does refresh token rotation defend against token replay attacks?
**Answer**: Every refresh token is single-use. When `/api/auth/refresh` is called, the supplied token is revoked and a new token is issued. If an attacker intercepts an old refresh token and attempts to use it, Tether detects that the token was already revoked, flags a replay attack, immediately revokes all active refresh tokens for that user family, and logs a high-severity security audit event (`SECURITY_ALERT_REFRESH_TOKEN_REUSE`).

---

### Q7: How does Tether protect against Server-Side Request Forgery (SSRF)?
**Answer**: In webhook configurations and HTTP probes, user-provided URLs are strictly validated:
1. Scheme must be `http` or `https`.
2. Hostnames matching `localhost`, `127.0.0.1`, `metadata.google.internal`, or `169.254.169.254` are blocked.
3. IP address literals in private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback, or link-local ranges are rejected.
4. Hostnames undergo pre-flight DNS resolution via `socket.getaddrinfo`, and any resolved IP matching private or restricted ranges is blocked before opening a network connection.

---

### Q8: What happens if PostgreSQL or Redis crashes?
**Answer**:
- **PostgreSQL Down**: `/health/readiness` fails with HTTP 503. The API continues serving liveness probes (`/health/live`), and Celery tasks retry with exponential backoff until the database reconnects with `pool_pre_ping=True`.
- **Redis Down**: Rate limiters automatically fall back to an in-memory sliding window, distributed locks degrade gracefully to database active-job checks, and `/health/readiness` reports `redis=unhealthy`. Workers reconnect automatically once Redis restarts.

---

### Q9: How would Tether scale from 100 to 10,000 targets?
**Answer**:
1. **Worker Mesh**: Scale Celery worker containers horizontally across nodes.
2. **Time-Series Storage**: Partition `monitoring_results` by day/week or migrate raw result metrics to a dedicated time-series engine (e.g. TimescaleDB or ClickHouse).
3. **Queue Sharding**: Shard Redis queues by protocol or target priority (`monitoring:high`, `monitoring:default`).
4. **Leader Election Scheduler**: Replace single Celery Beat with a Raft-coordinated distributed scheduler.
