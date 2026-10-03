import pytest

from app.monitoring.dns_probe import DnsProbe
from app.monitoring.http import HttpProbe
from app.monitoring.registry import ProbeRegistry, create_default_registry, default_probe_registry
from app.monitoring.tcp import TcpProbe


def test_registry_contains_all_protocols() -> None:
    registry = create_default_registry()
    protocols = registry.supported_protocols()
    assert "tcp" in protocols
    assert "http" in protocols
    assert "https" in protocols
    assert "dns" in protocols


def test_registry_returns_correct_probe_types() -> None:
    registry = default_probe_registry
    assert isinstance(registry.get("tcp"), TcpProbe)
    assert isinstance(registry.get("http"), HttpProbe)
    assert isinstance(registry.get("https"), HttpProbe)
    assert isinstance(registry.get("dns"), DnsProbe)


def test_registry_case_insensitive() -> None:
    registry = default_probe_registry
    assert isinstance(registry.get("TCP"), TcpProbe)
    assert isinstance(registry.get("Http"), HttpProbe)
    assert isinstance(registry.get("HTTPS"), HttpProbe)
    assert isinstance(registry.get("Dns"), DnsProbe)


def test_registry_unknown_protocol_raises_value_error() -> None:
    registry = default_probe_registry
    with pytest.raises(ValueError) as exc_info:
        registry.get("ftp")
    assert "Unsupported protocol: 'ftp'" in str(exc_info.value)
    assert "Supported protocols:" in str(exc_info.value)
