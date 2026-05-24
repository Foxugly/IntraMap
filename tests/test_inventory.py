from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from intramap.inventory import load, merge, save
from intramap.models import DiscoveredHost, Host, Inventory, Location, Uplink


def make_host(mac: str, ip: str, **kwargs) -> Host:
    now = datetime(2026, 5, 24, 14, 0, 0)
    defaults = dict(hostname=None, vendor=None, first_seen=now, last_seen=now)
    defaults.update(kwargs)
    return Host(mac=mac, ip=ip, **defaults)


def test_load_missing_file_returns_empty_inventory(tmp_path: Path):
    inv = load(tmp_path / "does_not_exist.yaml")
    assert inv.hosts == {}
    assert inv.last_scan is None


def test_save_then_load_round_trip(tmp_path: Path):
    now = datetime(2026, 5, 24, 14, 30, 0)
    inv = Inventory(
        hosts={
            "aa:bb:cc:dd:ee:01": make_host(
                "aa:bb:cc:dd:ee:01", "192.168.1.1",
                custom_name="Box", location=Location(floor="RDC", room="salon"),
            ),
        },
        last_scan=now,
    )
    path = tmp_path / "inv.yaml"
    save(inv, path)
    loaded = load(path)
    assert loaded == inv


def test_save_sorts_hosts_by_mac(tmp_path: Path):
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:03": make_host("aa:bb:cc:dd:ee:03", "192.168.1.3"),
        "aa:bb:cc:dd:ee:01": make_host("aa:bb:cc:dd:ee:01", "192.168.1.1"),
        "aa:bb:cc:dd:ee:02": make_host("aa:bb:cc:dd:ee:02", "192.168.1.2"),
    }, last_scan=datetime(2026, 5, 24))
    path = tmp_path / "inv.yaml"
    save(inv, path)
    text = path.read_text(encoding="utf-8")
    pos1 = text.index("aa:bb:cc:dd:ee:01")
    pos2 = text.index("aa:bb:cc:dd:ee:02")
    pos3 = text.index("aa:bb:cc:dd:ee:03")
    assert pos1 < pos2 < pos3


def test_load_normalizes_mac_keys(tmp_path: Path):
    path = tmp_path / "inv.yaml"
    path.write_text(
        "last_scan: 2026-05-24T14:30:00\n"
        "hosts:\n"
        "  AA-BB-CC-DD-EE-01:\n"
        "    ip: 192.168.1.1\n"
        "    hostname: null\n"
        "    vendor: null\n"
        "    custom_name: null\n"
        "    location: {floor: null, room: null, rack: null, rack_unit: null}\n"
        "    first_seen: '2026-05-01T10:00:00'\n"
        "    last_seen: '2026-05-24T14:30:00'\n"
        "    online: true\n",
        encoding="utf-8",
    )
    inv = load(path)
    assert "aa:bb:cc:dd:ee:01" in inv.hosts


def test_save_is_atomic_no_temp_left_behind(tmp_path: Path):
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host("aa:bb:cc:dd:ee:01", "192.168.1.1"),
    }, last_scan=datetime(2026, 5, 24))
    path = tmp_path / "inv.yaml"
    save(inv, path)
    # No leftover .tmp file
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []


def test_save_failure_preserves_existing_file(tmp_path: Path):
    path = tmp_path / "inv.yaml"
    original_text = "last_scan: null\nhosts: {}\n"
    path.write_text(original_text, encoding="utf-8")

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host("aa:bb:cc:dd:ee:01", "192.168.1.1"),
    }, last_scan=datetime(2026, 5, 24))

    with patch("os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            save(inv, path)

    # Original file untouched
    assert path.read_text(encoding="utf-8") == original_text


def test_load_corrupted_yaml_raises(tmp_path: Path):
    path = tmp_path / "inv.yaml"
    path.write_text("hosts: [not, a, mapping\n", encoding="utf-8")  # malformed
    with pytest.raises(yaml.YAMLError):
        load(path)


def test_load_corrupted_yaml_does_not_overwrite(tmp_path: Path):
    path = tmp_path / "inv.yaml"
    bad = "hosts: [not, a, mapping\n"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load(path)
    assert path.read_text(encoding="utf-8") == bad


def test_load_accepts_bare_date_in_yaml(tmp_path: Path):
    """PyYAML auto-parses 'YYYY-MM-DD' (no time) as a date object; load
    must accept it (we treat it as midnight)."""
    path = tmp_path / "inv.yaml"
    path.write_text(
        "last_scan: 2026-05-24\n"
        "hosts:\n"
        "  aa:bb:cc:dd:ee:01:\n"
        "    ip: 192.168.1.1\n"
        "    hostname: null\n"
        "    vendor: null\n"
        "    custom_name: null\n"
        "    location: {floor: null, room: null, rack: null, rack_unit: null}\n"
        "    uplink: null\n"
        "    first_seen: 2026-05-01\n"
        "    last_seen: 2026-05-24\n"
        "    online: true\n",
        encoding="utf-8",
    )
    inv = load(path)
    assert inv.last_scan == datetime(2026, 5, 24)
    assert inv.hosts["aa:bb:cc:dd:ee:01"].first_seen == datetime(2026, 5, 1)
    assert inv.hosts["aa:bb:cc:dd:ee:01"].last_seen == datetime(2026, 5, 24)


def test_merge_adds_new_host_with_empty_annotations():
    inv = Inventory()
    now = datetime(2026, 5, 24, 14, 0, 0)
    discovered = [DiscoveredHost(mac="aa:bb:cc:dd:ee:01",
                                 ip="192.168.1.1",
                                 hostname="box",
                                 vendor="Sagemcom")]
    merge(inv, discovered, now=now)

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    assert h.ip == "192.168.1.1"
    assert h.hostname == "box"
    assert h.vendor == "Sagemcom"
    assert h.custom_name is None
    assert h.location == Location()
    assert h.uplink is None
    assert h.first_seen == now
    assert h.last_seen == now
    assert h.online is True
    assert inv.last_scan == now


def test_merge_existing_host_preserves_annotations():
    earlier = datetime(2026, 5, 1, 10, 0, 0)
    now = datetime(2026, 5, 24, 14, 0, 0)
    uplink_value = Uplink(
        switch_mac="aa:bb:cc:dd:ee:02",
        switch_port=4,
        patch_port=7,
        poe=True,
    )
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01",
            ip="192.168.1.5",         # old IP
            hostname="old-name",
            vendor="OldVendor",
            custom_name="Box internet",
            location=Location(floor="RDC", room="salon"),
            uplink=uplink_value,
            first_seen=earlier,
            last_seen=earlier,
            online=False,
        ),
    }, last_scan=earlier)

    discovered = [DiscoveredHost(mac="aa:bb:cc:dd:ee:01",
                                 ip="192.168.1.1",
                                 hostname="livebox",
                                 vendor="Sagemcom")]
    merge(inv, discovered, now=now)

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    # updated
    assert h.ip == "192.168.1.1"
    assert h.hostname == "livebox"
    assert h.vendor == "Sagemcom"
    assert h.last_seen == now
    assert h.online is True
    # preserved
    assert h.custom_name == "Box internet"
    assert h.location == Location(floor="RDC", room="salon")
    assert h.uplink == uplink_value
    assert h.first_seen == earlier


def test_merge_absent_host_marked_offline():
    earlier = datetime(2026, 5, 1, 10, 0, 0)
    now = datetime(2026, 5, 24, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01",
            ip="192.168.1.1",
            hostname="box",
            vendor="Sagemcom",
            custom_name="Box",
            location=Location(floor="RDC"),
            first_seen=earlier,
            last_seen=earlier,
            online=True,
        ),
    }, last_scan=earlier)

    merge(inv, [], now=now)  # nothing discovered

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    assert h.online is False
    # everything else unchanged
    assert h.ip == "192.168.1.1"
    assert h.hostname == "box"
    assert h.custom_name == "Box"
    assert h.last_seen == earlier
    assert h.first_seen == earlier


def test_merge_skips_manual_hosts_in_scan():
    """A discovered MAC that matches a manual=True host must NOT be updated."""
    from datetime import datetime
    from intramap.inventory import merge
    from intramap.models import DiscoveredHost, Host, Inventory, Location

    earlier = datetime(2026, 5, 1, 10, 0, 0)
    now = datetime(2026, 5, 25, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01",
            ip=None,
            hostname=None,
            vendor=None,
            custom_name="Switch principal",
            location=Location(floor="cave", room="local"),
            first_seen=earlier,
            last_seen=earlier,
            manual=True,
            online=True,
        ),
    }, last_scan=earlier)

    discovered = [DiscoveredHost(mac="aa:bb:cc:dd:ee:01",
                                 ip="192.168.1.5",
                                 hostname="something",
                                 vendor="SomeVendor")]
    merge(inv, discovered, now=now)

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    # NOT updated
    assert h.ip is None
    assert h.hostname is None
    assert h.vendor is None
    assert h.last_seen == earlier
    assert h.online is True
    # preserved
    assert h.custom_name == "Switch principal"
    assert h.manual is True


def test_merge_does_not_mark_manual_hosts_offline_when_absent():
    """A manual=True host absent from the scan must remain online=True."""
    from datetime import datetime
    from intramap.inventory import merge
    from intramap.models import Host, Inventory

    earlier = datetime(2026, 5, 1, 10, 0, 0)
    now = datetime(2026, 5, 25, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01",
            ip=None,
            hostname=None,
            vendor=None,
            custom_name="Switch principal",
            first_seen=earlier,
            last_seen=earlier,
            manual=True,
            online=True,
        ),
    }, last_scan=earlier)

    merge(inv, [], now=now)

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    assert h.online is True  # NOT marked offline
    assert h.last_seen == earlier  # untouched
