# Tether — System Architecture & Component Design

## 1. System Overview
**Tether** is a distributed, multi-tenant network monitoring and alerting platform designed to continuously track the availability, responsiveness, and protocol-level health of networked endpoints (TCP, HTTP, HTTPS, DNS).

```text
                                  ┌────────────────────────┐
                                  │   React 18 Dashboard   │
                                  │  (TypeScript / Vite)   │
                                  └───────────┬────────────┘
                                              │ HTTP / JSON
                                              ▼
                                  ┌────────────────────────┐
                                  │  Nginx Reverse Proxy   │
                                  │  (TLS / Rate Limiting) │
                                  └───────────┬────────────┘
                                              │ Reverse Proxy
                                              ▼
                                  ┌────────────────────────┐
                                  │    FastAPI Backend     │
                                  │  (Auth, RBAC, Metrics) │
                                  └─────┬───────────┬──────┘
                                        │           │
                       ┌────────────────┴─────┐     │ Task Dispatch
                       ▼                      ▼     ▼
                ┌──────────────┐         ┌───────────────────┐
                │  PostgreSQL  │         │   Redis 7 Broker  │
                │  (16 Alpine) │         │ (Queues & Locks)  │
                └──────────────┘         └─────────┬─────────┘
                       ▲                           │
                       │ Task Results & State      │ Task Consumption
                       │                           ▼
                       │                 ┌───────────────────┐
                       │                 │   Celery Workers  │
                       │                 │  (Mesh Instances) │
                       │                 └─────────┬─────────┘
                       │                           │
                       │            ┌──────────────┼──────────────┐
                       │            ▼              ▼              ▼
                       │       ┌─────────┐    ┌─────────┐    ┌─────────┐
                       │       │TCP Probe│    │HTTP/S   │    │DNS Probe│
                       │       └────┬────┘    └────┬────┘    └────┬────┘
                       │            └──────────────┼──────────────┘
                       │                           │
                       │                           ▼
                       │                 ┌───────────────────┐
                       │                 │   Alert Engine    │
                       │                 │  (State Machine)  │
                       │                 └─────────┬─────────┘
                       │                           │
                       │                           ▼
                       │                 ┌───────────────────┐
                       └─────────────────┤  Notification     │
                                         │  Router (Email /  │
                                         │  Slack / Webhook) │
                                         └───────────────────┘
```

---

## 2. Component Decomposition

### 2.1 API & Control Plane (FastAPI)
- **Authentication & Multi-Tenancy**: Resolves incoming JWT bearer tokens, validates claims against the tenant database, enforces Role-Based Access Control (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`), and scopes all database operations to `TenantContext`.
- **Target Management**: CRUD endpoints for monitoring targets with customizable intervals ($10\text{s} - 86400\text{s}$), timeout thresholds, and protocol parameters.
- **Observability Probes**: Exposes Prometheus metrics on `/metrics`, liveness on `/health/live`, and dependency readiness on `/health/ready`.

### 2.2 Periodic Scheduler (Celery Beat)
- **Role**: Evaluates database targets where `enabled = True` and `next_check_at <= now_utc`.
- **Single Instance Guarantee**: Celery Beat runs as a single logical process. It dispatches lightweight check tasks to the Redis broker and advances `target.next_check_at` to prevent dispatch storms.

### 2.3 Distributed Worker Mesh (Celery)
- **Concurrency & Scaling**: Workers consume monitoring jobs from Redis queues. Worker count scales horizontally with workload size.
- **Distributed Concurrency Guard**: Before probing, workers acquire a short-lived Redis lock (`tether:lock:target:{target_id}`). If a duplicate task is dequeued, it exits immediately.
- **Exponential Backoff**: Transient connection errors trigger automatic retries with exponential backoff:
  $$\text{Delay}(n) = \min(\text{initial\_delay} \times \text{factor}^{n-1}, \text{max\_delay})$$

### 2.4 Monitoring Strategy Registry
Probes follow a uniform interface (`BaseProbe`):
- **TCP Probe**: Non-blocking socket connect measuring round-trip connection latency.
- **HTTP/HTTPS Probe**: `httpx`-driven HTTP client validating status code ranges, custom headers, keyword presence, and TLS certificate expiration.
- **DNS Probe**: Resolves `A`, `AAAA`, `CNAME`, and `MX` records against authoritative or custom nameservers.

### 2.5 State Machine Alerting Engine
- Tracks consecutive successes and failures per target.
- **Outage Detection**: When `consecutive_failures == failure_threshold`, transitions target to `DOWN` and queues an `OUTAGE` event.
- **Cooldown Suppression**: Subsequent failures while in `DOWN` state do not spam notifications during `cooldown_seconds`.
- **Recovery Detection**: The first successful probe transitions target to `UP` and dispatches a single `RECOVERY` notification.

---

## 3. Data Flow Architecture

```text
[Celery Beat Scheduler]
       │ (1. Enqueue job when next_check_at <= now)
       ▼
 [Redis Task Queue]
       │ (2. Worker dequeues task)
       ▼
[Celery Worker Thread]
       │ (3. Acquire Redis target lock & DB active check)
       ├──► Locked? ──► Abort duplicate check
       │
       ▼ (4. Execute Protocol Probe: TCP / HTTP / DNS)
[Target Endpoint]
       │ (5. Probe response or socket timeout)
       ▼
[Monitoring Result Persistence] ──► INSERT INTO monitoring_results
       │
       ▼ (6. Update target state: UP / DOWN / UNKNOWN)
[Target Record Update] ──► UPDATE targets SET consecutive_failures, status
       │
       ▼ (7. Evaluate Alert State Machine)
[Alert Engine]
       ├──► Threshold reached? ──► Dispatch OUTAGE to Notification Queue
       ├──► Recovered? ──► Dispatch RECOVERY to Notification Queue
       └──► In Cooldown? ──► Suppress notification
```
