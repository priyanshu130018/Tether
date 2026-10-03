import socket
import threading
from unittest.mock import patch

from app.monitoring.tcp import TcpErrorType, check_tcp


def test_tcp_check_reports_open_port() -> None:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    thread = threading.Thread(target=lambda: server.accept()[0].close(), daemon=True)
    thread.start()
    try:
        result = check_tcp("127.0.0.1", server.getsockname()[1], 1)
        assert result.success is True
        assert result.latency_ms is not None
        assert result.error_message is None
        data = result.to_dict("127.0.0.1", server.getsockname()[1])
        assert data["status"] == "up"
        assert data["latency_ms"] is not None
        assert data["host"] == "127.0.0.1"
    finally:
        server.close()


def test_tcp_check_reports_closed_port() -> None:
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.close()
    result = check_tcp("127.0.0.1", port, 0.2)
    assert result.success is False
    assert result.latency_ms is None
    assert result.error_type in (
        TcpErrorType.CONNECTION_REFUSED.value,
        TcpErrorType.NETWORK_ERROR.value,
        TcpErrorType.TIMEOUT.value,
    )
    assert result.error_message


def test_tcp_check_reports_connection_refused() -> None:
    with patch("socket.create_connection", side_effect=ConnectionRefusedError("Connection refused")):
        result = check_tcp("127.0.0.1", 80, 1.0)
        assert result.success is False
        assert result.latency_ms is None
        assert result.error_type == "connection_refused"
        assert "Connection refused" in result.error_message


def test_tcp_check_reports_timeout() -> None:
    with patch("socket.create_connection", side_effect=socket.timeout("timed out")):
        result = check_tcp("192.0.2.1", 80, 0.1)
        assert result.success is False
        assert result.latency_ms is None
        assert result.error_type == "timeout"
        assert "timed out" in result.error_message.lower()

        data = result.to_dict("192.0.2.1", 80)
        assert data["status"] == "down"
        assert data["latency_ms"] is None
        assert data["error_type"] == "timeout"


def test_tcp_check_reports_dns_failure() -> None:
    with patch("socket.create_connection", side_effect=socket.gaierror(11001, "getaddrinfo failed")):
        result = check_tcp("nonexistent.domain.invalid", 80, 1.0)
        assert result.success is False
        assert result.latency_ms is None
        assert result.error_type == "dns_failure"
        assert "DNS resolution failed" in result.error_message
