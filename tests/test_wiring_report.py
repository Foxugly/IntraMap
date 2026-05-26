"""Tests du builder de rapport de branchements (build_wiring_report)."""
from datetime import datetime

import pytest

from intramap.models import Host, Inventory, Link, Location
from intramap.wiring_report import (
    INFRA_TYPES_ORDER, build_wiring_report,
)


_NOW = datetime(2026, 5, 26)


def _h(mac, name, dtype, floor=None, room=None, port_labels=None):
    return Host(mac=mac, ip=None, hostname=None, vendor=None,
                first_seen=_NOW, last_seen=_NOW, custom_name=name,
                device_type=dtype, location=Location(floor=floor, room=room),
                port_labels=port_labels or {})


def test_empty_inventory_returns_message():
    report = build_wiring_report(Inventory())
    assert "Aucun appareil" in report


def test_no_infra_returns_specific_message():
    inv = Inventory()
    inv.hosts["aa:00:00:00:00:01"] = _h("aa:00:00:00:00:01", "phone", "phone")
    report = build_wiring_report(inv)
    assert "Aucun appareil d'infrastructure" in report


def test_groups_appear_in_canonical_order():
    """Routeur > Switch > Patch panel > Outlet, dans cet ordre."""
    inv = Inventory()
    out  = _h("aa:00:00:00:00:01", "Out", "outlet")
    pp   = _h("aa:00:00:00:00:02", "PP",  "patchpanel")
    sw   = _h("aa:00:00:00:00:03", "SW",  "switch")
    box  = _h("aa:00:00:00:00:04", "BOX", "router")
    for d in (out, pp, sw, box):
        inv.hosts[d.mac] = d
    report = build_wiring_report(inv)
    # On verifie l'ordre des entetes ## dans le rapport.
    headers_order = [t for t in INFRA_TYPES_ORDER
                     if f"## " in report]
    # On extrait par recherche d'index croissant.
    positions = [report.find(f"## {label}") for label in (
        "Routeur", "Switch", "Patch panel", "Outlet")]
    assert positions == sorted(positions)
    assert all(p >= 0 for p in positions)


def test_port_labels_on_outlet_appear_between_brackets():
    inv = Inventory()
    pp  = _h("aa:00:00:00:00:01", "PP", "patchpanel")
    out = _h("aa:00:00:00:00:02", "Outlet salon", "outlet",
             port_labels={1: "21"})
    inv.hosts[pp.mac] = pp
    inv.hosts[out.mac] = out
    inv.links = [Link(mac_a=pp.mac, port_a=21, mac_b=out.mac, port_b=1)]

    report = build_wiring_report(inv)
    # Cote patch panel : voit "port 1 [21]" (label de l'outlet).
    assert "port 1 [21]" in report
    # Cote outlet : voit son propre port avec son propre label.
    # (cf. la ligne sous Outlet salon)


def test_poe_marker_present_when_link_is_poe():
    inv = Inventory()
    sw  = _h("aa:00:00:00:00:01", "SW", "switch")
    pp  = _h("aa:00:00:00:00:02", "PP", "patchpanel")
    inv.hosts[sw.mac] = sw
    inv.hosts[pp.mac] = pp
    inv.links = [Link(mac_a=sw.mac, port_a=1, mac_b=pp.mac, port_b=24,
                      poe=True)]
    report = build_wiring_report(inv)
    assert "PoE" in report


def test_no_branchement_message_when_device_isolated():
    inv = Inventory()
    sw = _h("aa:00:00:00:00:01", "SW orphelin", "switch")
    inv.hosts[sw.mac] = sw
    report = build_wiring_report(inv)
    assert "(aucun branchement)" in report


def test_ports_sorted_ascending_on_each_device():
    inv = Inventory()
    sw  = _h("aa:00:00:00:00:01", "SW", "switch")
    a   = _h("aa:00:00:00:00:02", "A",  "laptop")
    b   = _h("aa:00:00:00:00:03", "B",  "laptop")
    c   = _h("aa:00:00:00:00:04", "C",  "laptop")
    for d in (sw, a, b, c):
        inv.hosts[d.mac] = d
    # Liens dans le desordre : ports 7, 1, 3 cote switch.
    inv.links = [
        Link(mac_a=sw.mac, port_a=7, mac_b=a.mac),
        Link(mac_a=sw.mac, port_a=1, mac_b=b.mac),
        Link(mac_a=sw.mac, port_a=3, mac_b=c.mac),
    ]
    report = build_wiring_report(inv)
    # Les "port 1", "port 3", "port 7" doivent apparaitre dans cet ordre.
    i1 = report.find("port 1 ")
    i3 = report.find("port 3 ")
    i7 = report.find("port 7 ")
    assert 0 <= i1 < i3 < i7


def test_unknown_peer_mac_does_not_crash():
    """Si un Link reference une MAC inexistante, le rapport reste lisible."""
    inv = Inventory()
    sw = _h("aa:00:00:00:00:01", "SW", "switch")
    inv.hosts[sw.mac] = sw
    inv.links = [Link(mac_a=sw.mac, port_a=1, mac_b="ff:ff:ff:ff:ff:ff",
                      port_b=2)]
    report = build_wiring_report(inv)
    assert "port 1" in report
    assert "ff:ff:ff:ff:ff:ff" in report
