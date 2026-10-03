# Tether — Dashboard UI Views & Screenshot Reference

This document catalogs the primary user interface screens of the Tether React + TypeScript dashboard (<http://localhost:3000>).

---

## 1. Catalog of Primary Views

### 1.1 Dashboard Overview (`/`)
- **Route**: `DashboardPage.tsx`
- **Key Elements**:
  - Top summary cards: Monitored Targets, UP/DOWN/UNKNOWN counts, Active Outages, Running Jobs, Active Worker Nodes.
  - Active Outages banner listing degraded targets with failure durations.
  - Recent Targets table with live status badges, protocol tags (TCP, HTTP, HTTPS, DNS), intervals, and latency indicators.

---

### 1.2 Target Detail & Latency History (`/targets/:id`)
- **Route**: `TargetDetailPage.tsx`
- **Key Elements**:
  - Header with target status indicator, hostname, port, protocol badge, and manual check button (`Run Check Now`).
  - Interactive latency time-series chart (Chart.js) with time-range selector (`1h`, `6h`, `24h`, `7d`).
  - Target Configuration card: Interval, timeout, retry count, custom HTTP headers/body assertions.
  - Recent Probe Results history table with status codes, error classifications, and worker IDs.

---

### 1.3 Target Management & Creation (`/targets/new`, `/targets`)
- **Route**: `TargetsListPage.tsx`, `TargetCreatePage.tsx`
- **Key Elements**:
  - Filterable targets grid with protocol and status filters.
  - Create Target modal/form supporting dynamic protocol switching (TCP port, HTTP method/path/headers/status code assertions, DNS record type/nameserver).

---

### 1.4 Outage & Alert History (`/alerts`)
- **Route**: `AlertsPage.tsx`
- **Key Elements**:
  - Alert timeline with status badges (`SENT`, `FAILED`, `SUPPRESSED`).
  - Event details: Event type (`OUTAGE`, `RECOVERY`), target name, failure threshold, trigger timestamp, and resolved timestamp.
  - Delivery breakdown showing channel dispatches (Slack, Email, Webhook) with attempt counts and error details.

---

### 1.5 Background Jobs & Worker Mesh Telemetry (`/jobs`, `/workers`)
- **Route**: `JobsPage.tsx`, `WorkersPage.tsx`
- **Key Elements**:
  - Live worker nodes table with worker hostnames, active job counts, processed task totals, and last heartbeat timestamps.
  - Background jobs queue table displaying job ID, task ID, target name, status (`PENDING`, `IN_PROGRESS`, `SUCCESSFUL`, `FAILED`), and queue wait duration.

---

### 1.6 System Infrastructure & Health Diagnostics (`/system`)
- **Route**: `SystemStatusPage.tsx`
- **Key Elements**:
  - Component health cards: API Service (`alive`), PostgreSQL (`ready`), Redis (`ready`), Celery Worker Mesh (`active`).
  - Environment metadata: Platform version (`v1.0.0`), uptime, active database connection pool stats, and Prometheus metrics links.

---

### 1.7 Organization, Team & RBAC Management (`/settings/team`)
- **Route**: `TeamManagementPage.tsx`, `SettingsPage.tsx`
- **Key Elements**:
  - Organization settings: Tenant name, slug, and audit log stream.
  - Member management table: User name, email, role badge (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`), and invite/role modification controls.
