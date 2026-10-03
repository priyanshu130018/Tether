# Tether — 5-Minute Technical Interview Demonstration Guide

This guide provides a structured, timed, 5-minute live demonstration script for engineering interviews and technical portfolio reviews.

---

## Timeline & Demonstration Script

### [0:00 - 0:30] Problem Statement & Core Value
- **Spoken Summary**:
  > "In distributed environments, network health cannot be inferred solely from application logs. Tether is a distributed network monitoring and alerting platform designed to continuously test availability and protocol compliance across TCP, HTTP/HTTPS, and DNS endpoints. It decouples periodic scheduling from asynchronous execution using Celery and Redis, enforces multi-tenant RBAC with JWT token rotation, and prevents alert storms through a threshold-driven state machine."

---

### [0:30 - 1:15] Architecture Walkthrough
- **Visual**: Point to the primary architecture diagram in [`docs/architecture.md`](../docs/architecture.md) or [`README.md`](../README.md).
- **Key Talking Points**:
  1. **Control Plane**: FastAPI handling tenant authentication, RBAC, target configurations, and metrics export.
  2. **Scheduler (Celery Beat)**: Stateful periodic dispatcher evaluating target intervals and pushing check tasks to Redis.
  3. **Worker Mesh (Celery)**: Distributed worker mesh acquiring Redis atomic locks (`SET key 1 NX EX`) to prevent duplicate runs before dispatching protocol probes.
  4. **State Machine & Alerting**: Outage detection requiring $N$ consecutive failures with cooldown suppression to eliminate notification spam.

---

### [1:15 - 2:00] Live Healthy State Verification
- **Action**: Run the interactive demo or open the React dashboard (<http://localhost:3000>):
  ```bash
  python scripts/final_demo.py
  ```
- **What to Highlight**:
  - Tenant organization creation (`Acme Corp Infrastructure`) and owner JWT generation.
  - Multi-protocol target configuration: HTTPS (`api.acme.corp:443`), TCP (`db.acme.corp:5432`), and DNS (`ns1.acme.corp:53`).
  - Healthy probe execution recording sub-30ms latency with 0 alerts fired.

---

### [2:00 - 3:00] Simulated Outage & State Machine Threshold
- **Spoken Summary**:
  > "Now let's observe how Tether handles failures. Rather than alerting on single transient blips, we require 3 consecutive failures."
- **Demonstration**:
  - Probe 1 fails (consecutive = 1/3) $\rightarrow$ No alert generated.
  - Probe 2 fails (consecutive = 2/3) $\rightarrow$ No alert generated.
  - Probe 3 fails (consecutive = 3/3) $\rightarrow$ **Threshold reached**. Target transitions to `DOWN`, generating a single `OUTAGE` alert routed to Slack and Email.
  - Probe 4 fails (consecutive = 4) $\rightarrow$ Cooldown active ($1800\text{s}$) $\rightarrow$ **Notification suppressed**. No alert spam.

---

### [3:00 - 4:00] Target Recovery & Notification Delivery
- **Spoken Summary**:
  > "When the monitored service recovers, Tether detects the first successful check, resets failure counters, transitions the target back to `UP`, and fires a single `RECOVERY` notification."
- **Demonstration**:
  - Service restored $\rightarrow$ Status `UP` (Latency: 21.8ms).
  - Single `RECOVERY` alert dispatched to Slack and Email.
  - Target consecutive failures reset to 0; consecutive successes set to 1.

---

### [4:00 - 5:00] Observability, Security Controls & Architecture Defense
- **Key Highlights to Show**:
  1. **Prometheus Metrics**: Curl `GET /metrics` showing `tether_monitoring_queue_delay_seconds` and `tether_monitoring_execution_duration_seconds`.
  2. **Security Controls**:
     - Pre-flight DNS SSRF protection blocking private RFC1918 and cloud metadata endpoints.
     - Single-use refresh token rotation with anti-replay family revocation.
     - Sliding-window rate limiters on manual checks and test dispatches.
  3. **Verification**: 100 passing backend pytest tests and 13 passing frontend tests.

---

## Quick Reference Commands

```powershell
# 1. Run full interactive portfolio demo
python scripts/final_demo.py

# 2. Run incident lifecycle simulator
python scripts/simulate_incident.py

# 3. Run full backend regression suite
cd backend
python -m pytest -v

# 4. Run frontend test suite & build
cd ../frontend
npm test -- --run
npm run build
```
