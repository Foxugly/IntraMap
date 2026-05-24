from datetime import datetime

import pytest

from intramap.models import DiscoveredHost, Host, Inventory, Location, Uplink, normalize_mac


@pytest.mark.parametrize("raw, expected", [
    ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
    ("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
    ("aa-bb-cc-dd-ee-ff", "aa:bb:cc:dd:ee:ff"),
    ("AABBCCDDEEFF", "aa:bb:cc:dd:ee:ff"),
    ("  aa:bb:cc:dd:ee:ff  ", "aa:bb:cc:dd:ee:ff"),
])
def test_normalize_mac_accepts_common_formats(raw, expected):
    assert normalize_mac(raw) == expected


@pytest.mark.parametrize("bad", [
    "",
    "not-a-mac",
    "aa:bb:cc:dd:ee",          # too short
    "aa:bb:cc:dd:ee:ff:gg",    # too long
    "zz:bb:cc:dd:ee:ff",       # invalid hex
])
def test_normalize_mac_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_mac(bad)


def test_discovered_host_normalizes_mac():
    h = DiscoveredHost(mac="AA-BB-CC-DD-EE-01", ip="192.168.1.1",
                       hostname="box", vendor="Sagemcom")
    assert h.mac == "aa:bb:cc:dd:ee:01"


def test_host_normalizes_mac_and_defaults():
    now = datetime(2026, 5, 24, 14, 0, 0)
    h = Host(mac="AA:BB:CC:DD:EE:02", ip="192.168.1.10",
             hostname=None, vendor="Cisco",
             first_seen=now, last_seen=now)
    assert h.mac == "aa:bb:cc:dd:ee:02"
    assert h.custom_name is None
    assert h.location == Location()
    assert h.uplink is None
    assert h.online is True


def test_location_empty_by_default():
    loc = Location()
    assert loc.floor is None
    assert loc.room is None
    assert loc.rack is None
    assert loc.rack_unit is None


def test_uplink_defaults_are_empty_no_poe():
    u = Uplink()
    assert u.switch_mac is None
    assert u.switch_port is None
    assert u.patch_port is None
    assert u.poe is False


def test_uplink_normalizes_switch_mac():
    u = Uplink(switch_mac="AA-BB-CC-DD-EE-02")
    assert u.switch_mac == "aa:bb:cc:dd:ee:02"


def test_uplink_none_switch_mac_stays_none():
    u = Uplink(switch_mac=None, patch_port=7)
    assert u.switch_mac is None
    assert u.patch_port == 7


def test_inventory_to_dict_and_from_dict_round_trip_no_uplink():
    now = datetime(2026, 5, 24, 14, 30, 0)
    host = Host(
        mac="aa:bb:cc:dd:ee:01",
        ip="192.168.1.1",
        hostname="box",
        vendor="Sagemcom",
        custom_name="Box internet",
        location=Location(floor="RDC", room="salon"),
        first_seen=now,
        last_seen=now,
        online=True,
    )
    inv = Inventory(hosts={host.mac: host}, last_scan=now)
    data = inv.to_dict()
    restored = Inventory.from_dict(data)
    assert restored == inv
    assert restored.hosts[host.mac].uplink is None


def test_inventory_to_dict_and_from_dict_round_trip_with_uplink():
    now = datetime(2026, 5, 24, 14, 30, 0)
    host = Host(
        mac="aa:bb:cc:dd:ee:03",
        ip="192.168.1.50",
        hostname="cam",
        vendor="Hikvision",
        custom_name="Caméra entrée",
        location=Location(floor="RDC", room="hall"),
        uplink=Uplink(
            switch_mac="aa:bb:cc:dd:ee:02",
            switch_port=4,
            patch_port=7,
            poe=True,
        ),
        first_seen=now,
        last_seen=now,
        online=True,
    )
    inv = Inventory(hosts={host.mac: host}, last_scan=now)
    data = inv.to_dict()
    restored = Inventory.from_dict(data)
    assert restored == inv
    assert restored.hosts[host.mac].uplink == Uplink(
        switch_mac="aa:bb:cc:dd:ee:02",
        switch_port=4,
        patch_port=7,
        poe=True,
    )
