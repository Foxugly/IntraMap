"""Tests du builder de rapport de chemins (sans Qt)."""
from datetime import datetime

from intramap.models import Host, Inventory, Link
from intramap.path_report import build_report


def _h(mac, **kw):
    now = datetime(2026, 5, 25)
    d = dict(ip=None, hostname=None, vendor=None, first_seen=now, last_seen=now)
    d.update(kw)
    return Host(mac=mac, **d)


def _inv(*hosts, links=None):
    return Inventory(hosts={h.mac: h for h in hosts}, links=list(links or []))


def test_build_report_traces_device_to_gateway():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router",
            custom_name="Box")
    pc = _h("aa:bb:cc:dd:ee:02", device_type="laptop", custom_name="PC")
    inv = _inv(gw, pc,
               links=[Link(mac_a=pc.mac, port_a=1, mac_b=gw.mac, port_b=2)])
    report = build_report(inv)
    assert "Box" in report and "PC" in report
    assert "Accès Internet" in report


def test_build_report_flags_unreachable_device():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    orphan = _h("aa:bb:cc:dd:ee:02", device_type="laptop", custom_name="Isolé")
    report = build_report(_inv(gw, orphan))
    assert "aucun chemin" in report


def test_build_report_empty_inventory():
    assert "Aucun appareil" in build_report(Inventory())
