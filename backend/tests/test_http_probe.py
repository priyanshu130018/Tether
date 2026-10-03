from unittest.mock import MagicMock, patch
import httpx
import ssl

from app.monitoring.http import HttpProbe, build_url


def test_build_url_normalizes_correctly() -> None:
    # Basic HTTP
    assert build_url("http", "example.com", 80, "/health") == "http://example.com/health"
    # Basic HTTPS
    assert build_url("https", "example.com", 443, "/api/v1") == "https://example.com/api/v1"
    # Custom port
    assert build_url("http", "example.com", 8080, "/") == "http://example.com:8080/"
    # Host provided with scheme
    assert build_url("http", "http://example.com", 80, "/test") == "http://example.com/test"
    # Leading slash added if omitted
    assert build_url("https", "api.test.com", 443, "status") == "https://api.test.com/status"


def test_http_probe_success_200() -> None:
    probe = HttpProbe(scheme="http")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.url = "http://example.com/health"
    mock_resp.http_version = "HTTP/1.1"

    with patch("httpx.Client.request", return_value=mock_resp):
        res = probe.check("example.com", 80, 5.0, {"path": "/health"})
        assert res.success is True
        assert res.status_code == 200
        assert res.latency_ms is not None
        assert res.error_type is None
        assert res.metadata["final_url"] == "http://example.com/health"

        data = res.to_dict()
        assert data["status"] == "up"
        assert data["status_code"] == 200


def test_http_probe_expected_status_codes() -> None:
    probe = HttpProbe(scheme="http")
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.url = "http://example.com/create"
    mock_resp.http_version = "HTTP/1.1"

    with patch("httpx.Client.request", return_value=mock_resp):
        res = probe.check("example.com", 80, 5.0, {"expected_status_codes": [200, 201]})
        assert res.success is True
        assert res.status_code == 201


def test_http_probe_unexpected_status_code() -> None:
    probe = HttpProbe(scheme="http")
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.url = "http://example.com/health"
    mock_resp.http_version = "HTTP/1.1"

    with patch("httpx.Client.request", return_value=mock_resp):
        res = probe.check("example.com", 80, 5.0, {"expected_status_codes": [200]})
        assert res.success is False
        assert res.status_code == 500
        assert res.error_type == "http_status_error"
        assert "expected one of [200]" in res.error_message


def test_http_probe_timeout() -> None:
    probe = HttpProbe(scheme="http")
    with patch("httpx.Client.request", side_effect=httpx.ConnectTimeout("Connection timed out")):
        res = probe.check("10.255.255.1", 80, 2.0)
        assert res.success is False
        assert res.error_type == "timeout"
        assert "timed out" in res.error_message


def test_http_probe_connection_error() -> None:
    probe = HttpProbe(scheme="http")
    with patch("httpx.Client.request", side_effect=httpx.ConnectError("Connection refused")):
        res = probe.check("127.0.0.1", 9999, 1.0)
        assert res.success is False
        assert res.error_type == "connection_error"
        assert "Could not connect" in res.error_message


def test_https_probe_ssl_error() -> None:
    probe = HttpProbe(scheme="https")
    with patch("httpx.Client.request", side_effect=ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")):
        res = probe.check("self-signed.example.com", 443, 5.0)
        assert res.success is False
        assert res.error_type == "ssl_error"
        assert "verification error" in res.error_message.lower()


def test_http_probe_too_many_redirects() -> None:
    probe = HttpProbe(scheme="http")
    with patch("httpx.Client.request", side_effect=httpx.TooManyRedirects("Too many redirects")):
        res = probe.check("loop.example.com", 80, 5.0)
        assert res.success is False
        assert res.error_type == "too_many_redirects"


def test_http_probe_invalid_url() -> None:
    probe = HttpProbe(scheme="http")
    res = probe.check("gopher://unsafe.internal", 70, 5.0)
    assert res.success is False
    assert res.error_type == "invalid_url"
