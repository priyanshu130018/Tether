# Tether — System Resilience & Failure Recovery Matrix

## 1. Resilience Philosophy
Tether is architected under the core assumption that **any component (database, cache, workers, scheduler, third-party network) can and will fail**. The system must gracefully degrade, retry with backoff, isolate blast radiuses, and automatically self-heal once dependencies recover.

---

## 2. Failure Mode & Recovery Matrix

| Component | Failure Scenario | Detection Mechanism | System Behavior & Mitigation | Recovery Action |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | Primary database unavailable or connection drops | `/health/readiness` fails with `503`, SQLAlchemy pool disconnect | API serves health check status with detailed component status. Tasks catch connection errors, Celery retries check with exponential backoff ($2^n$). | Connection pool auto-reconnects with `pool_pre_ping=True`. Retried tasks complete normally. |
| **Redis Cache / Broker** | Redis instance crashes or becomes unreachable | Redis connection timeouts, `/health/readiness` reports `redis=unhealthy` | Rate limiters fallback to in-memory sliding window. Distributed locks degrade gracefully to database-level active job deduplication (`has_active_job`). Worker checks queue when Redis restores. | Redis restarts, connection pool reconnects, distributed locking resumes. |
| **Celery Worker Mesh** | Worker container crashes mid-check execution | `celery_task_id` heartbeat expires, job remains `IN_PROGRESS` | Stale job cleanup maintenance task (`cleanup_stale_jobs`) scans for jobs exceeding timeout and marks them `FAILED`. Database lock releases on TTL expiration. | Worker mesh orchestrator (Docker Compose / K8s) restarts worker container; next scheduled beat dispatches fresh job. |
| **Celery Beat Scheduler** | Beat scheduler process halts or partitions | `tether_target_next_check_at` lag grows, Prometheus alert fires | Workers continue processing queued jobs. Manual API checks (`POST /api/targets/{id}/check`) remain functional for on-demand verification. | Beat container restarts, queries DB for targets with `next_check_at <= now_utc`, and catches up on monitoring cadence. |
| **Notification Provider (Slack/SMTP/Webhook)** | Third-party endpoint down, 5xx status, or SSL handshake timeout | `NotificationDelivery` status set to `FAILED`, exception captured | Notification failure is caught and logged. Target status update and monitoring results are NOT aborted. Delivery retried up to 3 times with backoff. | Once provider recovers, subsequent state transitions or test notifications succeed cleanly. |
| **Monitored Target Unreachable** | Target network partition, DNS resolution failure, or port closed | Probe returns `CheckStatus.DOWN` with explicit error classification | Consecutive failure counter increments. If `consecutive_failures == failure_threshold`, alert state machine fires single `OUTAGE` event. Subsequent failures enter cooldown suppression. | On target recovery, single `RECOVERY` event is dispatched and counter resets. |
| **Malicious / Abuse Traffic** | Rapid spamming of manual checks or token refresh endpoint | Sliding window rate limiter triggered (`> 20 req/min`) | HTTP `429 Too Many Requests` returned with informative retry message. No Celery tasks are spawned, preventing queue starvation. | Client waits for rate limit window to slide forward before making further calls. |

---

## 3. Incident Lifecycle State Transition Verification

```text
[Healthy State: UP]
   │
   ├─► Check 1: FAIL (consecutive_failures = 1) ──► No Alert
   ├─► Check 2: FAIL (consecutive_failures = 2) ──► No Alert
   ├─► Check 3: FAIL (consecutive_failures = 3 == threshold) ──► [OUTAGE EVENT GENERATED]
   │                                                                     │
   ├─► Check 4: FAIL (consecutive_failures = 4, in cooldown) ──► Suppressed (No Spam)
   │
   ▼
[Recovery Check: SUCCESS] (consecutive_successes = 1) ──► [RECOVERY EVENT GENERATED]
   │
   ▼
[Healthy State Restored: UP] (consecutive_failures = 0)
```

Verified programmatically via `scripts/simulate_incident.py` and automated test suite `tests/test_phase8_resilience_and_security.py`.
