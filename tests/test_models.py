from datetime import datetime

import pytest

from intramap.models import (
    DEVICE_TYPES, DiscoveredHost, Host, Inventory, Link, Location,
    _resolve_device_type, infer_device_type, is_valid_ip, links_touching,
    normalize_mac, trace_all_paths, trace_paths,
)


@pytest.mark.parametrize("text, expected", [
    ("192.168.1.1", True),
    ("10.0.0.255", True),
    ("::1", True),
    ("2001:db8::1", True),
    ("999.1.1.1", False),
    ("not-an-ip", False),
    ("", False),
    ("   ", False),
])
def test_is_valid_ip(text, expected):
    assert is_valid_ip(text) is expected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def make_host_factory():
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


def _h(mac, **kw):
    now = datetime(2026, 5, 25)
    d = dict(ip=None, hostname=None, vendor=None, first_seen=now, last_seen=now)
    d.update(kw)
    return Host(mac=mac, **d)


def _inv(*hosts, links=None, last_scan=None):
    return Inventory(
        hosts={h.mac: h for h in hosts},
        links=list(links or []),
        last_scan=last_scan,
    )


# ---------------------------------------------------------------------------
# normalize_mac
# ---------------------------------------------------------------------------

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
    "", "not-a-mac", "aa:bb:cc:dd:ee", "aa:bb:cc:dd:ee:ff:gg",
    "zz:bb:cc:dd:ee:ff",
])
def test_normalize_mac_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_mac(bad)


def test_discovered_host_normalizes_mac():
    h = DiscoveredHost(mac="AA-BB-CC-DD-EE-01", ip="192.168.1.1",
                       hostname="box", vendor="Sagemcom")
    assert h.mac == "aa:bb:cc:dd:ee:01"


# ---------------------------------------------------------------------------
# Link : modèle symétrique d'un câble
# ---------------------------------------------------------------------------

def test_link_normalizes_macs():
    lk = Link(mac_a="AA-BB-CC-DD-EE-01", mac_b="AA:BB:CC:DD:EE:02",
              port_a=1, port_b=24, poe=True)
    assert lk.mac_a == "aa:bb:cc:dd:ee:01"
    assert lk.mac_b == "aa:bb:cc:dd:ee:02"


def test_link_touches_either_endpoint():
    lk = Link(mac_a="aa:bb:cc:dd:ee:01", mac_b="aa:bb:cc:dd:ee:02")
    assert lk.touches("aa:bb:cc:dd:ee:01")
    assert lk.touches("aa:bb:cc:dd:ee:02")
    assert not lk.touches("aa:bb:cc:dd:ee:03")


def test_link_other_mac_and_port_at():
    lk = Link(mac_a="aa:bb:cc:dd:ee:01", port_a=1,
              mac_b="aa:bb:cc:dd:ee:02", port_b=24)
    assert lk.other_mac("aa:bb:cc:dd:ee:01") == "aa:bb:cc:dd:ee:02"
    assert lk.other_mac("aa:bb:cc:dd:ee:02") == "aa:bb:cc:dd:ee:01"
    assert lk.port_at("aa:bb:cc:dd:ee:01") == 1
    assert lk.port_at("aa:bb:cc:dd:ee:02") == 24


def test_link_other_mac_raises_for_non_endpoint():
    lk = Link(mac_a="aa:bb:cc:dd:ee:01", mac_b="aa:bb:cc:dd:ee:02")
    with pytest.raises(ValueError):
        lk.other_mac("aa:bb:cc:dd:ee:99")


# ---------------------------------------------------------------------------
# Host : champs et round-trip
# ---------------------------------------------------------------------------

def test_host_normalizes_mac_and_defaults():
    now = datetime(2026, 5, 24)
    h = Host(mac="AA:BB:CC:DD:EE:02", ip="192.168.1.10",
             hostname=None, vendor="Cisco",
             first_seen=now, last_seen=now)
    assert h.mac == "aa:bb:cc:dd:ee:02"
    assert h.custom_name is None
    assert h.location == Location()
    assert h.online is True
    assert h.is_gateway is False
    assert h.poe_gateway is None
    assert h.wifi_ap_mac is None
    assert h.manual is False


def test_location_empty_by_default():
    loc = Location()
    assert loc.floor is None and loc.room is None
    assert loc.rack is None and loc.rack_unit is None


def test_host_round_trip(make_host_factory):
    h = make_host_factory(custom_name="X",
                          location=Location(floor="RDC", room="salon"))
    restored = Host.from_dict(h.mac, h.to_dict())
    assert restored == h


# ---------------------------------------------------------------------------
# Inventory : to_dict / from_dict avec liaisons
# ---------------------------------------------------------------------------

def test_inventory_round_trip_with_links():
    a = _h("aa:bb:cc:dd:ee:01", custom_name="A")
    b = _h("aa:bb:cc:dd:ee:02", custom_name="B")
    inv = Inventory(
        hosts={a.mac: a, b.mac: b},
        links=[Link(mac_a=a.mac, port_a=1, mac_b=b.mac, port_b=24, poe=False)],
        last_scan=datetime(2026, 5, 25),
    )
    restored = Inventory.from_dict(inv.to_dict())
    assert restored == inv


def test_inventory_no_links_round_trip(make_host_factory):
    h = make_host_factory()
    inv = Inventory(hosts={h.mac: h}, last_scan=datetime(2026, 5, 25))
    restored = Inventory.from_dict(inv.to_dict())
    assert restored == inv
    assert restored.links == []


# ---------------------------------------------------------------------------
# Compat ascendante : les anciens uplinks/uplink sont convertis en Link
# ---------------------------------------------------------------------------

def test_inventory_from_dict_legacy_uplinks_become_links():
    """L'ancienne forme `uplinks:` (liste par hôte) est convertie en liens."""
    data = {
        "last_scan": "2026-05-25T00:00:00",
        "hosts": {
            "aa:bb:cc:dd:ee:01": {
                "ip": None, "hostname": None, "vendor": None,
                "custom_name": None, "location": {},
                "first_seen": "2026-05-25T00:00:00",
                "last_seen": "2026-05-25T00:00:00", "online": True,
                "uplinks": [
                    {"switch_mac": "aa:bb:cc:dd:ee:02",
                     "switch_port": 4, "patch_port": 7, "poe": True},
                ],
            },
            "aa:bb:cc:dd:ee:02": {
                "ip": None, "hostname": None, "vendor": None,
                "custom_name": None, "location": {},
                "first_seen": "2026-05-25T00:00:00",
                "last_seen": "2026-05-25T00:00:00", "online": True,
            },
        },
    }
    inv = Inventory.from_dict(data)
    assert len(inv.links) == 1
    lk = inv.links[0]
    assert lk.mac_a == "aa:bb:cc:dd:ee:01"
    assert lk.port_a == 7
    assert lk.mac_b == "aa:bb:cc:dd:ee:02"
    assert lk.port_b == 4
    assert lk.poe is True


def test_inventory_from_dict_legacy_uplink_singular():
    """L'ancienne forme `uplink:` (un seul, par hôte) est aussi convertie."""
    data = {
        "last_scan": "2026-05-25T00:00:00",
        "hosts": {
            "aa:bb:cc:dd:ee:01": {
                "ip": None, "hostname": None, "vendor": None,
                "custom_name": None, "location": {},
                "first_seen": "2026-05-25T00:00:00",
                "last_seen": "2026-05-25T00:00:00", "online": True,
                "uplink": {"switch_mac": "aa:bb:cc:dd:ee:02",
                           "switch_port": 4},
            },
        },
    }
    inv = Inventory.from_dict(data)
    assert len(inv.links) == 1
    assert inv.links[0].mac_a == "aa:bb:cc:dd:ee:01"
    assert inv.links[0].mac_b == "aa:bb:cc:dd:ee:02"


def test_inventory_from_dict_legacy_uplink_null_no_link():
    data = {
        "last_scan": "2026-05-25T00:00:00",
        "hosts": {
            "aa:bb:cc:dd:ee:01": {
                "ip": None, "hostname": None, "vendor": None,
                "custom_name": None, "location": {},
                "first_seen": "2026-05-25T00:00:00",
                "last_seen": "2026-05-25T00:00:00", "online": True,
                "uplink": None,
            },
        },
    }
    assert Inventory.from_dict(data).links == []


def test_inventory_from_dict_legacy_uplink_invalid_shape_raises():
    """uplink: true (au lieu d'un mapping) lève une erreur claire."""
    data = {
        "last_scan": "2026-05-25T00:00:00",
        "hosts": {
            "aa:bb:cc:dd:ee:01": {
                "ip": None, "hostname": None, "vendor": None,
                "custom_name": None, "location": {},
                "first_seen": "2026-05-25T00:00:00",
                "last_seen": "2026-05-25T00:00:00", "online": True,
                "uplink": True,
            },
        },
    }
    with pytest.raises(ValueError, match="switch_mac"):
        Inventory.from_dict(data)


def test_inventory_from_dict_legacy_doubled_cable_becomes_two_links():
    """Un ancien câble `doubled` est converti en deux Link séparés."""
    data = {
        "hosts": {
            "aa:bb:cc:dd:ee:01": {
                "ip": None, "hostname": None, "vendor": None,
                "custom_name": None, "location": {},
                "first_seen": "2026-05-25T00:00:00",
                "last_seen": "2026-05-25T00:00:00", "online": True,
                "uplinks": [
                    {"switch_mac": "aa:bb:cc:dd:ee:02",
                     "switch_port": 4, "patch_port": 7,
                     "doubled": True, "patch_port_b": 8},
                ],
            },
        },
    }
    inv = Inventory.from_dict(data)
    assert len(inv.links) == 2


# ---------------------------------------------------------------------------
# DEVICE_TYPES + infer / resolve
# ---------------------------------------------------------------------------

def test_device_types_catalogue():
    expected = {
        "router", "switch", "ap", "controller", "nas",
        "tv", "stb", "phone", "tablet", "laptop",
        "iot", "camera", "printer", "voip", "other",
        "outlet", "patchpanel", "appliance",
    }
    assert DEVICE_TYPES == expected


@pytest.mark.parametrize("vendor, expected", [
    ("Sagemcom Broadband SAS", "router"),
    ("Synology Incorporated", "nas"),
    ("Cisco Systems", "switch"),
    ("TP-Link Systems", "ap"),
    ("LG Electronics", "tv"),
    ("Apple Inc", "phone"),
    ("Hikvision", "camera"),
    ("Intel Corporate", "laptop"),
    ("Tuya Smart", "iot"),
    ("Grandstream Networks", "voip"),
    ("Canon Inc", "printer"),
])
def test_infer_device_type_known_vendors(vendor, expected):
    assert infer_device_type(vendor) == expected


def test_infer_device_type_unknown_returns_none():
    assert infer_device_type("Totally Unknown Vendor Ltd") is None
    assert infer_device_type(None) is None


def test_resolve_device_type_explicit_wins(make_host_factory):
    h = make_host_factory(vendor="Synology", device_type="laptop")
    assert _resolve_device_type(h) == "laptop"


def test_resolve_device_type_falls_back_to_inferred(make_host_factory):
    h = make_host_factory(vendor="Synology Incorporated", device_type=None)
    assert _resolve_device_type(h) == "nas"


def test_resolve_device_type_invalid_explicit_falls_back_to_other(make_host_factory):
    h = make_host_factory(vendor="Synology", device_type="refrigerator")
    assert _resolve_device_type(h) == "other"


def test_resolve_device_type_no_match_returns_other(make_host_factory):
    h = make_host_factory(vendor="Totally Unknown", device_type=None)
    assert _resolve_device_type(h) == "other"


# ---------------------------------------------------------------------------
# Champs Host : device_type, manual, is_gateway, poe_gateway, wifi_ap_mac
# ---------------------------------------------------------------------------

def test_host_device_type_defaults_to_none(make_host_factory):
    assert make_host_factory().device_type is None


def test_host_manual_defaults_to_false(make_host_factory):
    assert make_host_factory().manual is False


def test_host_from_dict_device_type_bad_type_raises():
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "device_type": 42,
    }
    with pytest.raises(ValueError, match="device_type"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_from_dict_manual_bad_type_raises():
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "manual": "yes",
    }
    with pytest.raises(ValueError, match="manual"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_wifi_ap_mac_defaults_none_and_normalized(make_host_factory):
    assert make_host_factory().wifi_ap_mac is None
    h = make_host_factory(wifi_ap_mac="AA-BB-CC-DD-EE-02")
    assert h.wifi_ap_mac == "aa:bb:cc:dd:ee:02"


def test_host_is_gateway_defaults_false_and_round_trip(make_host_factory):
    assert make_host_factory().is_gateway is False
    h = make_host_factory(is_gateway=True)
    assert Host.from_dict(h.mac, h.to_dict()) == h


def test_host_from_dict_is_gateway_bad_type_raises():
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "is_gateway": "yes",
    }
    with pytest.raises(ValueError, match="is_gateway"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_poe_gateway_defaults_none_normalized_round_trip(make_host_factory):
    assert make_host_factory().poe_gateway is None
    h = make_host_factory(poe_gateway="AA-BB-CC-DD-EE-02")
    assert h.poe_gateway == "aa:bb:cc:dd:ee:02"
    assert Host.from_dict(h.mac, h.to_dict()) == h


def test_host_from_dict_poe_gateway_bad_type_raises():
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "poe_gateway": 42,
    }
    with pytest.raises(ValueError, match="poe_gateway"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


# ---------------------------------------------------------------------------
# links_touching
# ---------------------------------------------------------------------------

def test_links_touching_returns_both_ends():
    a = _h("aa:bb:cc:dd:ee:01")
    b = _h("aa:bb:cc:dd:ee:02")
    c = _h("aa:bb:cc:dd:ee:03")
    lk1 = Link(mac_a=a.mac, mac_b=b.mac)
    lk2 = Link(mac_a=b.mac, mac_b=c.mac)
    inv = _inv(a, b, c, links=[lk1, lk2])
    assert links_touching(inv, a.mac) == [lk1]
    assert set(map(id, links_touching(inv, b.mac))) == {id(lk1), id(lk2)}
    assert links_touching(inv, c.mac) == [lk2]


# ---------------------------------------------------------------------------
# Traceroute : non-directionnel, BFS depuis la passerelle, transit infra
# ---------------------------------------------------------------------------

def test_trace_paths_linear_chain_reaches_gateway():
    a = _h("aa:bb:cc:dd:ee:03")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    inv = _inv(a, sw, gw, links=[
        Link(mac_a=a.mac, port_a=1, mac_b=sw.mac, port_b=3),
        Link(mac_a=sw.mac, port_a=24, mac_b=gw.mac, port_b=24),
    ])
    paths = trace_paths(inv, a.mac)
    assert len(paths) == 1
    path = paths[0]
    assert [hop.src.mac for hop in path] == [a.mac, sw.mac]
    assert [hop.dst.mac for hop in path] == [sw.mac, gw.mac]


def test_trace_paths_from_gateway_is_empty():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True)
    assert trace_paths(_inv(gw), gw.mac) == [[]]


def test_trace_paths_isolated_host_returns_empty():
    h = _h("aa:bb:cc:dd:ee:01")
    gw = _h("aa:bb:cc:dd:ee:02", is_gateway=True, device_type="router")
    assert trace_paths(_inv(h, gw), h.mac) == [[]]


def test_trace_paths_no_gateway_returns_empty():
    a = _h("aa:bb:cc:dd:ee:01")
    b = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    inv = _inv(a, b, links=[Link(mac_a=a.mac, mac_b=b.mac)])
    assert trace_paths(inv, a.mac) == [[]]


def test_trace_paths_does_not_route_through_leaf_devices():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    laptop = _h("aa:bb:cc:dd:ee:02", device_type="laptop")
    other = _h("aa:bb:cc:dd:ee:03")
    inv = _inv(gw, laptop, other, links=[
        Link(mac_a=laptop.mac, mac_b=gw.mac),
        Link(mac_a=other.mac, mac_b=laptop.mac),
    ])
    # other ne peut pas atteindre gw : il faudrait traverser le laptop (leaf).
    assert trace_paths(inv, other.mac) == [[]]


def test_trace_paths_breaks_cycles():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    a = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    b = _h("aa:bb:cc:dd:ee:03", device_type="switch")
    inv = _inv(gw, a, b, links=[
        Link(mac_a=a.mac, mac_b=gw.mac),
        Link(mac_a=a.mac, mac_b=b.mac),
    ])
    paths = trace_paths(inv, b.mac)
    assert len(paths) == 1
    assert paths[0][-1].dst.mac == gw.mac


def test_trace_all_paths_memoised_returns_one_path_per_host():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    a = _h("aa:bb:cc:dd:ee:03")
    b = _h("aa:bb:cc:dd:ee:04")
    inv = _inv(gw, sw, a, b, links=[
        Link(mac_a=sw.mac, mac_b=gw.mac),
        Link(mac_a=a.mac, mac_b=sw.mac),
        Link(mac_a=b.mac, mac_b=sw.mac),
    ])
    paths = trace_all_paths(inv)
    assert paths[sw.mac][-1].dst.mac == gw.mac
    assert paths[a.mac][-1].dst.mac == gw.mac
    assert paths[b.mac][-1].dst.mac == gw.mac
    assert gw.mac not in paths


# ---------------------------------------------------------------------------
# Traceroute PoE : reste en PoE jusqu'au switch PoE, puis hors PoE
# ---------------------------------------------------------------------------

def test_trace_paths_poe_device_runs_poe_then_non_poe_past_its_switch():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    psw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    pp = _h("aa:bb:cc:dd:ee:03", device_type="patchpanel")
    cam = _h("aa:bb:cc:dd:ee:04", device_type="camera", poe_gateway=psw.mac)
    inv = _inv(gw, psw, pp, cam, links=[
        Link(mac_a=psw.mac, port_a=1, mac_b=gw.mac, port_b=24, poe=False),
        Link(mac_a=pp.mac, port_a=22, mac_b=psw.mac, port_b=5, poe=True),
        Link(mac_a=cam.mac, port_a=None, mac_b=pp.mac, port_b=10, poe=True),
    ])
    paths = trace_paths(inv, cam.mac)
    assert len(paths) == 1
    path = paths[0]
    assert len(path) == 3
    assert path[-1].dst.is_gateway is True
    assert [hop.link.poe for hop in path] == [True, True, False]


def test_trace_paths_poe_device_no_poe_cable_to_its_switch_returns_empty():
    # Caméra PoE qui désigne sw comme switch PoE, mais aucun câble PoE
    # n'y mène : le segment PoE ne se construit pas.
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    cam = _h("aa:bb:cc:dd:ee:04", device_type="camera",
             poe_gateway=sw.mac)
    inv = _inv(gw, sw, cam, links=[
        Link(mac_a=sw.mac, mac_b=gw.mac, poe=False),
        Link(mac_a=cam.mac, mac_b=sw.mac, poe=False),
    ])
    assert trace_paths(inv, cam.mac) == [[]]


def test_trace_paths_coupled_cables_poe_device_picks_poe():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    cam = _h("aa:bb:cc:dd:ee:04", device_type="camera", poe_gateway=sw.mac)
    inv = _inv(gw, sw, cam, links=[
        Link(mac_a=sw.mac, mac_b=gw.mac, poe=False),
        Link(mac_a=cam.mac, port_a=None, mac_b=sw.mac, port_b=8, poe=True),
        Link(mac_a=cam.mac, port_a=None, mac_b=sw.mac, port_b=9, poe=False),
    ])
    paths = trace_paths(inv, cam.mac)
    assert len(paths) == 1
    assert paths[0][0].link.poe is True
    assert paths[0][-1].dst.is_gateway is True


def test_trace_paths_non_poe_device_uses_non_poe_links():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    pc = _h("aa:bb:cc:dd:ee:04", device_type="laptop")
    inv = _inv(gw, sw, pc, links=[
        Link(mac_a=sw.mac, mac_b=gw.mac, poe=False),
        Link(mac_a=pc.mac, mac_b=sw.mac, poe=False),
    ])
    paths = trace_paths(inv, pc.mac)
    assert len(paths) == 1
    assert paths[0][-1].dst.is_gateway is True


def test_trace_paths_cable_declared_from_either_end():
    """Non-directionnel : peu importe l'ordre mac_a/mac_b dans le câble."""
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    pc = _h("aa:bb:cc:dd:ee:03")
    # Câble côté gateway, puis câble côté switch (ordre des extrémités).
    inv = _inv(gw, sw, pc, links=[
        Link(mac_a=gw.mac, port_a=24, mac_b=sw.mac, port_b=1),
        Link(mac_a=sw.mac, port_a=3, mac_b=pc.mac, port_b=1),
    ])
    paths = trace_paths(inv, pc.mac)
    assert len(paths) == 1
    assert paths[0][-1].dst.mac == gw.mac


# ---------------------------------------------------------------------------
# Traceroute via Wi-Fi : wifi_ap_mac comme liaison virtuelle
# ---------------------------------------------------------------------------

def test_trace_paths_wifi_association_is_used_as_a_link():
    """Un appareil sans câble mais associé à un AP atteint la box via le Wi-Fi."""
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    ap = _h("aa:bb:cc:dd:ee:03", device_type="ap")
    phone = _h("aa:bb:cc:dd:ee:04", device_type="phone",
               wifi_ap_mac=ap.mac)
    inv = _inv(gw, sw, ap, phone, links=[
        Link(mac_a=sw.mac, mac_b=gw.mac, poe=False),
        Link(mac_a=ap.mac, mac_b=sw.mac, poe=False),
    ])
    paths = trace_paths(inv, phone.mac)
    assert len(paths) == 1
    path = paths[0]
    # Premier saut Wi-Fi (phone -> AP), suite par cable jusqu'a la box.
    assert path[0].wifi is True
    assert path[0].dst.mac == ap.mac
    assert path[-1].dst.mac == gw.mac


def test_trace_paths_wifi_device_without_ap_returns_empty():
    """Pas d'AP associe et pas de cable : pas de chemin."""
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    phone = _h("aa:bb:cc:dd:ee:04", device_type="phone")
    inv = _inv(gw, phone)
    assert trace_paths(inv, phone.mac) == [[]]


def test_trace_paths_wifi_to_poe_ap_via_poe_cable():
    """Un device Wi-Fi (non-PoE) doit pouvoir transiter par le cable PoE
    qui alimente l'AP. La regle 'pas de PoE' ne s'applique qu'aux
    appareils PoE eux-memes."""
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    pp = _h("aa:bb:cc:dd:ee:02", device_type="patchpanel")
    ap = _h("aa:bb:cc:dd:ee:03", device_type="ap")
    phone = _h("aa:bb:cc:dd:ee:04", device_type="phone",
               wifi_ap_mac=ap.mac)
    inv = _inv(gw, pp, ap, phone, links=[
        # Patch panel relie a la box en non-PoE
        Link(mac_a=pp.mac, port_a=1, mac_b=gw.mac, port_b=24, poe=False),
        # AP alimente en PoE depuis le patch panel
        Link(mac_a=ap.mac, mac_b=pp.mac, port_b=22, poe=True),
    ])
    paths = trace_paths(inv, phone.mac)
    assert len(paths) == 1
    assert paths[0][-1].dst.mac == gw.mac


# ---------------------------------------------------------------------------
# Host.port_labels : labels par port (utile pour outlets)
# ---------------------------------------------------------------------------

def test_host_port_labels_defaults_to_empty(make_host_factory):
    assert make_host_factory().port_labels == {}


def test_host_port_labels_round_trip(make_host_factory):
    h = make_host_factory(port_labels={1: "21", 2: "22"})
    restored = Host.from_dict(h.mac, h.to_dict())
    assert restored == h
    assert restored.port_labels == {1: "21", 2: "22"}


def test_host_from_dict_port_labels_string_keys_coerced_to_int():
    """Certains parseurs YAML rendent des cles str ; on les coerce en int."""
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "port_labels": {"1": "21", "2": "22"},
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.port_labels == {1: "21", 2: "22"}


def test_host_from_dict_port_labels_bad_type_raises():
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "port_labels": "not a dict",
    }
    with pytest.raises(ValueError, match="port_labels"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_from_dict_port_labels_non_int_key_raises():
    data = {
        "ip": None, "hostname": None, "vendor": None, "custom_name": None,
        "location": {}, "first_seen": "2026-05-25T00:00:00",
        "last_seen": "2026-05-25T00:00:00", "online": True,
        "port_labels": {"abc": "21"},
    }
    with pytest.raises(ValueError, match="port_labels"):
        Host.from_dict("aa:bb:cc:dd:ee:ff", data)


def test_trace_paths_patch_panel_strict_pass_through_chooses_matching_port():
    """Quand le patch panel est cable port-a-port (un meme port apparait
    sur 2 cables : un cote vers le switch, l'autre cote vers l'outlet),
    le BFS doit ressortir par le meme port que celui d'entree.

    Scenario : 2 cables PP<->Switch PoE (port 5 et port 22). L'outlet est
    branche sur port 5 du PP. Le chemin AP -> Outlet -> PP -> Switch PoE
    doit utiliser le cable PP:5<->SwPoE:1 (pas PP:22<->SwPoE:2).
    """
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    swpoe = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    pp = _h("aa:bb:cc:dd:ee:03", device_type="patchpanel")
    out = _h("aa:bb:cc:dd:ee:04", device_type="outlet")
    ap = _h("aa:bb:cc:dd:ee:05", device_type="ap", poe_gateway=swpoe.mac)
    inv = _inv(gw, swpoe, pp, out, ap, links=[
        Link(mac_a=swpoe.mac, port_a=24, mac_b=gw.mac, port_b=1),
        # Deux cables PP<->Swpoe : seul celui sur port 5 doit etre choisi.
        Link(mac_a=pp.mac, port_a=22, mac_b=swpoe.mac, port_b=2, poe=True),
        Link(mac_a=pp.mac, port_a=5,  mac_b=swpoe.mac, port_b=1, poe=True),
        # L'outlet est cote port 5 du patch panel.
        Link(mac_a=out.mac, port_a=1, mac_b=pp.mac, port_b=5, poe=True),
        Link(mac_a=ap.mac, port_a=1, mac_b=out.mac, port_b=1, poe=True),
    ])
    paths = trace_paths(inv, ap.mac)
    assert len(paths) == 1
    path = paths[0]
    # On retrouve le hop "PP -> Swpoe" et il doit utiliser port 5 / port 1.
    pp_to_swpoe = next(
        h for h in path
        if h.src.mac == pp.mac and h.dst is not None and h.dst.mac == swpoe.mac
    )
    assert pp_to_swpoe.link.port_at(pp.mac) == 5
    assert pp_to_swpoe.link.port_at(swpoe.mac) == 1


def test_trace_paths_patch_panel_loose_mode_still_works():
    """Un patch panel ou chaque port n'apparait qu'une fois (modele 'naif')
    est traite comme un simple repartiteur : le BFS prend n'importe quel
    cable. Garantit la retrocompatibilite des YAML existants.
    """
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    psw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    pp = _h("aa:bb:cc:dd:ee:03", device_type="patchpanel")
    cam = _h("aa:bb:cc:dd:ee:04", device_type="camera", poe_gateway=psw.mac)
    inv = _inv(gw, psw, pp, cam, links=[
        Link(mac_a=psw.mac, port_a=1, mac_b=gw.mac, port_b=24, poe=False),
        # PP cote A : port 22 (vers switch).
        Link(mac_a=pp.mac, port_a=22, mac_b=psw.mac, port_b=5, poe=True),
        # PP cote B : port 10 (vers camera). Ports differents : pas strict.
        Link(mac_a=cam.mac, port_a=None, mac_b=pp.mac, port_b=10, poe=True),
    ])
    paths = trace_paths(inv, cam.mac)
    assert len(paths) == 1
    path = paths[0]
    assert len(path) > 0
    assert path[-1].dst.mac == gw.mac


# ---------------------------------------------------------------------------
# Inventory.add_link — déduplication centralisée des câbles (par identité
# canonique, ordre des extrémités neutralisé)
# ---------------------------------------------------------------------------

def test_add_link_appends_new_cable_and_reports_true():
    inv = Inventory()
    lk = Link(mac_a="aa:bb:cc:dd:ee:01", port_a=1,
              mac_b="aa:bb:cc:dd:ee:02", port_b=2)
    assert inv.add_link(lk) is True
    assert inv.links == [lk]


def test_add_link_dedups_equivalent_cable_regardless_of_orientation():
    inv = Inventory()
    inv.add_link(Link(mac_a="aa:bb:cc:dd:ee:01", port_a=1,
                      mac_b="aa:bb:cc:dd:ee:02", port_b=2))
    # Même câble décrit dans l'autre sens : ce n'est pas un nouveau câble.
    dup = Link(mac_a="aa:bb:cc:dd:ee:02", port_a=2,
               mac_b="aa:bb:cc:dd:ee:01", port_b=1)
    assert inv.add_link(dup) is False
    assert len(inv.links) == 1


def test_add_link_allows_distinct_cable_on_other_ports():
    inv = Inventory()
    inv.add_link(Link(mac_a="aa:bb:cc:dd:ee:01", port_a=1,
                      mac_b="aa:bb:cc:dd:ee:02", port_b=2))
    assert inv.add_link(Link(mac_a="aa:bb:cc:dd:ee:01", port_a=3,
                             mac_b="aa:bb:cc:dd:ee:02", port_b=4)) is True
    assert len(inv.links) == 2


# ---------------------------------------------------------------------------
# Robustesse du chargement : erreurs claires (ValueError) plutôt que des
# TypeError/KeyError bruts sur un fichier édité à la main
# ---------------------------------------------------------------------------

def test_from_dict_self_loop_link_with_mixed_ports_does_not_crash():
    data = {"links": [{
        "mac_a": "aa:bb:cc:dd:ee:01", "mac_b": "aa:bb:cc:dd:ee:01",
        "port_a": 5, "port_b": None,
    }]}
    inv = Inventory.from_dict(data)
    assert len(inv.links) == 1


def test_from_dict_rejects_unknown_link_field():
    data = {"links": [{
        "mac_a": "aa:bb:cc:dd:ee:01", "mac_b": "aa:bb:cc:dd:ee:02",
        "doubled": True,
    }]}
    with pytest.raises(ValueError, match="doubled"):
        Inventory.from_dict(data)


def test_from_dict_rejects_link_missing_endpoint():
    data = {"links": [{"mac_a": "aa:bb:cc:dd:ee:01", "port_a": 1}]}
    with pytest.raises(ValueError, match="mac_b"):
        Inventory.from_dict(data)


def _host_payload(**over) -> dict:
    base = {
        "ip": "192.168.1.1", "hostname": None, "vendor": None,
        "first_seen": "2026-05-01T10:00:00",
        "last_seen": "2026-05-24T14:30:00",
    }
    base.update(over)
    return base


def test_host_from_dict_unknown_location_field_raises():
    data = _host_payload(location={"floor": "1", "building": "X"})
    with pytest.raises(ValueError, match="location"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_from_dict_missing_first_seen_raises():
    data = _host_payload()
    del data["first_seen"]
    with pytest.raises(ValueError, match="first_seen"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


# ---------------------------------------------------------------------------
# Plusieurs passerelles Internet : chaque appareil doit pouvoir rejoindre la
# passerelle la plus proche (et non uniquement la première déclarée)
# ---------------------------------------------------------------------------

def test_trace_paths_reaches_second_gateway():
    gw1 = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    gw2 = _h("aa:bb:cc:dd:ee:02", is_gateway=True, device_type="router")
    dev = _h("aa:bb:cc:dd:ee:03", device_type="laptop")
    # dev n'est câblé qu'à la seconde box.
    inv = _inv(gw1, gw2, dev,
               links=[Link(mac_a=dev.mac, mac_b=gw2.mac, port_a=1, port_b=4)])
    paths = trace_paths(inv, dev.mac)
    assert len(paths) == 1
    assert paths[0], "le device doit atteindre la 2e passerelle"
    assert paths[0][-1].dst.mac == gw2.mac


def test_trace_all_paths_uses_nearest_of_two_gateways():
    gw1 = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    gw2 = _h("aa:bb:cc:dd:ee:02", is_gateway=True, device_type="router")
    d1 = _h("aa:bb:cc:dd:ee:03", device_type="laptop")
    d2 = _h("aa:bb:cc:dd:ee:04", device_type="laptop")
    inv = _inv(gw1, gw2, d1, d2, links=[
        Link(mac_a=d1.mac, mac_b=gw1.mac, port_a=1, port_b=1),
        Link(mac_a=d2.mac, mac_b=gw2.mac, port_a=1, port_b=1),
    ])
    paths = trace_all_paths(inv)
    assert paths[d1.mac] and paths[d1.mac][-1].dst.mac == gw1.mac
    assert paths[d2.mac] and paths[d2.mac][-1].dst.mac == gw2.mac
