from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.models import CheckStatus, Job, JobStatus, MonitoringResult, Protocol, Target, TargetStatus
from app.monitoring.base import ProbeResult
from app.tasks.monitoring import run_monitoring_check


def test_api_create_http_target(client: TestClient) -> None:
    payload = {
        "name": "HTTP API Server",
        "host": "api.example.com",
        "protocol": "http",
        "interval_seconds": 60,
        "config": {
            "path": "/health",
            "method": "GET",
            "expected_status_codes": [200, 204],
        },
    }
    response = client.post("/targets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["protocol"] == "http"
    assert data["port"] == 80  # Defaulted
    assert data["config"]["path"] == "/health"
    assert data["config"]["expected_status_codes"] == [200, 204]


def test_api_create_https_target(client: TestClient) -> None:
    payload = {
        "name": "HTTPS Secure API",
        "host": "secure.example.com",
        "protocol": "https",
        "interval_seconds": 120,
    }
    response = client.post("/targets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["protocol"] == "https"
    assert data["port"] == 443  # Defaulted


def test_api_create_dns_target(client: TestClient) -> None:
    payload = {
        "name": "Cloudflare DNS",
        "host": "one.one.one.one",
        "protocol": "dns",
        "interval_seconds": 300,
        "config": {
            "record_type": "A",
            "expected_records": ["1.1.1.1", "1.0.0.1"],
        },
    }
    response = client.post("/targets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["protocol"] == "dns"
    assert data["port"] == 53  # Defaulted
    assert data["config"]["record_type"] == "A"
    assert data["config"]["expected_records"] == ["1.1.1.1", "1.0.0.1"]


def test_api_rejects_invalid_protocol_config(client: TestClient) -> None:
    # Invalid HTTP method
    res1 = client.post(
        "/targets",
        json={"name": "Bad HTTP", "host": "example.com", "protocol": "http", "config": {"method": "INVALID"}},
    )
    assert res1.status_code == 422

    # Invalid DNS record type
    res2 = client.post(
        "/targets",
        json={"name": "Bad DNS", "host": "example.com", "protocol": "dns", "config": {"record_type": "XYZ"}},
    )
    assert res2.status_code == 422


def test_worker_executes_http_check(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Backend HTTP",
        hostname="web.service.internal",
        port=80,
        protocol=Protocol.HTTP,
        config={"path": "/healthz", "expected_status_codes": [200]},
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    job = Job(target_id=target.id, task_type="http_check", status=JobStatus.QUEUED)
    session.add(job)
    session.commit()
    session.refresh(job)

    mock_probe_result = ProbeResult(
        success=True,
        latency_ms=88.4,
        status_code=200,
        metadata={"url": "http://web.service.internal/healthz", "final_url": "http://web.service.internal/healthz"},
    )

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.monitoring.http.HttpProbe.check", return_value=mock_probe_result) as mock_check,
    ):
        output = run_monitoring_check(target.id, job.id)
        assert output["status"] == "up"
        assert output["latency_ms"] == 88.4
        assert output["status_code"] == 200
        mock_check.assert_called_once()

    session.refresh(target)
    session.refresh(job)

    assert target.status == TargetStatus.UP
    assert target.consecutive_successes == 1
    assert target.consecutive_failures == 0

    assert job.status == JobStatus.SUCCESSFUL
    assert job.task_type == "http_check"

    results = session.query(MonitoringResult).filter(MonitoringResult.target_id == target.id).all()
    assert len(results) == 1
    assert results[0].protocol == Protocol.HTTP
    assert results[0].status == CheckStatus.UP
    assert results[0].status_code == 200
    assert results[0].extra_data["final_url"] == "http://web.service.internal/healthz"
    session.close()


def test_worker_executes_dns_check(db_engine, fake_redis) -> None:
    TestingSession = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    target = Target(
        name="Mail DNS",
        hostname="example.org",
        port=53,
        protocol=Protocol.DNS,
        config={"record_type": "MX", "expected_records": ["10 mail.example.org"]},
    )
    session.add(target)
    session.commit()
    session.refresh(target)

    job = Job(target_id=target.id, task_type="dns_check", status=JobStatus.QUEUED)
    session.add(job)
    session.commit()
    session.refresh(job)

    mock_probe_result = ProbeResult(
        success=True,
        latency_ms=15.2,
        metadata={"record_type": "MX", "records": ["10 mail.example.org"]},
    )

    with (
        patch("app.tasks.monitoring.SessionLocal", TestingSession),
        patch("app.tasks.monitoring.get_redis_client", return_value=fake_redis),
        patch("app.monitoring.dns_probe.DnsProbe.check", return_value=mock_probe_result) as mock_dns,
    ):
        output = run_monitoring_check(target.id, job.id)
        assert output["status"] == "up"
        assert output["latency_ms"] == 15.2
        mock_dns.assert_called_once()

    session.refresh(target)
    session.refresh(job)

    assert target.status == TargetStatus.UP
    assert job.status == JobStatus.SUCCESSFUL

    results = session.query(MonitoringResult).filter(MonitoringResult.target_id == target.id).all()
    assert len(results) == 1
    assert results[0].protocol == Protocol.DNS
    assert results[0].status == CheckStatus.UP
    assert results[0].extra_data["records"] == ["10 mail.example.org"]
    session.close()
