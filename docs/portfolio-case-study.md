# Tether — Comprehensive Engineering Portfolio Case Study

## 1. Executive Summary & Problem Context
Modern distributed infrastructure depends on numerous internal and external network services: APIs, databases, authentication servers, and DNS resolvers. Relying solely on internal application logs or client telemetry often leaves teams blind when external network paths, SSL certificates, or third-party gateways fail.

**Tether** is an asynchronous, multi-tenant network monitoring platform and alerting engine built with FastAPI, Celery, Redis, PostgreSQL, and React. It periodically validates the availability, latency, and protocol compliance of TCP, HTTP, HTTPS, and DNS targets, detects outages through a state machine, and routes notifications via email, Slack, and webhooks while enforcing tenant isolation and RBAC.

---

## 2. Engineering Constraints & Requirements

1. **Multi-Protocol Extensibility**: Support TCP, HTTP, HTTPS (with TLS inspection), and DNS without creating siloed scheduling engines.
2. **Distributed Concurrency & Deduplication**: Ensure that long-running checks or scheduler bursts never produce duplicate checks or race conditions.
3. **Alert Storm Prevention**: Prevent notification floods during intermittent network jitter or extended outages.
4. **Multi-Tenant Security Boundaries**: Enforce tenant isolation and Insecure Direct Object Reference (IDOR) protection across all CRUD operations.
5. **SSRF & Attack Defense**: Prevent outbound probes and webhooks from being weaponized against private infrastructure or cloud metadata endpoints.
6. **Observability**: Provide cloud-native Prometheus telemetry, structured correlation logs, and dependency readiness checks.

---

## 3. High-Level Architecture

```text
                    React Dashboard (TypeScript / Vite)
                                  │
                                  ▼
                    Nginx Reverse Proxy (TLS / Headers)
                                  │
                                  ▼
                      FastAPI Backend API
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
     PostgreSQL 16          Redis 7 Broker            Auth & RBAC
  (Relational Storage)      (Queues & Locks)      (Tenant Isolation)
          ▲                       │                       │
          │                       ▼                       │
          │               Celery Worker Mesh ◄────────────┘
          │               (Worker 1 .. Worker N)
          │                       │
          │        ┌──────────────┼──────────────┐
          │        ▼              ▼              ▼
          │    TCP Probe      HTTP Probe     DNS Probe
          │        │              │              │
          └────────┴──────────────┼──────────────┘
                                  ▼
                             Alert Engine
                         (State Machine & Cooldown)
                                  │
                                  ▼
                         Notification Router
                       /          |          \
                  SMTP Email    Slack      Webhook
```

---

## 4. Hard Engineering Challenges & Solutions

### Challenge 1: The Single-Scheduler / Distributed Worker Paradox
- **Problem**: Scaling Celery workers horizontally is straightforward, but running multiple Celery Beat schedulers leads to duplicate periodic tasks being enqueued simultaneously.
- **Solution**: Celery Beat runs as a dedicated single logical process that advances `next_check_at` before task enqueueing. Celery workers acquire a Redis atomic lock (`SET tether:lock:target:{id} 1 NX EX 30`) prior to execution. If a duplicate job reaches a worker, it exits immediately.

### Challenge 2: Alert Storm Prevention & Recovery Detection
- **Problem**: Flapping network connections or services that remain down for hours generate hundreds of noisy notifications that cause alert fatigue.
- **Solution**: Implemented a threshold-driven state machine:
  - An `OUTAGE` event is generated only after $N$ consecutive failures (`consecutive_failures == failure_threshold`).
  - Subsequent failures while `DOWN` enter a configurable cooldown window (e.g. 1800s) during which notifications are suppressed.
  - The first successful check transitions the target to `UP`, resets failure counters, and dispatches a single `RECOVERY` alert.

### Challenge 3: Anti-Replay Refresh Token Rotation
- **Problem**: Long-lived refresh tokens stored on client devices are susceptible to interception and replay attacks.
- **Solution**: Implemented single-use refresh token rotation with family revocation. If an already-revoked token hash is presented, Tether flags token compromise, immediately invalidates all active sessions for that user family, logs a security audit event, and rejects the exchange with HTTP 401.

### Challenge 4: Server-Side Request Forgery (SSRF) Defense
- **Problem**: User-configured webhooks or HTTP probe targets could point to internal VPC services (`10.0.0.1`), loopback (`127.0.0.1`), or cloud metadata endpoints (`169.254.169.254`).
- **Solution**: Built multi-tiered SSRF validation: scheme whitelisting, IP literal inspection, and pre-flight DNS resolution via `socket.getaddrinfo` to verify that resolved IP addresses do not belong to private or link-local subnets before opening network sockets.

---

## 5. Observability & Performance Snapshot

### 5.1 Prometheus Telemetry & Metrics
- `tether_monitoring_queue_delay_seconds`: Measures task wait time in Redis queues before worker acquisition.
- `tether_monitoring_execution_duration_seconds`: Measures network probe execution time before persistence.
- `tether_http_requests_total` & `tether_http_request_duration_seconds`: API request tracking with normalized paths.

### 5.2 Performance Profiling (Local Benchmark)
- **Environment**: Python 3.10.9 (CPython) on Uvicorn ASGI Server, PostgreSQL 16 Alpine, Redis 7 Alpine.
- **Harness**: In-process asynchronous ASGI transport (`load_tests/benchmark.py`), 500 requests @ concurrency 20.
- **Results**:
  - API Throughput: **373.48 req/sec**
  - Median Latency ($p_{50}$): **41.9 ms**
  - Tail Latency ($p_{95}$): **111.8 ms**
  - Worker Queue Transit Latency: **$\le 12\text{ ms}$**

> [!NOTE]
> *Disclaimer*: These metrics reflect local in-process benchmarking designed to profile framework overhead and query efficiency. They should not be interpreted as physical multi-node production capacity guarantees.

---

## 6. Technical Debt & Scaling Roadmap

1. **Distributed Beat HA**: Migrate from single Celery Beat to Raft leader-elected scheduling (`RedBeat`) for zero-downtime scheduler failover.
2. **Time-Series Storage**: Partition `monitoring_results` or adopt ClickHouse / TimescaleDB for high write throughput ($> 50,000$ targets).
3. **Notification Idempotency**: Add `X-Tether-Event-ID` headers to outbound webhooks for receiver-side deduplication.
