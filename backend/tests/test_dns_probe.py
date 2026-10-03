from unittest.mock import MagicMock, patch
import dns.exception
import dns.resolver

from app.monitoring.dns_probe import DnsProbe


def make_mock_rdata(val: str, preference: int | None = None):
    rdata = MagicMock()
    if preference is not None:
        rdata.preference = preference
        rdata.exchange.to_text.return_value = val
        return rdata
    rdata.address = val
    rdata.target = MagicMock()
    rdata.target.to_text.return_value = val
    rdata.strings = [val.encode("utf-8")]
    rdata.__str__.return_value = val
    return rdata


def test_dns_probe_a_record() -> None:
    probe = DnsProbe()
    mock_rdata = MagicMock()
    mock_rdata.address = "93.184.216.34"

    with patch("dns.resolver.Resolver.resolve", return_value=[mock_rdata]):
        res = probe.check("example.com", 53, 2.0, {"record_type": "A"})
        assert res.success is True
        assert res.latency_ms is not None
        assert res.metadata["record_type"] == "A"
        assert res.metadata["records"] == ["93.184.216.34"]


def test_dns_probe_aaaa_record() -> None:
    probe = DnsProbe()
    mock_rdata = MagicMock()
    mock_rdata.address = "2606:2800:220:1:248:1893:25c8:1946"

    with patch("dns.resolver.Resolver.resolve", return_value=[mock_rdata]):
        res = probe.check("example.com", 53, 2.0, {"record_type": "AAAA"})
        assert res.success is True
        assert res.metadata["records"] == ["2606:2800:220:1:248:1893:25c8:1946"]


def test_dns_probe_cname_record() -> None:
    probe = DnsProbe()
    mock_rdata = MagicMock()
    mock_rdata.target = MagicMock()
    mock_rdata.target.to_text.return_value = "target.example.net."

    with patch("dns.resolver.Resolver.resolve", return_value=[mock_rdata]):
        res = probe.check("alias.example.com", 53, 2.0, {"record_type": "CNAME"})
        assert res.success is True
        assert "target.example.net" in res.metadata["records"]


def test_dns_probe_mx_record() -> None:
    probe = DnsProbe()
    mock_rdata = MagicMock()
    mock_rdata.preference = 10
    mock_rdata.exchange = MagicMock()
    mock_rdata.exchange.to_text.return_value = "mail.example.com."

    with patch("dns.resolver.Resolver.resolve", return_value=[mock_rdata]):
        res = probe.check("example.com", 53, 2.0, {"record_type": "MX"})
        assert res.success is True
        assert res.metadata["records"] == ["10 mail.example.com"]


def test_dns_probe_txt_record() -> None:
    probe = DnsProbe()
    mock_rdata = MagicMock()
    mock_rdata.strings = [b"v=spf1 -all"]

    with patch("dns.resolver.Resolver.resolve", return_value=[mock_rdata]):
        res = probe.check("example.com", 53, 2.0, {"record_type": "TXT"})
        assert res.success is True
        assert "v=spf1 -all" in res.metadata["records"]


def test_dns_probe_ns_record() -> None:
    probe = DnsProbe()
    mock_rdata = MagicMock()
    mock_rdata.target = MagicMock()
    mock_rdata.target.to_text.return_value = "ns1.example.com."

    with patch("dns.resolver.Resolver.resolve", return_value=[mock_rdata]):
        res = probe.check("example.com", 53, 2.0, {"record_type": "NS"})
        assert res.success is True
        assert "ns1.example.com" in res.metadata["records"]


def test_dns_probe_expected_records_match() -> None:
    probe = DnsProbe()
    r1 = MagicMock()
    r1.address = "1.1.1.1"
    r2 = MagicMock()
    r2.address = "1.0.0.1"

    with patch("dns.resolver.Resolver.resolve", return_value=[r1, r2]):
        res = probe.check(
            "one.one.one.one",
            53,
            2.0,
            {"record_type": "A", "expected_records": ["1.0.0.1", "1.1.1.1"]},
        )
        assert res.success is True
        assert res.error_type is None


def test_dns_probe_expected_records_mismatch() -> None:
    probe = DnsProbe()
    r1 = MagicMock()
    r1.address = "1.1.1.1"

    with patch("dns.resolver.Resolver.resolve", return_value=[r1]):
        res = probe.check(
            "one.one.one.one",
            53,
            2.0,
            {"record_type": "A", "expected_records": ["8.8.8.8"]},
        )
        assert res.success is False
        assert res.error_type == "record_mismatch"
        assert "do not match expected" in res.error_message


def test_dns_probe_nxdomain() -> None:
    probe = DnsProbe()
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.NXDOMAIN()):
        res = probe.check("nonexistent.invalid", 53, 2.0, {"record_type": "A"})
        assert res.success is False
        assert res.error_type == "nxdomain"
        assert "NXDOMAIN" in res.error_message


def test_dns_probe_no_answer() -> None:
    probe = DnsProbe()
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.NoAnswer()):
        res = probe.check("example.com", 53, 2.0, {"record_type": "AAAA"})
        assert res.success is False
        assert res.error_type == "no_answer"
        assert "No AAAA records found" in res.error_message


def test_dns_probe_timeout() -> None:
    probe = DnsProbe()
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.Timeout()):
        res = probe.check("example.com", 53, 1.0, {"record_type": "A"})
        assert res.success is False
        assert res.error_type == "timeout"
        assert "timed out" in res.error_message


def test_dns_probe_unsupported_record_type() -> None:
    probe = DnsProbe()
    res = probe.check("example.com", 53, 2.0, {"record_type": "PTR"})
    assert res.success is False
    assert res.error_type == "unsupported_record_type"
