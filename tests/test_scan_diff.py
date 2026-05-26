"""Tests du diff de scan (sans Qt)."""
from datetime import datetime

from intramap.models import Host, Inventory
from intramap.scan_diff import diff_inventories, format_scan_diff


def _h(mac, ip=None, *, online=True, custom_name=None):
    now = datetime(2026, 5, 26)
    return Host(mac=mac, ip=ip, hostname=None, vendor=None, first_seen=now,
                last_seen=now, online=online, custom_name=custom_name)


def _inv(*hosts):
    return Inventory(hosts={h.mac: h for h in hosts})


def test_appeared():
    before = _inv(_h("aa:bb:cc:dd:ee:01"))
    after = _inv(_h("aa:bb:cc:dd:ee:01"), _h("aa:bb:cc:dd:ee:02"))
    d = diff_inventories(before, after)
    assert d.appeared == ["aa:bb:cc:dd:ee:02"]
    assert d.has_changes


def test_gone_offline_and_back_online():
    before = _inv(_h("aa:bb:cc:dd:ee:01", online=True),
                  _h("aa:bb:cc:dd:ee:02", online=False))
    after = _inv(_h("aa:bb:cc:dd:ee:01", online=False),
                 _h("aa:bb:cc:dd:ee:02", online=True))
    d = diff_inventories(before, after)
    assert d.gone_offline == ["aa:bb:cc:dd:ee:01"]
    assert d.back_online == ["aa:bb:cc:dd:ee:02"]


def test_ip_changed():
    before = _inv(_h("aa:bb:cc:dd:ee:01", ip="192.168.1.10"))
    after = _inv(_h("aa:bb:cc:dd:ee:01", ip="192.168.1.20"))
    d = diff_inventories(before, after)
    assert d.ip_changed == [("aa:bb:cc:dd:ee:01", "192.168.1.10",
                             "192.168.1.20")]


def test_no_changes():
    inv1 = _inv(_h("aa:bb:cc:dd:ee:01", ip="192.168.1.10"))
    inv2 = _inv(_h("aa:bb:cc:dd:ee:01", ip="192.168.1.10"))
    d = diff_inventories(inv1, inv2)
    assert d.has_changes is False
    assert "Aucun changement" in format_scan_diff(d, inv2)


def test_format_scan_diff_lists_devices():
    before = _inv()
    after = _inv(_h("aa:bb:cc:dd:ee:02", custom_name="Imprimante"))
    text = format_scan_diff(diff_inventories(before, after), after)
    assert "Nouveaux" in text
    assert "Imprimante" in text
    assert "aa:bb:cc:dd:ee:02" in text
