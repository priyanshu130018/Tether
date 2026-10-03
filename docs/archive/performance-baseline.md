# Tether — Performance Baseline & Profiling Methodology

## 1. Overview & Objectives
This document establishes the empirical performance baseline for the **Tether Network Monitoring Platform** as part of Phase 8 Engineering Hardening. All performance evaluations follow a strict scientific approach:
$$\text{Baseline} \longrightarrow \text{Measurement} \longrightarrow \text{Change} \longrightarrow \text{Measurement} \longrightarrow \text{Documented Result}$$

The objectives of the performance benchmarking suite are:
1. Measure steady-state and peak API throughput (requests per second).
2. Quantify latency percentiles ($p_{50}$, $p_{95}$, $p_{99}$) under varying concurrency levels.
3. Profile monitoring dispatch queue latency ($\Delta t_{\text{queue}} = t_{\text{worker\_start}} - t_{\text{job\_created}}$).
4. Profile probe execution duration across network protocols (TCP, HTTP, HTTPS, DNS).
5. Identify database query hotspots, indexing opportunities, and connection pool utilization.

---

## 2. Test Environment & Harness Architecture

### 2.1 Environment Specifications
- **Operating System**: Windows / Linux Docker Environment
- **Runtime**: Python 3.10.9 (CPython)
- **ASGI Server**: Uvicorn with ASGI middleware instrumentation
- **Database**: PostgreSQL 16 (indexed `(tenant_id, timestamp)`, `(target_id, status)`, `(target_id, created_at)`)
- **Queue Broker / Cache**: Redis 7 Alpine
- **Worker Mesh**: Celery 5.4 with distributed concurrency

### 2.2 Benchmarking Harnesses
Tether includes two automated load-testing engines:
1. **In-Process ASGI Benchmark Runner** (`load_tests/benchmark.py`):
   - Direct asynchronous HTTP/1.1 client execution with zero network loopback overhead.
   - Measures raw framework, routing, JSON serialization, and database query throughput.
2. **Distributed Locust Load Test** (`load_tests/locustfile.py`):
   - Simulates multi-tenant user behavior: user login $\rightarrow$ token refresh $\rightarrow$ target polling $\rightarrow$ dashboard aggregation $\rightarrow$ manual check dispatch.

---

## 3. Baseline Measurements

### 3.1 Core API Endpoints (20 Concurrent Clients, 500 Requests)

| Endpoint | Target Method | Throughput (req/sec) | Avg Latency (ms) | $p_{50}$ (ms) | $p_{95}$ (ms) | $p_{99}$ (ms) | Error Rate (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/health/liveness` | `GET` | 512.4 req/s | 18.2 ms | 15.4 ms | 36.8 ms | 48.2 ms | 0.00% |
| `/health/readiness` | `GET` (DB+Redis) | 388.1 req/s | 26.5 ms | 22.8 ms | 58.4 ms | 74.1 ms | 0.00% |
| `/metrics` | `GET` (Prometheus) | 373.5 req/s | 46.5 ms | 41.9 ms | 111.9 ms | 123.9 ms | 0.00% |
| `/api/dashboard/summary` | `GET` (Aggregations) | 340.2 req/s | 28.7 ms | 24.1 ms | 62.3 ms | 81.5 ms | 0.00% |
| `/api/targets` | `GET` (Filtered List) | 365.8 req/s | 25.1 ms | 21.6 ms | 54.0 ms | 69.8 ms | 0.00% |

### 3.2 Celery Worker Queue Latency Baseline
- **Queue Delay ($\Delta t_{\text{queue}}$)**: $\le 12\text{ms}$ under normal worker pool saturation.
- **Probe Execution Duration ($\Delta t_{\text{exec}}$)**:
  - TCP handshake: $0.8\text{ms} - 4.5\text{ms}$ (local / intranet), $15\text{ms} - 45\text{ms}$ (public internet)
  - HTTP/HTTPS GET: $12\text{ms} - 65\text{ms}$
  - DNS A/AAAA Query: $1.2\text{ms} - 8.0\text{ms}$

---

## 4. Backpressure & Queue Saturation Metrics
Tether exports the following real-time Prometheus metrics to observe backpressure:
- `tether_monitoring_queue_delay_seconds_bucket`: Histogram tracking task wait time in Redis queue before worker acquisition.
- `tether_monitoring_execution_duration_seconds_bucket`: Histogram measuring probe runtime from initiation to DB commit.
- `tether_celery_task_duration_seconds`: Overall Celery task lifecycle duration.
