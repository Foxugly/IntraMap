"""Tests du diagnostic d'anomalies de câblage (sans Qt)."""
from datetime import datetime

from intramap.models import Host, Inventory, Link
from intramap.diagnostics import diagnose


def _h(mac, **kw):
    now = datetime(2026, 5, 26)
    d = dict(ip=None, hostname=None, vendor=None, first_seen=now, last_seen=now)
    d.update(kw)
    return Host(mac=mac, **d)


def _inv(*hosts, links=None):
    return Inventory(hosts={h.mac: h for h in hosts}, links=list(links or []))


def _cat(findings, category):
    return [f for f in findings if f.category == category]


def test_clean_inventory_has_no_findings():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    pc = _h("aa:bb:cc:dd:ee:02", device_type="laptop")
    inv = _inv(gw, pc,
               links=[Link(mac_a=pc.mac, port_a=1, mac_b=gw.mac, port_b=1)])
    assert diagnose(inv) == []


def test_dangling_link_is_error():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    inv = _inv(gw, links=[Link(mac_a=gw.mac, port_a=1,
                               mac_b="ff:ff:ff:ff:ff:ff", port_b=2)])
    f = _cat(diagnose(inv), "broken-link")
    assert f and f[0].severity == "error"
    assert "ff:ff:ff:ff:ff:ff" in f[0].message
    assert gw.mac in f[0].macs


def test_self_loop_link_is_error():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    inv = _inv(gw, links=[Link(mac_a=gw.mac, port_a=1, mac_b=gw.mac, port_b=2)])
    f = _cat(diagnose(inv), "broken-link")
    assert f and f[0].severity == "error"


def test_unreachable_device_is_warning():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    orphan = _h("aa:bb:cc:dd:ee:02", device_type="laptop")
    f = _cat(diagnose(_inv(gw, orphan)), "unreachable")
    assert f and f[0].macs == (orphan.mac,)


def test_no_unreachable_when_no_gateway():
    a = _h("aa:bb:cc:dd:ee:01", device_type="laptop")
    findings = diagnose(_inv(a))
    assert not _cat(findings, "unreachable")
    assert _cat(findings, "gateway")


def test_port_oversubscribed_on_switch_is_warning():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    sw = _h("aa:bb:cc:dd:ee:02", device_type="switch")
    a = _h("aa:bb:cc:dd:ee:03", device_type="laptop")
    b = _h("aa:bb:cc:dd:ee:04", device_type="laptop")
    inv = _inv(gw, sw, a, b, links=[
        Link(mac_a=sw.mac, port_a=5, mac_b=a.mac, port_b=1),
        Link(mac_a=sw.mac, port_a=5, mac_b=b.mac, port_b=1),  # port 5 doublé
    ])
    f = _cat(diagnose(inv), "port-conflict")
    assert f and sw.mac in f[0].macs
    assert "5" in f[0].message


def test_patch_panel_two_cables_same_port_not_flagged():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    pp = _h("aa:bb:cc:dd:ee:02", device_type="patchpanel")
    a = _h("aa:bb:cc:dd:ee:03", device_type="laptop")
    inv = _inv(gw, pp, a, links=[
        Link(mac_a=pp.mac, port_a=10, mac_b=gw.mac, port_b=1),
        Link(mac_a=pp.mac, port_a=10, mac_b=a.mac, port_b=1),  # pass-through
    ])
    assert not _cat(diagnose(inv), "port-conflict")


def test_patch_panel_three_cables_same_port_flagged():
    pp = _h("aa:bb:cc:dd:ee:02", device_type="patchpanel")
    a = _h("aa:bb:cc:dd:ee:03", device_type="laptop")
    b = _h("aa:bb:cc:dd:ee:04", device_type="laptop")
    c = _h("aa:bb:cc:dd:ee:05", device_type="laptop")
    inv = _inv(pp, a, b, c, links=[
        Link(mac_a=pp.mac, port_a=10, mac_b=a.mac, port_b=1),
        Link(mac_a=pp.mac, port_a=10, mac_b=b.mac, port_b=1),
        Link(mac_a=pp.mac, port_a=10, mac_b=c.mac, port_b=1),
    ])
    assert _cat(diagnose(inv), "port-conflict")


def test_no_gateway_is_warning():
    a = _h("aa:bb:cc:dd:ee:01", device_type="laptop")
    f = _cat(diagnose(_inv(a)), "gateway")
    assert f and f[0].severity == "warning"


def test_wifi_ap_unknown_mac_is_error():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    phone = _h("aa:bb:cc:dd:ee:02", device_type="phone",
               wifi_ap_mac="ff:ff:ff:ff:ff:fe")
    f = _cat(diagnose(_inv(gw, phone)), "wifi")
    assert f and f[0].severity == "error"


def test_wifi_ap_pointing_to_non_ap_is_warning():
    gw = _h("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    printer = _h("aa:bb:cc:dd:ee:02", device_type="printer")
    phone = _h("aa:bb:cc:dd:ee:03", device_type="phone",
               wifi_ap_mac=printer.mac)
    f = _cat(diagnose(_inv(gw, printer, phone)), "wifi")
    assert f and f[0].severity == "warning"
    assert phone.mac in f[0].macs and printer.mac in f[0].macs
