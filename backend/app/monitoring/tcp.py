import errno
import socket
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any

from app.monitoring.base import BaseProbe, ProbeResult


class TcpErrorType(str, Enum):
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    DNS_FAILURE = "dns_failure"
    NETWORK_UNREACHABLE = "network_unreachable"
    NETWORK_ERROR = "network_error"
    UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class TcpCheckResult:
    success: bool
    latency_ms: float | None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self, hostname: str, port: int) -> dict[str, object]:
        if self.success:
            return {
                "status": "up",
                "latency_ms": round(self.latency_ms, 2) if self.latency_ms is not None else None,
                "host": hostname,
                "port": port,
            }
        return {
            "status": "down",
            "latency_ms": None,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


def check_tcp(hostname: str, port: int, timeout_seconds: float) -> TcpCheckResult:
    started = perf_counter()
    try:
        with socket.create_connection((hostname, port), timeout=timeout_seconds):
            latency_ms = (perf_counter() - started) * 1000
            return TcpCheckResult(
                success=True,
                latency_ms=round(latency_ms, 2),
            )
    except (socket.timeout, TimeoutError):
        return TcpCheckResult(
            success=False,
            latency_ms=None,
            error_type=TcpErrorType.TIMEOUT.value,
            error_message=f"Connection timed out after {timeout_seconds}s",
        )
    except socket.gaierror as exc:
        return TcpCheckResult(
            success=False,
            latency_ms=None,
            error_type=TcpErrorType.DNS_FAILURE.value,
            error_message=f"DNS resolution failed for '{hostname}': {exc.strerror or str(exc)}",
        )
    except ConnectionRefusedError:
        return TcpCheckResult(
            success=False,
            latency_ms=None,
            error_type=TcpErrorType.CONNECTION_REFUSED.value,
            error_message=f"Connection refused by {hostname}:{port}",
        )
    except OSError as exc:
        err = exc.errno
        if err in (errno.ECONNREFUSED, 10061, 111):
            return TcpCheckResult(
                success=False,
                latency_ms=None,
                error_type=TcpErrorType.CONNECTION_REFUSED.value,
                error_message=f"Connection refused by {hostname}:{port}",
            )
        elif err in (getattr(errno, "ETIMEDOUT", 110), 10060):
            return TcpCheckResult(
                success=False,
                latency_ms=None,
                error_type=TcpErrorType.TIMEOUT.value,
                error_message=f"Connection timed out after {timeout_seconds}s",
            )
        elif err in (getattr(errno, "EHOSTUNREACH", 113), getattr(errno, "ENETUNREACH", 101), 10051, 10065):
            return TcpCheckResult(
                success=False,
                latency_ms=None,
                error_type=TcpErrorType.NETWORK_UNREACHABLE.value,
                error_message=f"Network unreachable for {hostname}:{port}",
            )
        else:
            return TcpCheckResult(
                success=False,
                latency_ms=None,
                error_type=TcpErrorType.NETWORK_ERROR.value,
                error_message=f"Network error connecting to {hostname}:{port}: {exc.strerror or str(exc)}",
            )
    except Exception as exc:
        return TcpCheckResult(
            success=False,
            latency_ms=None,
            error_type=TcpErrorType.UNEXPECTED.value,
            error_message=f"Unexpected error: {type(exc).__name__}",
        )


class TcpProbe(BaseProbe):
    """
    TCP probe implementing the BaseProbe strategy interface.
    """

    def check(
        self,
        target_host: str,
        port: int | None,
        timeout_seconds: float,
        config: dict[str, Any] | None = None,
    ) -> ProbeResult:
        if port is None:
            return ProbeResult(
                success=False,
                latency_ms=None,
                error_type="missing_port",
                error_message="Port is required for TCP monitoring",
                metadata={"port": None},
            )

        tcp_res = check_tcp(target_host, port, timeout_seconds)
        return ProbeResult(
            success=tcp_res.success,
            latency_ms=tcp_res.latency_ms,
            error_type=tcp_res.error_type,
            error_message=tcp_res.error_message,
            metadata={"port": port, "host": target_host},
        )
