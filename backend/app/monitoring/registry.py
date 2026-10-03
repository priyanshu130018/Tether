import logging

from app.monitoring.base import BaseProbe
from app.monitoring.dns_probe import DnsProbe
from app.monitoring.http import HttpProbe
from app.monitoring.tcp import TcpProbe

logger = logging.getLogger(__name__)


class ProbeRegistry:
    """
    Registry for protocol probes using the Strategy pattern.
    Maps target protocol identifiers to their corresponding BaseProbe implementation.
    """

    def __init__(self) -> None:
        self._probes: dict[str, BaseProbe] = {}

    def register(self, protocol: str, probe: BaseProbe) -> None:
        self._probes[protocol.lower()] = probe

    def get(self, protocol: str) -> BaseProbe:
        proto_key = protocol.lower()
        if proto_key not in self._probes:
            supported = ", ".join(sorted(self._probes.keys()))
            raise ValueError(f"Unsupported protocol: '{protocol}'. Supported protocols: {supported}")
        return self._probes[proto_key]

    def supported_protocols(self) -> list[str]:
        return sorted(self._probes.keys())


def create_default_registry() -> ProbeRegistry:
    registry = ProbeRegistry()
    registry.register("tcp", TcpProbe())
    registry.register("http", HttpProbe(scheme="http"))
    registry.register("https", HttpProbe(scheme="https"))
    registry.register("dns", DnsProbe())
    return registry


default_probe_registry = create_default_registry()
