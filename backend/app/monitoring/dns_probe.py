import logging
from time import perf_counter
from typing import Any

import dns.exception
import dns.rdatatype
import dns.resolver

from app.monitoring.base import BaseProbe, ProbeResult

logger = logging.getLogger(__name__)

SUPPORTED_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "TXT", "NS"}


def normalize_record(record_type: str, record_text: str) -> str:
    """
    Normalize record text for consistent comparison (e.g. strip trailing dots, quotes, whitespace).
    """
    cleaned = record_text.strip()
    if record_type in ("CNAME", "NS"):
        cleaned = cleaned.rstrip(".")
    elif record_type == "TXT":
        cleaned = cleaned.strip('"')
    elif record_type == "MX":
        cleaned = cleaned.rstrip(".")
    return cleaned


class DnsProbe(BaseProbe):
    """
    DNS monitoring probe supporting A, AAAA, CNAME, MX, TXT, and NS records.
    """

    def check(
        self,
        target_host: str,
        port: int | None,
        timeout_seconds: float,
        config: dict[str, Any] | None = None,
    ) -> ProbeResult:
        config = config or {}
        raw_record_type = str(config.get("record_type", "A")).upper().strip()
        expected_records = config.get("expected_records")
        nameservers = config.get("nameservers") or config.get("nameserver")

        if raw_record_type not in SUPPORTED_RECORD_TYPES:
            return ProbeResult(
                success=False,
                latency_ms=None,
                error_type="unsupported_record_type",
                error_message=(
                    f"Unsupported DNS record type '{raw_record_type}'. "
                    f"Supported types: {sorted(SUPPORTED_RECORD_TYPES)}"
                ),
                metadata={"record_type": raw_record_type, "host": target_host},
            )

        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout_seconds
        resolver.timeout = timeout_seconds

        if nameservers:
            if isinstance(nameservers, str):
                resolver.nameservers = [nameservers.strip()]
            elif isinstance(nameservers, list):
                resolver.nameservers = [str(ns).strip() for ns in nameservers]

        metadata: dict[str, Any] = {
            "record_type": raw_record_type,
            "host": target_host,
            "expected_records": expected_records,
            "records": [],
        }

        started = perf_counter()
        try:
            answer = resolver.resolve(target_host, raw_record_type)
            latency_ms = (perf_counter() - started) * 1000

            records: list[str] = []
            for rdata in answer:
                if raw_record_type in ("A", "AAAA"):
                    records.append(str(getattr(rdata, "address", rdata)))
                elif raw_record_type in ("CNAME", "NS"):
                    target_obj = getattr(rdata, "target", rdata)
                    target_text = target_obj.to_text() if hasattr(target_obj, "to_text") else str(target_obj)
                    records.append(str(target_text).rstrip("."))
                elif raw_record_type == "MX":
                    exchange_obj = getattr(rdata, "exchange", rdata)
                    exchange_text = exchange_obj.to_text() if hasattr(exchange_obj, "to_text") else str(exchange_obj)
                    records.append(f"{rdata.preference} {str(exchange_text).rstrip('.')}")
                elif raw_record_type == "TXT":
                    # TXT rdata can consist of multiple string chunks
                    text_content = "".join(
                        part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part)
                        for part in rdata.strings
                    )
                    records.append(text_content.strip('"'))
                else:
                    records.append(str(rdata))

            metadata["records"] = records

            # Check expected records if configured (Section 8)
            if expected_records is not None:
                norm_actual = {normalize_record(raw_record_type, r) for r in records}
                norm_expected = {normalize_record(raw_record_type, str(r)) for r in expected_records}

                if norm_actual != norm_expected:
                    return ProbeResult(
                        success=False,
                        latency_ms=round(latency_ms, 2),
                        error_type="record_mismatch",
                        error_message=(
                            f"Resolved records {records} do not match expected {expected_records}"
                        ),
                        metadata=metadata,
                    )

            return ProbeResult(
                success=True,
                latency_ms=round(latency_ms, 2),
                metadata=metadata,
            )

        except (dns.resolver.Timeout, dns.exception.Timeout):
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="timeout",
                error_message=f"DNS query timed out after {timeout_seconds}s",
                metadata=metadata,
            )
        except dns.resolver.NXDOMAIN:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="nxdomain",
                error_message=f"Domain '{target_host}' does not exist (NXDOMAIN)",
                metadata=metadata,
            )
        except dns.resolver.NoAnswer:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="no_answer",
                error_message=f"No {raw_record_type} records found for '{target_host}'",
                metadata=metadata,
            )
        except dns.resolver.NoNameservers:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="no_nameservers",
                error_message=f"All nameservers failed for '{target_host}'",
                metadata=metadata,
            )
        except dns.exception.DNSException as exc:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="dns_failure",
                error_message=f"DNS query error for '{target_host}': {exc}",
                metadata=metadata,
            )
        except Exception as exc:
            latency_ms = (perf_counter() - started) * 1000
            return ProbeResult(
                success=False,
                latency_ms=round(latency_ms, 2),
                error_type="unexpected",
                error_message=f"Unexpected DNS probe error: {type(exc).__name__}",
                metadata=metadata,
            )
