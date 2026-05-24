from unittest.mock import MagicMock, patch

import pytest

from intramap.scanner import scan
from intramap.models import DiscoveredHost


def _fake_port_scanner(hosts_data: dict):
    """Build a fake nmap.PortScanner that yields hosts_data.

    hosts_data maps IP -> dict with 'addresses', 'hostnames', 'vendor'.
    """
    fake = MagicMock()
    fake.all_hosts.return_value = list(hosts_data.keys())
    fake.__getitem__.side_effect = lambda ip: hosts_data[ip]
    return fake


def test_scan_returns_discovered_hosts_with_full_info():
    hosts_data = {
        "192.168.1.1": {
            "addresses": {"ipv4": "192.168.1.1", "mac": "AA:BB:CC:DD:EE:01"},
            "hostnames": [{"name": "livebox.home", "type": "PTR"}],
            "vendor": {"AA:BB:CC:DD:EE:01": "Sagemcom"},
        },
    }
    fake = _fake_port_scanner(hosts_data)
    with patch("intramap.scanner.nmap.PortScanner", return_value=fake):
        result = scan("192.168.1.0/24")

    assert result == [
        DiscoveredHost(mac="aa:bb:cc:dd:ee:01",
                       ip="192.168.1.1",
                       hostname="livebox.home",
                       vendor="Sagemcom"),
    ]
    fake.scan.assert_called_once()
    args, kwargs = fake.scan.call_args
    # We expect a host-discovery scan (no port scan)
    assert kwargs.get("hosts") == "192.168.1.0/24"
    assert "-sn" in kwargs.get("arguments", "")


def test_scan_skips_hosts_without_mac():
    hosts_data = {
        "192.168.1.1": {
            "addresses": {"ipv4": "192.168.1.1"},  # no MAC
            "hostnames": [],
            "vendor": {},
        },
        "192.168.1.2": {
            "addresses": {"ipv4": "192.168.1.2", "mac": "AA:BB:CC:DD:EE:02"},
            "hostnames": [],
            "vendor": {},
        },
    }
    fake = _fake_port_scanner(hosts_data)
    with patch("intramap.scanner.nmap.PortScanner", return_value=fake):
        result = scan("192.168.1.0/24")

    macs = [h.mac for h in result]
    assert macs == ["aa:bb:cc:dd:ee:02"]


def test_scan_handles_missing_hostname_and_vendor():
    hosts_data = {
        "192.168.1.1": {
            "addresses": {"ipv4": "192.168.1.1", "mac": "AA:BB:CC:DD:EE:01"},
            "hostnames": [],
            "vendor": {},
        },
    }
    fake = _fake_port_scanner(hosts_data)
    with patch("intramap.scanner.nmap.PortScanner", return_value=fake):
        result = scan("192.168.1.0/24")

    assert len(result) == 1
    assert result[0].hostname is None
    assert result[0].vendor is None


def test_scan_treats_empty_hostname_string_as_none():
    hosts_data = {
        "192.168.1.1": {
            "addresses": {"ipv4": "192.168.1.1", "mac": "AA:BB:CC:DD:EE:01"},
            "hostnames": [{"name": "", "type": "PTR"}],
            "vendor": {},
        },
    }
    fake = _fake_port_scanner(hosts_data)
    with patch("intramap.scanner.nmap.PortScanner", return_value=fake):
        result = scan("192.168.1.0/24")

    assert result[0].hostname is None


def test_scan_raises_friendly_error_when_nmap_binary_missing():
    import nmap as nmap_module
    with patch("intramap.scanner.nmap.PortScanner",
               side_effect=nmap_module.PortScannerError("nmap not found")):
        with pytest.raises(RuntimeError, match="nmap"):
            scan("192.168.1.0/24")
