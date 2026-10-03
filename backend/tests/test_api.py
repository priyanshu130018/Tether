from fastapi.testclient import TestClient

from app.models import Job, JobStatus, Protocol, Target, TargetStatus
from app.tasks.locks import acquire_target_lock


def test_create_target_with_host(client: TestClient) -> None:
    payload = {
        "name": "Production Server",
        "host": "192.168.1.10",
        "port": 443,
        "interval_seconds": 300,
        "timeout_seconds": 5.0,
        "retry_count": 3,
        "enabled": True,
    }
    response = client.post("/api/targets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Production Server"
    assert data["host"] == "192.168.1.10"
    assert data["hostname"] == "192.168.1.10"
    assert data["port"] == 443
    assert data["interval_seconds"] == 300
    assert data["status"] == "UNKNOWN"
    assert data["next_check_at"] is not None
    assert data["consecutive_failures"] == 0

    # Also check /targets alias
    response_alias = client.get(f"/targets/{data['id']}")
    assert response_alias.status_code == 200
    assert response_alias.json()["id"] == data["id"]


def test_create_target_with_hostname(client: TestClient) -> None:
    payload = {
        "name": "Database Server",
        "hostname": "db.internal.net",
        "port": 5432,
        "interval_seconds": 60,
    }
    response = client.post("/targets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["hostname"] == "db.internal.net"
    assert data["host"] == "db.internal.net"


def test_list_targets(client: TestClient) -> None:
    client.post("/api/targets", json={"name": "T1", "host": "1.1.1.1", "port": 80, "enabled": True})
    client.post("/api/targets", json={"name": "T2", "host": "2.2.2.2", "port": 80, "enabled": False})

    res_all = client.get("/api/targets")
    assert res_all.status_code == 200
    assert len(res_all.json()) >= 2

    res_enabled = client.get("/api/targets?enabled=true")
    assert res_enabled.status_code == 200
    assert all(t["enabled"] is True for t in res_enabled.json())

    res_disabled = client.get("/api/targets?enabled=false")
    assert res_disabled.status_code == 200
    assert all(t["enabled"] is False for t in res_disabled.json())


def test_enable_and_disable_target(client: TestClient) -> None:
    res = client.post("/api/targets", json={"name": "Toggle Target", "host": "3.3.3.3", "port": 80, "enabled": True})
    target_id = res.json()["id"]

    # Disable
    res_dis = client.post(f"/api/targets/{target_id}/disable")
    assert res_dis.status_code == 200
    assert res_dis.json()["enabled"] is False
    assert res_dis.json()["next_check_at"] is None

    # Enable
    res_en = client.post(f"/api/targets/{target_id}/enable")
    assert res_en.status_code == 200
    assert res_en.json()["enabled"] is True
    assert res_en.json()["next_check_at"] is not None


def test_manual_check_endpoint(client: TestClient) -> None:
    res = client.post("/api/targets", json={"name": "Manual Target", "host": "4.4.4.4", "port": 80})
    target_id = res.json()["id"]

    check_res = client.post(f"/api/targets/{target_id}/check")
    assert check_res.status_code == 202
    job_data = check_res.json()
    assert job_data["target_id"] == target_id
    assert job_data["status"] == "queued"
    assert job_data["task_type"] in ("tcp", "tcp_check")


def test_manual_check_duplicate_prevention(client: TestClient, fake_redis) -> None:
    res = client.post("/api/targets", json={"name": "Busy Target", "host": "5.5.5.5", "port": 80})
    target_id = res.json()["id"]

    # Lock the target
    acquire_target_lock(fake_redis, target_id)

    # Manual check should return 409 Conflict
    check_res = client.post(f"/api/targets/{target_id}/check")
    assert check_res.status_code == 409
    assert "already in progress" in check_res.json()["detail"]


def test_jobs_api_listing_and_filtering(client: TestClient, db_session) -> None:
    # Setup target and multiple jobs in DB
    target = Target(name="Job Target", hostname="6.6.6.6", port=80)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    job1 = Job(target_id=target.id, task_type="tcp", status=JobStatus.SUCCESSFUL)
    job2 = Job(target_id=target.id, task_type="tcp", status=JobStatus.FAILED)
    db_session.add_all([job1, job2])
    db_session.commit()

    # List jobs
    res = client.get("/api/jobs")
    assert res.status_code == 200
    jobs = res.json()
    assert len(jobs) >= 2

    # Filter by status
    res_filtered = client.get("/api/jobs?status=successful")
    assert res_filtered.status_code == 200
    for j in res_filtered.json():
        assert j["status"] == "successful"

    # Get single job
    job_res = client.get(f"/api/jobs/{job1.id}")
    assert job_res.status_code == 200
    assert job_res.json()["id"] == job1.id
    assert job_res.json()["status"] == "successful"

    # Not found job
    assert client.get("/api/jobs/999999").status_code == 404
