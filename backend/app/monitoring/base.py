from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProbeResult:
    """
    Unified probe result returned by all protocol probes (TCP, HTTP, HTTPS, DNS).
    """

    success: bool
    latency_ms: float | None
    error_type: str | None = None
    error_message: str | None = None
    status_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "status": "up" if self.success else "down",
            "latency_ms": round(self.latency_ms, 2) if self.latency_ms is not None else None,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "metadata": dict(self.metadata),
        }
        if self.status_code is not None:
            data["status_code"] = self.status_code
        return data


class BaseProbe(ABC):
    """
    Abstract strategy interface for protocol probes.
    """

    @abstractmethod
    def check(
        self,
        target_host: str,
        port: int | None,
        timeout_seconds: float,
        config: dict[str, Any] | None = None,
    ) -> ProbeResult:
        """
        Execute the protocol probe against target_host.
        """
        pass
