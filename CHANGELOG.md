# Changelog

All notable changes to the **Tether** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-03

### Added
- **Multi-Protocol Monitoring**:
  - Asynchronous TCP socket probe with latency measurement and error categorization.
  - HTTP probe with status code evaluation, custom headers, and body matching.
  - HTTPS probe with SSL/TLS handshake inspection and certificate validity tracking.
  - DNS probe supporting `A`, `AAAA`, `CNAME`, and `MX` records via configurable nameservers.
- **Distributed Task Mesh & Scheduling**:
  - Celery Beat dynamic periodic scheduler with per-target intervals.
  - Distributed Redis locking (`tether:lock:target:{id}`) and PostgreSQL active job deduplication.
  - Task execution retry engine with exponential backoff and jitter.
- **Alerting & Notification Engine**:
  - Threshold-driven target state machine (`consecutive_failures >= threshold` $\rightarrow$ `OUTAGE`).
  - Outage cooldown suppression and recovery detection (`RECOVERY`).
  - Multi-channel notification routing supporting SMTP Email, Slack Webhooks, and Generic HTTP Webhooks.
  - Notification delivery tracking with retry backoff and failure isolation.
- **Multi-Tenancy, Authentication & RBAC**:
  - Secure bcrypt password hashing and JWT access token issuance.
  - Single-use refresh token rotation with anti-replay family revocation.
  - Role-Based Access Control (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`).
  - Tenant context injection and strict query-level tenant isolation (IDOR protection).
  - Security audit logging with sensitive credential redaction.
- **Observability & Operational Hardening**:
  - Prometheus metrics instrumentation (`/metrics`) tracking HTTP traffic, Celery tasks, and queue latency.
  - Structured JSON logging with `X-Request-ID` correlation across distributed components.
  - Liveness (`/health/live`) and readiness (`/health/ready`) probes.
  - SSRF protection on notification channels and webhooks.
  - Redis sliding-window rate limiting on sensitive endpoints.
- **Frontend Dashboard**:
  - Single Page Application built with React 18, TypeScript, Tailwind CSS, and TanStack Query.
  - Route-level code splitting (`React.lazy` + `Suspense`) for optimized bundle delivery.
  - Live system diagnostics page (`/system`), target latency graphs, and team management.
- **Testing & Tooling**:
  - 100 passing backend pytest tests with mock isolation.
  - 13 passing frontend Vitest tests.
  - In-process load benchmark runner (`load_tests/benchmark.py`) and Locust scenario (`load_tests/locustfile.py`).
  - Deterministic incident lifecycle simulation script (`scripts/simulate_incident.py`).
  - Production Nginx reverse proxy configuration and multi-stage Dockerfiles.
