import logging
import ssl
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.monitoring.base import BaseProbe, ProbeResult

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
DEFAULT_EXPECTED_STATUSES = [200]


def build_url(scheme: str, host: str, port: int | None, path: str) -> str:
    """
    Construct and validate the target HTTP/HTTPS URL safely.
    """
    cleaned_host = host.strip()
    # Strip scheme if user included it in host field
    if "://" in cleaned_host:
        parts = urlsplit(cleaned_host)
        if parts.scheme and parts.scheme.lower() not in ALLOWED_SCHEMES:
            raise ValueError(f"Unsupported URL scheme: {parts.scheme}")
        cleaned_host = parts.netloc or parts.path
        if parts.path and parts.path != "/" and not path:
            path = parts.path

    # Normalize path
    if not path:
        path = "/"
    elif not path.startswith("/"):
        path = f"/{path}"

    scheme = scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme must be one of {ALLOWED_SCHEMES}, got '{scheme}'")

    # Handle port formatting
    is_default_port = (scheme == "http" and (port is None or port == 80)) or (
        scheme == "https" and (port is None or port == 443)
    )
    if is_default_port or port is None:
        netloc = cleaned_host
    else:
        # Avoid duplicating port if already present in cleaned_host
        if ":" in cleaned_host and not cleaned_host.startswith("["):
            netloc = cleaned_host
        else:
            netloc = f"{cleaned_host}:{port}"

    return f"{scheme}://{netloc}{path}"


class HttpProbe(BaseProbe):
    """
    HTTP and HTTPS monitoring probe using httpx.
    """

    def __init__(self, scheme: str = "http") -> None:
        self.scheme = scheme.lower()

    def check(
        self,
        target_host: str,
        port: int | None,
        timeout_seconds: float,
        config: dict[str, Any] | None = None,
    ) -> ProbeResult:
        config = config or {}
        method = str(config.get("method", "GET")).upper()
        path = str(config.get("path", "/"))
        expected_statuses = config.get("expected_status_codes", DEFAULT_EXPECTED_STATUSES)
        if not expected_statuses:
            expected_statuses = DEFAULT_EXPECTED_STATUSES
        expected_statuses = [int(s) for s in expected_statuses]

        verify_ssl = bool(config.get("verify_ssl", True))
        follow_redirects = bool(config.get("follow_redirects", True))
        headers = config.get("headers", {})

        try:
            url = build_url(self.scheme, target_host, port, path)
        except Exception as exc:
            return ProbeResult(
                success=False,
                latency_ms=None,
                error_type="invalid_url",
                error_message=f"Invalid URL configuration: {exc}",
                metadata={"scheme": self.scheme, "host": target_host, "port": port},
            )

        metadata: dict[str, Any] = {
            "url": url,
            "method": method,
            "scheme": self.scheme,
            "verify_ssl": verify_ssl,
            "follow_redirects": follow_redirects,
            "expected_status_codes": expected_statuses,
        }

        started = perf_counter()
        try:
            with httpx.Client(
                verify=verify_ssl,
                follow_redirects=follow_redirects,
                timeout=httpx.Timeout(timeout_seconds),
            ) as client:
                response = client.request(method, url, headers=headers)
                latency_ms = (perf_counter() - started) * 1000

                status_code = response.status_code
                metadata["status_code"] = status_code
                metadata["final_url"] = str(response.url)
                metadata["http_version"] = response.http_version

                if status_code in expected_statuses:
                    return ProbeResult(
                        success=True,
                        latency_ms=round(latency_ms, 2),
                        status_code=status_code,
                        metadata=metadata,
                    )
                else:
                    return ProbeResult(
                        success=False,
                        latency_ms=round(latency_ms, 2),
                        status_code=status_code,
                        error_type="http_status_error",
                        error_message=(
                            f"Received HTTP status {status_code}, expected one of {expected_statuses}"
                        ),
                        metadata=metadata,
                    )

        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout):
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="timeout",
                error_message=f"HTTP request timed out after {timeout_seconds}s",
                metadata=metadata,
            )
        except httpx.TooManyRedirects:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="too_many_redirects",
                error_message=f"Exceeded maximum redirect limit for {url}",
                metadata=metadata,
            )
        except (ssl.SSLError, httpx.ConnectError) as exc:
            latency_ms = (perf_counter() - started) * 1000
            err_str = str(exc)
            if "certificate" in err_str.lower() or "ssl" in err_str.lower() or isinstance(exc, ssl.SSLError):
                return ProbeResult(
                    success=False,
                    latency_ms=round(latency_ms, 2),
                    error_type="ssl_error",
                    error_message=f"TLS/SSL verification error for {url}: {err_str}",
                    metadata=metadata,
                )
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="connection_error",
                error_message=f"Could not connect to {url}: {err_str}",
                metadata=metadata,
            )
        except httpx.InvalidURL as exc:
            return ProbeResult(
                success=False,
                latency_ms=None,
                error_type="invalid_url",
                error_message=f"Invalid HTTP URL: {exc}",
                metadata=metadata,
            )
        except Exception as exc:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="unexpected",
                error_message=f"Unexpected HTTP probe error: {type(exc).__name__}",
                metadata=metadata,
            )
