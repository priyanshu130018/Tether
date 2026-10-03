from datetime import datetime, timezone
from app.models import (
    AlertEvent,
    AlertEventStatus,
    AlertEventType,
    CheckStatus,
    Job,
    JobStatus,
    MonitoringResult,
    Protocol,
    Target,
    TargetStatus,
)


def test_dashboard_summary_api(client, db_session):
    # Setup targets
    t1 = Target(name="T1", hostname="t1.com", port=80, status=TargetStatus.UP)
    t2 = Target(name="T2", hostname="t2.com", port=443, status=TargetStatus.DOWN)
    t3 = Target(name="T3", hostname="t3.com", port=53, status=TargetStatus.UNKNOWN)
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    # Setup alert event
    alert = AlertEvent(
        target_id=t2.id,
        event_type=AlertEventType.OUTAGE,
        status=AlertEventStatus.SENT,
        message="Outage active",
    )
    db_session.add(alert)

    # Setup jobs
    j1 = Job(target_id=t1.id, task_type="http_check", status=JobStatus.RUNNING, worker_id="worker-1")
    j2 = Job(target_id=t2.id, task_type="https_check", status=JobStatus.SUCCESSFUL, worker_id="worker-1")
    db_session.add_all([j1, j2])
    db_session.commit()

    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["targets"] >= 3
    assert data["up"] >= 1
    assert data["down"] >= 1
    assert data["unknown"] >= 1
    assert data["active_alerts"] >= 1
    assert data["running_jobs"] >= 1


def test_target_latency_and_delete_api(client, db_session):
    target = Target(name="Latency Target", hostname="lat.com", port=80, protocol=Protocol.HTTP)
    db_session.add(target)
    db_session.commit()

    now = datetime.now(timezone.utc)
    r1 = MonitoringResult(target_id=target.id, status=CheckStatus.UP, latency_ms=45.2, timestamp=now)
    r2 = MonitoringResult(target_id=target.id, status=CheckStatus.UP, latency_ms=50.1, timestamp=now)
    db_session.add_all([r1, r2])
    db_session.commit()

    # Latency history
    res = client.get(f"/api/targets/{target.id}/latency?range=1h")
    assert res.status_code == 200
    points = res.json()
    assert len(points) == 2
    assert points[0]["latency_ms"] == 45.2

    # Delete target
    del_res = client.delete(f"/api/targets/{target.id}")
    assert del_res.status_code == 204

    # Verify 404 after delete
    get_res = client.get(f"/api/targets/{target.id}")
    assert get_res.status_code == 404


def test_workers_api(client, db_session):
    target = Target(name="Worker API Target", hostname="worker.com", port=80)
    db_session.add(target)
    db_session.commit()

    j1 = Job(
        target_id=target.id,
        task_type="tcp_check",
        status=JobStatus.SUCCESSFUL,
        worker_id="celery@worker-node-1",
    )
    db_session.add(j1)
    db_session.commit()

    res = client.get("/api/workers")
    assert res.status_code == 200
    workers = res.json()
    assert len(workers) >= 1
    assert any(w["worker_id"] == "celery@worker-node-1" for w in workers)
