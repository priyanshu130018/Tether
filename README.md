# Tether

Distributed network monitoring and alerting platform built with FastAPI, Celery, Redis, PostgreSQL, React, and Docker.

Tether asynchronously monitors TCP, HTTP/HTTPS, and DNS targets, tracks health state transitions, detects outages via a threshold state machine, and routes alerts through SMTP email, Slack webhooks, and generic HTTP endpoints with tenant isolation and role-based access control.

```text
================================================================================
  Version: v1.0.0  |  License: MIT  |  Backend: 100/100 Tests  |  Frontend: 13/13 Tests
================================================================================
```

---

## 1. Feature Matrix

| Capability | Implementation | Technical Description |
|---|---|---|
| **Monitoring** | TCP / HTTP / HTTPS / DNS Probes | Extensible strategy registry validating ports, TLS certificates, HTTP assertions, and DNS records. |
| **Scheduling** | Celery Beat | Single-instance periodic dispatcher evaluating per-target check intervals ($10\text{s} - 86400\text{s}$). |
| **Background Execution** | Celery Worker Mesh | Horizontally scalable worker pool consuming from Redis FIFO queues. |
| **Queue & Locking** | Redis 7 | Sub-millisecond queue broker and atomic distributed locking (`SET NX EX`). |
| **Persistence** | PostgreSQL 16 | Relational configuration, time-series probe history, and immutable audit logs. |
| **Alert State Machine** | Threshold State Machine | Fired after $N$ consecutive failures; suppresses alert spam via cooldown windows. |
| **Notifications** | SMTP / Slack / Webhooks | Multi-channel router with exponential retry backoff ($2^n$) and failure isolation. |
| **Authentication** | JWT + Refresh Token Rotation | Bcrypt password hashing, 15-min access tokens, and anti-replay token family revocation. |
| **Authorization & RBAC** | Multi-Tenant Scoping | Role hierarchy (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`) with strict query-level isolation. |
| **Security Controls** | SSRF Defense + Rate Limiting | Pre-flight DNS validation, private CIDR blocking, and nanosecond sliding-window rate limiters. |
| **Observability** | Prometheus + Structured JSON | Cloud-native `/metrics`, `/health/live`, `/health/ready`, and correlation IDs (`X-Request-ID`). |
| **Frontend** | React 18 + TypeScript + Vite | Observability dashboard with live diagnostics, latency charts, and route-level code splitting. |
| **Deployment** | Docker Compose + Nginx | Reverse proxy with HTTP routing, security headers, and health probes. |

---

## 2. Architecture & Data Flow

```text
                    React Dashboard (TypeScript / Vite)
                                  │
                                  ▼
                    Nginx Reverse Proxy (HTTP / Headers)
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

### Why Celery Beat Runs as a Single Logical Process
Celery Beat operates as a single logical clock calculating next target check times. Running multiple Beat schedulers against the same Redis broker without distributed leader election results in duplicate task floods, dispatching redundant probe checks and overwhelming workers and monitored targets.

---

## 3. Monitored Target Execution Sequence

```text
[Celery Beat Scheduler]
       │ (1. Periodic tick queries DB: enabled = True AND next_check_at <= now)
       ▼
 [Redis Task Queue]
       │ (2. Worker dequeues job)
       ▼
[Celery Worker Instance]
       │ (3. Acquire Redis lock: tether:lock:target:{id})
       ├──► Lock held? ──► Terminate duplicate task immediately
       │
       ▼ (4. Execute Protocol Probe: TCP / HTTP / HTTPS / DNS)
[Target Endpoint]
       │ (5. Connection result or socket timeout)
       ▼
[PostgreSQL Database] ──► Record monitoring_results & update target state
       │
       ▼ (6. Evaluate Alert State Machine)
[Alert Engine]
       ├──► Consecutive failures == threshold? ──► Dispatch OUTAGE alert
       ├──► Recovered after outage? ──► Dispatch RECOVERY alert
       └──► Within cooldown window? ──► Suppress notification (prevent alert spam)
```

---

## 4. Reliability & Security Models

### 4.1 Reliability Model
- **Distributed Concurrency Guard**: Redis atomic locks (`SET key 1 NX EX 30`) and database active-job checks eliminate race conditions and duplicate task execution.
- **Exponential Retry Backoff**: Transient network errors trigger retries with exponential backoff:
  $$\text{Delay}(n) = \min(\text{initial\_delay} \times \text{factor}^{n-1}, \text{max\_delay})$$
- **Stale Job Recovery**: Periodic maintenance task automatically identifies and marks orphaned `IN_PROGRESS` jobs as `FAILED` after execution timeouts.
- **Alert Storm Cooldown**: Threshold-based outage detection ($N$ consecutive failures) suppresses continuous notifications during active incidents.

### 4.2 Security Model
- **Anti-Replay Refresh Token Rotation**: Single-use cryptographic refresh tokens. Presenting an already-revoked token hash triggers immediate revocation of all active sessions for that user family.
- **Multi-Tenant Scoping & IDOR Defense**: All database queries enforce `WHERE tenant_id = ctx.tenant.id`, preventing cross-tenant data access.
- **SSRF Protection**: Outbound webhook and probe URLs are validated against private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.1`), and cloud metadata (`169.254.169.254`) with pre-flight DNS resolution.
- **Sliding-Window Rate Limiting**: Redis sorted-set rate limiters with nanosecond-precision member keys protect auth endpoints, manual checks, and test dispatches.

---

## 5. Performance Snapshot

### Benchmark Configuration & Results
- **Environment**: Python 3.10.9 (CPython) on Uvicorn ASGI Server, PostgreSQL 16 Alpine, Redis 7 Alpine.
- **Harness**: In-process asynchronous ASGI transport (`load_tests/benchmark.py`), 500 requests @ concurrency 20.

| Metric | Measured Value | Context |
|---|---|---|
| **API Throughput** | **373.48 req/sec** | Measured on `/metrics` endpoint |
| **Median Latency ($p_{50}$)** | **41.9 ms** | Measured across active connection pool |
| **Tail Latency ($p_{95}$)** | **111.8 ms** | Under 20 concurrent client requests |
| **Worker Queue Transit Delay** | **$\le 12\text{ ms}$** | Steady-state Redis queue transit time |
| **Frontend Entry Chunk Size** | **231.75 KB (gzip: 72.95 KB)** | Optimized Vite build with `React.lazy` code splitting |

> [!NOTE]
> *Benchmark Disclaimer*: These measurements reflect in-process local benchmarking designed to profile framework overhead, database query efficiency, and serialization. They should not be interpreted as physical multi-node production capacity guarantees.

---

## 6. Quickstart & Local Development

### 6.1 Prerequisites
- Docker & Docker Compose (v2.20+)
- Python 3.10+ (for local scripts/tests)
- Node.js 18+ (for frontend tests/development)

### 6.2 One-Command Platform Startup

Clone this repository, then follow the Quickstart instructions below:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Launch full platform stack with Docker Compose
docker compose up --build
```

### 6.3 Service Endpoints

| Service | URL | Context |
|---|---|---|
| **React Dashboard** | <http://localhost:3000> | Single Page Application |
| **REST API & Swagger Docs** | <http://localhost:8000/docs> | OpenAPI 3.0 Interactive Documentation |
| **Prometheus Metrics** | <http://localhost:8000/metrics> | Real-time Prometheus Collector |
| **Liveness Probe** | <http://localhost:8000/health/live> | Process Liveness (`200 OK`) |
| **Readiness Probe** | <http://localhost:8000/health/ready> | Dependency Check (`Postgres + Redis`) |

---

## 7. Automated Test Suites & Verification

### 7.1 Run Full Backend Test Suite (100 Tests)
```bash
cd backend
python -m pytest -v
```

### 7.2 Run Frontend Test Suite & Build (13 Tests)
```bash
cd frontend
npm test -- --run
npm run build
```

### 7.3 Run Interactive Portfolio Demo
```bash
python scripts/final_demo.py
```

### 7.4 Run Incident Lifecycle Simulation
```bash
python scripts/simulate_incident.py
```

---

## 8. Repository Structure

```text
tether/
├── backend/
│   ├── app/
│   │   ├── alerts/          # Outage detection state machine & delivery
│   │   ├── api/routes/      # REST API route handlers (Auth, Targets, Alerts)
│   │   ├── core/            # Config, DB pool, auth, metrics, rate limits
│   │   ├── monitoring/      # Protocol strategy probes (TCP, HTTP, HTTPS, DNS)
│   │   ├── notifications/   # Multi-channel senders (SMTP, Slack, Webhooks)
│   │   └── tasks/           # Celery background tasks, locks, maintenance
│   ├── tests/               # 100 passing pytest unit & integration tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/      # UI badges, modals, status cards
│   │   ├── pages/           # Dashboard, Targets, Alerts, System, Team
│   │   └── context/         # AuthContext & JWT lifecycle
│   ├── package.json
│   └── Dockerfile
│
├── docs/
│   ├── architecture.md
│   ├── architecture-decisions.md
│   ├── interview-guide.md
│   ├── portfolio-case-study.md
│   ├── screenshots.md
│   ├── resume-facts.md
│   ├── monitoring-sequence.md
│   ├── security-architecture.md
│   ├── security-review.md
│   ├── performance-baseline.md
│   ├── performance-report.md
│   ├── resilience-matrix.md
│   ├── technical-debt.md
│   ├── runbook.md
│   └── release.md
│
├── scripts/
│   ├── final_demo.py
│   ├── simulate_incident.py
│   └── portfolio_demo.md
│
├── load_tests/
│   ├── benchmark.py
│   └── locustfile.py
│
├── nginx/
│   └── nginx.conf
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── LICENSE
└── README.md
```

---

## 9. Known Limitations

Tether v1.0.0 is an open-source distributed monitoring platform with the following intentional boundaries:
1. **Single-Instance Beat Scheduler**: Celery Beat runs as a single logical process rather than a multi-node Raft leader-election cluster.
2. **Relational Result Storage**: Probe results are written to PostgreSQL; high-throughput clusters ($> 50,000$ targets) should consider time-series storage (e.g. TimescaleDB or ClickHouse).
3. **At-Least-Once Delivery**: In rare network drop scenarios during third-party dispatch, notifications may be retried.
4. **No Enterprise SAML/SSO**: Authentication is native JWT + RBAC without external enterprise identity providers (e.g. Okta).

---

## 10. Documentation Index

- **[System Architecture](docs/architecture.md)**: Detailed component breakdown, threading, and data flow.
- **[Interview Defense Guide](docs/interview-guide.md)**: 33 systems design answers across architecture, reliability, security, and scaling.
- **[Portfolio Case Study](docs/portfolio-case-study.md)**: Engineering case study detailing problems, hard challenges, and trade-offs.
- **[5-Minute Demo Script](scripts/portfolio_demo.md)**: Structured live interview demonstration script.
- **[Dashboard UI Views](docs/screenshots.md)**: Catalog of UI views, latency charts, and status indicators.
- **[Verified Resume Facts](docs/resume-facts.md)**: Factual technical bullet points and measured metrics.
- **[Monitoring Sequence](docs/monitoring-sequence.md)**: Sequence diagrams for probe scheduling and execution.
- **[Security Architecture](docs/security-architecture.md)**: Threat defense, SSRF mitigations, token rotation, and RBAC model.
- **[Architecture Decision Records (ADRs)](docs/architecture-decisions.md)**: ADR-001 through ADR-008 documenting all architectural trade-offs.
- **[Performance Baseline](docs/performance-baseline.md)**: Benchmark methodology and baseline numbers.
- **[Performance Report](docs/performance-report.md)**: Database indexing analysis, latency percentiles, and bundle metrics.
- **[Resilience Matrix](docs/resilience-matrix.md)**: Failure mode analysis and self-healing matrices.
- **[Technical Debt Register](docs/technical-debt.md)**: Documented limitations and scaling bottlenecks.
- **[Operations Runbook](docs/runbook.md)**: Production incident management and disaster recovery playbooks.
- **[Release Policy](docs/release.md)**: Versioning policy, release checklist, and rollback procedures.

---

## 11. License

Tether is open-source software licensed under the [MIT License](LICENSE).
