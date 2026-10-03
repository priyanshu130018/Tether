# Tether — Comprehensive Technical Interview & Systems Defense Guide

This guide contains precise, implementation-grounded answers to 33 architectural, reliability, security, performance, and scalability questions about Tether.

---

## 1. Architecture

### 1. Why FastAPI?
FastAPI is an asynchronous Python framework built on Starlette and Pydantic. It provides non-blocking asynchronous I/O for high-throughput HTTP endpoints, automatic OpenAPI/Swagger documentation generation, strict request/response data validation via Pydantic schemas, and native dependency injection for database session management and tenant authentication contexts.

### 2. Why Celery?
Network monitoring probes are I/O-bound and have non-deterministic response times (e.g. slow DNS queries or 5-second socket timeouts). Running network probes directly in API worker threads would block ASGI event loops, exhaust connection pools, and degrade API response times. Celery provides a distributed background task mesh with message queues, automatic worker retries, concurrency management, and worker health heartbeats.

### 3. Why Redis?
Redis serves two critical roles in Tether:
1. **Low-Latency Message Broker**: Provides FIFO task queues for Celery workers to ingest monitoring and notification jobs with sub-millisecond overhead.
2. **Distributed Concurrency Store**: Provides fast atomic primitives (`SET key val NX EX`) for distributed target locking and sliding-window rate limit counters.

### 4. Why PostgreSQL?
PostgreSQL was chosen for its ACID transactional guarantees, strong relational modeling, and rich indexing capabilities. It stores relational configuration (tenants, users, targets, alert rules, notification channels), time-series probe results (`monitoring_results`), job execution lifecycle records (`jobs`), and immutable audit trails (`audit_logs`) with foreign key cascade integrity.

### 5. Why separate Celery Beat from worker processes?
Celery Beat is a stateful logical clock responsible for calculating schedule ticks and enqueueing tasks. If Beat were embedded inside worker processes or scaled horizontally without leader election, every worker node would independently fire scheduled checks, creating duplicate task dispatch storms that flood Redis and overload monitored endpoints. Separating Beat guarantees a single source of scheduling truth.

### 6. Why use distributed locking?
When target check intervals are short (e.g. 10s) and target latency or timeouts take longer than the interval, or during scheduler bursts, multiple tasks for the same target could exist in the queue concurrently. A Redis distributed lock (`tether:lock:target:{id}`) ensures only one worker thread actively checks a specific target at any given instant.

### 7. How does duplicate job prevention work?
Tether implements two-tiered deduplication:
1. **Redis Lock (`acquire_target_lock`)**: When a worker begins executing `run_monitoring_check`, it attempts to acquire `SET tether:lock:target:{target_id} 1 NX EX 30`. If the key already exists, the task aborts immediately.
2. **Database Active Check (`has_active_job`)**: Before Beat enqueues a new job, it queries PostgreSQL for any existing job for that target with status `IN_PROGRESS`.

### 8. What happens if a worker crashes?
If a worker crashes mid-probe:
1. The Redis target lock expires automatically after its TTL (default: 30s).
2. The active job in PostgreSQL remains in `IN_PROGRESS` status until the maintenance task (`cleanup_stale_jobs`) detects jobs exceeding timeout thresholds and marks them `FAILED`.
3. Celery Beat continues dispatching subsequent checks on schedule, which are ingested by remaining healthy worker nodes.

---

## 2. Reliability

### 9. How are retries handled?
When a transient network error or socket disconnect occurs, the Celery task catches the exception and schedules a retry using exponential backoff with jitter:
$$\text{Delay}(n) = \min(\text{initial\_delay} \times \text{factor}^{n-1}, \text{max\_delay})$$
Configured by default with `initial_delay=1.0s`, `backoff_factor=2.0`, and `max_retries=3`.

### 10. How does stale-job recovery work?
Tether runs a scheduled maintenance task (`app.tasks.maintenance.cleanup_stale_jobs`) that scans the `jobs` table for records in `IN_PROGRESS` state whose `created_at` timestamp exceeds the maximum execution timeout ($> 120\text{s}$). Stale jobs are marked `FAILED` with an error message, and orphaned Redis locks are released.

### 11. How does alert cooldown work?
When a target enters `DOWN` state, the alert engine records `last_alerted_at = now()`. If subsequent monitoring checks continue to fail, the engine evaluates whether $(t_{\text{now}} - t_{\text{last\_alerted}}) < \text{cooldown\_seconds}$ (default: 1800s / 30 min). As long as the cooldown window is active, notifications are suppressed, preventing alert storms while the incident is being addressed.

### 12. How are recovery alerts generated?
When a target is in `DOWN` state and a monitoring check succeeds (`CheckStatus.UP`):
1. Target state transitions from `DOWN` to `UP`.
2. `consecutive_failures` resets to 0; `consecutive_successes` sets to 1.
3. If `rule.recovery_enabled == True`, the alert engine dispatches a single `RECOVERY` alert event with resolution latency metrics and updates `last_recovery_alerted_at`.

### 13. What delivery semantics do notifications provide?
Tether provides **at-least-once** notification delivery semantics. Alerts are placed into Celery delivery queues with automatic retry (up to 3 attempts). In edge cases where an external webhook server processes a payload but network connectivity drops before returning HTTP 200, the task may retry and deliver a duplicate payload.

### 14. What happens when a notification provider is unavailable?
If an SMTP server, Slack API, or generic webhook endpoint is unreachable:
1. The notification sender captures the error message and returns `(False, error_details)`.
2. The delivery record (`notification_deliveries`) is marked `FAILED` with `attempt_count += 1`.
3. Celery retries delivery with exponential backoff.
4. The core monitoring pipeline, probe persistence, and target status updates remain completely unaffected and non-blocking.

---

## 3. Security

### 15. How does authentication work?
Users authenticate via email and password (`POST /api/auth/login`). Passwords are verified against stored bcrypt hashes. Upon successful authentication, Tether issues:
1. **JWT Access Token** (15-minute expiration) containing `user_id`, `tenant_id`, and `role`.
2. **Cryptographic Refresh Token** (7-day expiration) stored in an `HttpOnly`, `SameSite=Lax` secure cookie.

### 16. Why are refresh tokens stored as hashes?
Storing raw refresh tokens in the database exposes all user sessions if the database is dumped. Tether hashes refresh tokens with SHA-256 (`token_hash`) before storing them in the `refresh_tokens` table. Even if the database is compromised, the hashes cannot be used directly as valid refresh cookies.

### 17. How does refresh-token reuse detection work?
Refresh tokens use single-use rotation: exchanging a refresh token immediately revokes it and issues a new one. If an already-revoked refresh token is presented (indicating a replay attack with an intercepted token):
1. Tether detects the reuse of a revoked token hash.
2. **Action**: Immediately revokes **all** active refresh tokens for that user family.
3. Logs a security audit event (`SECURITY_ALERT_REFRESH_TOKEN_REUSE`) and rejects the request with HTTP 401.

### 18. How does RBAC work?
Tether enforces a four-tier Role-Based Access Control hierarchy:
- `OWNER`: Full organization administration, member removal, tenant deletion.
- `ADMIN`: Target creation/deletion, notification channel CRUD, alert rule editing.
- `MEMBER`: Target configuration editing, manual check dispatch, notification tests.
- `VIEWER`: Read-only access to dashboard, target statuses, latency charts, and alert logs.
Enforced via FastAPI dependency injection (`require_role(minimum_role)`).

### 19. How is tenant isolation enforced?
Every authenticated request resolves `TenantContext` containing verified `user_id`, `tenant_id`, and `role`. All database queries explicitly filter by `Target.tenant_id == ctx.tenant.id`, `AlertEvent.tenant_id == ctx.tenant.id`, and `NotificationChannel.tenant_id == ctx.tenant.id`.

### 20. How is IDOR prevented?
Insecure Direct Object Reference (IDOR) attacks occur when an attacker modifies a target ID parameter in a URL (e.g. `GET /api/targets/42`) to view another tenant's data. Because all queries require `WHERE id = target_id AND tenant_id = ctx.tenant.id`, PostgreSQL returns `404 Not Found` if the resource belongs to another tenant.

### 21. How does SSRF protection work?
To prevent attackers from using webhooks or HTTP probes to scan internal cloud environments:
1. Schemes are restricted strictly to `http://` and `https://`.
2. Forbidden hostnames (`localhost`, `127.0.0.1`, `metadata.google.internal`, `169.254.169.254`) are blocked.
3. Direct IP literals in private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback, and link-local ranges are rejected.
4. Pre-flight DNS resolution inspects resolved IP addresses before opening socket connections.

### 22. Why is DNS pre-flight validation necessary?
An attacker can bypass simple domain string matching using DNS rebinding (pointing a domain name like `attacker.com` to `127.0.0.1` or `169.254.169.254`). Pre-flight validation resolves the hostname via `socket.getaddrinfo` and checks all resolved IP addresses against private CIDR blocks prior to establishing an HTTP connection.

### 23. What rate limits exist?
Using Redis sorted-set sliding windows (with thread-safe in-memory fallback):
- Auth endpoints (`/login`, `/register`): 10 requests / minute / IP.
- Manual check triggers (`/targets/{id}/check`): 20 requests / minute / target.
- Notification channel tests (`/notification-channels/{id}/test`): 10 requests / minute / channel.

---

## 4. Performance

### 24. What did you measure?
We measured:
1. API request throughput (requests/second) across core endpoints.
2. Latency percentiles ($p_{50}, p_{95}, p_{99}$) under 20 concurrent connections.
3. Celery worker queue latency ($\Delta t_{\text{queue}} = t_{\text{worker\_start}} - t_{\text{job\_created}}$).
4. Protocol probe execution latency across TCP, HTTP, HTTPS, and DNS probes.
5. Frontend JavaScript bundle chunk sizes before and after route-level code splitting.

### 25. What does the 373.48 req/sec benchmark actually mean?
It represents the peak steady-state throughput of a single Uvicorn/FastAPI process serving Prometheus `/metrics` over an in-process asynchronous ASGI transport with database connection pooling.

### 26. Why should that benchmark not be treated as production capacity?
In-process ASGI benchmarks eliminate physical network interface serialization, TLS negotiation overhead, and WAN packet latency. A physical multi-node production deployment with real network cards, Nginx TLS termination, and distributed database clustering will exhibit different throughput and latency profiles.

### 27. What indexes were added?
1. `ix_monitoring_results_target_timestamp`: `(target_id, timestamp DESC)` for $O(\log N)$ backward index seek on latency time-series queries.
2. `ix_jobs_target_status`: `(target_id, status)` for fast active-job deduplication lookups during Beat scheduling.
3. `ix_jobs_target_created_at`: `(target_id, created_at DESC)` for job history pagination.

### 28. Why was frontend code splitting introduced?
Initial monolithic bundle builds included Chart.js, Lucide icons, and all page components in a single ~650 KB file. Introducing `React.lazy` and `Suspense` reduced the core framework entry bundle to **231.75 KB** (gzip: **72.95 KB**), isolating heavy charting libraries into on-demand route chunks.

---

## 5. Scaling

### 29. What breaks first at very large scale?
At $\approx 20,000 - 50,000$ monitored targets with 10-second intervals:
1. **Relational Database Write I/O**: PostgreSQL experiences continuous write load from `monitoring_results` ($2,000 - 5,000\text{ inserts/sec}$).
2. **Beat Scheduling Query**: Scanning PostgreSQL for `next_check_at <= now` becomes expensive.

### 30. How would you handle more than 50,000 targets?
1. **Partitioning / Time-Series Database**: Move raw probe metrics to TimescaleDB, ClickHouse, or VictoriaMetrics, keeping PostgreSQL strictly for relational configuration and metadata.
2. **Queue Sharding**: Shard Redis queues by protocol or organization priority (`monitoring:high`, `monitoring:default`).
3. **Horizontal Worker Scaling**: Deploy workers across multiple nodes using Kubernetes Horizontal Pod Autoscalers (HPA) triggered by Redis queue length (`tether_monitoring_queue_delay_seconds`).

### 31. How would you make Celery Beat highly available?
Replace standard Celery Beat with a distributed scheduler using Raft consensus or `RedBeat` with distributed Redis locks. This allows standby Beat instances to elect a single active leader, ensuring immediate failover without task duplication.

### 32. When would PostgreSQL stop being the appropriate monitoring-result store?
When monitoring result write throughput exceeds $5,000 - 10,000\text{ inserts/sec}$ or when historical metric retention requires storing billions of rows, relational B-Trees incur high write amplification and storage bloat. At that threshold, an append-only columnar time-series engine is required.

### 33. How would you evolve the notification architecture?
For large-scale enterprise deployments:
1. Introduce a dedicated notification broker queue (e.g. Apache Kafka or AWS SQS) separate from monitoring probe queues.
2. Implement outbound rate-limiting per notification provider to comply with Slack/SendGrid API rate limits.
3. Add cryptographic webhook signatures (`X-Tether-Signature-256`) and idempotency IDs (`X-Tether-Event-ID`) for verifiable at-least-once delivery.
