from datetime import datetime

import pytest

from intramap.models import DiscoveredHost, Host, Inventory, Location, Uplink, normalize_mac


@pytest.fixture
def make_host_factory():
    """Return a function that builds a Host with sensible defaults."""
    from intramap.models import Host, Location  # local import to avoid early failure

    def _make(**kwargs):
        now = datetime(2026, 5, 25, 0, 0, 0)
        defaults = dict(
            mac="aa:bb:cc:dd:ee:01",
            ip="192.168.1.1",
            hostname=None,
            vendor=None,
            first_seen=now,
            last_seen=now,
        )
        defaults.update(kwargs)
        return Host(**defaults)
    return _make


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


# ---------------------------------------------------------------------------
# Task 1: DEVICE_TYPES catalogue + infer_device_type + _resolve_device_type
# ---------------------------------------------------------------------------

from intramap.models import (
    DEVICE_TYPES,
    infer_device_type,
    _resolve_device_type,
)


def test_device_types_catalogue_is_15_known_values():
    expected = {
        "router", "switch", "ap", "controller", "nas",
        "tv", "stb", "phone", "tablet", "laptop",
        "iot", "camera", "printer", "voip", "other",
    }
    assert DEVICE_TYPES == expected


@pytest.mark.parametrize("vendor, expected", [
    ("Sagemcom Broadband SAS", "router"),
    ("Vantiva USA", "router"),
    ("Synology Incorporated", "nas"),
    ("QNAP Systems", "nas"),
    ("Cisco Systems", "switch"),
    ("TP-Link Systems", "ap"),
    ("LG Electronics", "tv"),
    ("Samsung Electronics", "tv"),
    ("Apple Inc", "phone"),
    ("Hikvision", "camera"),
    ("Bticino SPA", "camera"),
    ("Intel Corporate", "laptop"),
    ("Universal Global Scientific Industrial.", "laptop"),
    ("Tuya Smart", "iot"),
    ("tado GmbH", "iot"),
    ("Davicom Semiconductor", "iot"),
    ("Grandstream Networks", "voip"),
    ("Canon Inc", "printer"),
])
def test_infer_device_type_known_vendors(vendor, expected):
    assert infer_device_type(vendor) == expected


def test_infer_device_type_case_insensitive():
    assert infer_device_type("SYNOLOGY INC") == "nas"
    assert infer_device_type("synology inc") == "nas"


def test_infer_device_type_unknown_returns_none():
    assert infer_device_type("Totally Unknown Vendor Ltd") is None


def test_infer_device_type_none_input_returns_none():
    assert infer_device_type(None) is None


def test_resolve_device_type_explicit_wins(make_host_factory):
    h = make_host_factory(vendor="Synology", device_type="laptop")
    assert _resolve_device_type(h) == "laptop"


def test_resolve_device_type_falls_back_to_inferred(make_host_factory):
    h = make_host_factory(vendor="Synology Incorporated", device_type=None)
    assert _resolve_device_type(h) == "nas"


def test_resolve_device_type_invalid_explicit_falls_back_to_other(make_host_factory):
    h = make_host_factory(vendor="Synology Incorporated", device_type="refrigerator")
    assert _resolve_device_type(h) == "other"


def test_resolve_device_type_no_match_no_explicit_returns_other(make_host_factory):
    h = make_host_factory(vendor="Totally Unknown", device_type=None)
    assert _resolve_device_type(h) == "other"


# ---------------------------------------------------------------------------
# Task 2: Host.device_type + Host.manual fields with round-trip and validation
# ---------------------------------------------------------------------------

def test_host_device_type_defaults_to_none(make_host_factory):
    h = make_host_factory()
    assert h.device_type is None


def test_host_manual_defaults_to_false(make_host_factory):
    h = make_host_factory()
    assert h.manual is False


def test_host_to_dict_includes_new_fields(make_host_factory):
    h = make_host_factory(device_type="nas", manual=True)
    d = h.to_dict()
    assert d["device_type"] == "nas"
    assert d["manual"] is True


def test_host_from_dict_reads_new_fields():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        "device_type": "nas",
        "manual": True,
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.device_type == "nas"
    assert h.manual is True


def test_host_from_dict_missing_new_fields_uses_defaults():
    """Backward compatibility: existing YAMLs without device_type/manual load
    with the new defaults (None and False)."""
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        # no device_type, no manual
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.device_type is None
    assert h.manual is False


def test_host_from_dict_device_type_bad_type_raises():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        "device_type": 42,  # not a string
    }
    with pytest.raises(ValueError, match="device_type"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_from_dict_manual_bad_type_raises():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        "manual": "yes",  # not a bool
    }
    with pytest.raises(ValueError, match="manual"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_round_trip_with_new_fields():
    from intramap.models import Host
    from datetime import datetime
    now = datetime(2026, 5, 25, 0, 0, 0)
    h = Host(
        mac="aa:bb:cc:dd:ee:01",
        ip="192.168.1.10",
        hostname=None,
        vendor="Synology",
        first_seen=now,
        last_seen=now,
        device_type="nas",
        manual=True,
    )
    restored = Host.from_dict(h.mac, h.to_dict())
    assert restored == h


# ---------------------------------------------------------------------------
# Task 5: Host.wifi_ap_mac field
# ---------------------------------------------------------------------------

def test_host_wifi_ap_mac_defaults_to_none(make_host_factory):
    h = make_host_factory()
    assert h.wifi_ap_mac is None


def test_host_wifi_ap_mac_normalized(make_host_factory):
    h = make_host_factory(wifi_ap_mac="AA-BB-CC-DD-EE-02")
    assert h.wifi_ap_mac == "aa:bb:cc:dd:ee:02"


def test_host_to_dict_includes_wifi_ap_mac(make_host_factory):
    h = make_host_factory(wifi_ap_mac="aa:bb:cc:dd:ee:02")
    d = h.to_dict()
    assert d["wifi_ap_mac"] == "aa:bb:cc:dd:ee:02"


def test_host_from_dict_reads_wifi_ap_mac():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10", "hostname": None, "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None, "device_type": None, "manual": False,
        "wifi_ap_mac": "aa:bb:cc:dd:ee:02",
        "first_seen": now, "last_seen": now, "online": True,
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.wifi_ap_mac == "aa:bb:cc:dd:ee:02"


def test_host_from_dict_missing_wifi_ap_mac_defaults_to_none():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10", "hostname": None, "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None, "device_type": None, "manual": False,
        "first_seen": now, "last_seen": now, "online": True,
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.wifi_ap_mac is None


def test_host_from_dict_wifi_ap_mac_bad_type_raises():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10", "hostname": None, "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None, "device_type": None, "manual": False,
        "wifi_ap_mac": 42,  # not a string
        "first_seen": now, "last_seen": now, "online": True,
    }
    with pytest.raises(ValueError, match="wifi_ap_mac"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_round_trip_with_wifi_ap_mac(make_host_factory):
    from intramap.models import Host
    h = make_host_factory(wifi_ap_mac="aa:bb:cc:dd:ee:02")
    restored = Host.from_dict(h.mac, h.to_dict())
    assert restored == h
