# Tether — Production Release & Versioning Policy

## 1. Release Philosophy & Versioning
Tether follows strict **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`):
- **MAJOR (`X.0.0`)**: Incompatible API changes, breaking database migrations, or core architecture modifications.
- **MINOR (`1.X.0`)**: Backwards-compatible new protocols, notification channels, or dashboard features.
- **PATCH (`1.0.X`)**: Backwards-compatible bug fixes, security patches, and performance optimizations.

---

## 2. Pre-Release Checklist & Quality Gate

Before tagging any release version, the following verification pipeline must pass:

1. **Backend Automated Tests**:
   ```bash
   cd backend
   python -m pytest -v
   ```
   *Requirement*: 100% test pass rate with zero errors or unhandled exceptions.

2. **Frontend Automated Tests & Build**:
   ```bash
   cd frontend
   npm test -- --run
   npm run build
   ```
   *Requirement*: All Vitest tests pass; TypeScript compiles cleanly (`tsc -b`); production bundle builds without warning errors.

3. **Database Migration Validation**:
   ```bash
   cd backend
   alembic upgrade head
   alembic check
   ```
   *Requirement*: Migrations apply cleanly to target database schema without data corruption.

4. **Security & Secret Scan**:
   *Requirement*: Zero unmasked secrets, hardcoded credentials, or exposed private endpoints in source or history.

5. **Incident Lifecycle Simulation**:
   ```bash
   python scripts/simulate_incident.py
   ```
   *Requirement*: Outage and recovery state transitions execute successfully.

---

## 3. Deployment & Rollback Playbook

### 3.1 Production Deployment
```bash
# 1. Pull latest verified release tag
git checkout v1.0.0

# 2. Build and launch updated containers
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 3. Verify health and readiness
curl -f http://localhost/health/ready
```

### 3.2 Emergency Rollback Procedure
If a regression is identified post-deployment:
```bash
# 1. Rollback containers to previous stable tag
git checkout v0.9.0
docker compose -f docker-compose.prod.yml up -d --build

# 2. Downgrade database schema if migration was applied
docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1

# 3. Verify service recovery
curl -f http://localhost/health/ready
```
