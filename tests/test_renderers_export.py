"""Tests des renderers d'export Mermaid et HTML interactif."""
import json
from datetime import datetime

from intramap.models import Host, Inventory, Link, Location
from intramap.renderers.mermaid import render as render_mermaid
from intramap.renderers.html import render as render_html


def _h(mac, ip=None, *, custom_name=None, device_type=None, location=None,
       online=True, wifi_ap_mac=None):
    now = datetime(2026, 5, 26)
    return Host(mac=mac, ip=ip, hostname=None, vendor=None,
                custom_name=custom_name, device_type=device_type,
                location=location or Location(), first_seen=now, last_seen=now,
                online=online, wifi_ap_mac=wifi_ap_mac)


def _inv(*hosts, links=None):
    return Inventory(hosts={h.mac: h for h in hosts}, links=list(links or []))


# -- Mermaid ---------------------------------------------------------------

def test_mermaid_starts_with_flowchart():
    out = render_mermaid(Inventory())
    assert out.startswith("flowchart TB")


def test_mermaid_renders_node_and_floor_subgraph():
    h = _h("aa:bb:cc:dd:ee:01", "192.168.1.1", custom_name="Box",
           device_type="router", location=Location(floor="RDC", room="Salon"))
    out = render_mermaid(_inv(h))
    assert "Box" in out and "192.168.1.1" in out
    assert 'subgraph' in out and "RDC" in out


def test_mermaid_poe_link_is_thick_and_wifi_dashed():
    sw = _h("aa:bb:cc:dd:ee:01", custom_name="SW", device_type="switch")
    cam = _h("aa:bb:cc:dd:ee:02", custom_name="Cam", device_type="camera")
    ap = _h("aa:bb:cc:dd:ee:03", custom_name="AP", device_type="ap")
    phone = _h("aa:bb:cc:dd:ee:04", custom_name="Phone", device_type="phone",
               wifi_ap_mac=ap.mac)
    out = render_mermaid(_inv(sw, cam, ap, phone, links=[
        Link(mac_a=sw.mac, port_a=1, mac_b=cam.mac, port_b=1, poe=True)]))
    assert "===" in out          # lien PoE épais
    assert "-.->" in out         # association Wi-Fi pointillée


def test_mermaid_escapes_quotes_in_label():
    h = _h("aa:bb:cc:dd:ee:01", custom_name='PC "test"', device_type="laptop")
    out = render_mermaid(_inv(h))
    assert "&quot;" in out
    assert 'PC "test"' not in out  # le guillemet brut ne doit pas fuiter


# -- HTML ------------------------------------------------------------------

def test_html_is_self_contained_page_with_visnetwork():
    out = render_html(Inventory())
    assert out.startswith("<!DOCTYPE html>")
    assert "vis-network" in out


def test_html_embeds_nodes_json_with_host():
    h = _h("aa:bb:cc:dd:ee:01", "192.168.1.1", custom_name="Box",
           device_type="router")
    out = render_html(_inv(h))
    assert "Box" in out
    assert "h1" in out  # id de nœud


def test_html_json_survives_quotes_and_backslash():
    h = _h("aa:bb:cc:dd:ee:01", custom_name='Pc\\ "x"', device_type="laptop")
    out = render_html(_inv(h))
    # Le bloc nœuds doit rester du JSON valide malgré les caractères spéciaux.
    block = out.split("new vis.DataSet(", 1)[1]
    json_text = block.split(");", 1)[0]
    nodes = json.loads(json_text)          # ne doit pas lever
    assert nodes[0]["label"].startswith('Pc\\ "x"')


def test_html_poe_edge_is_orange():
    sw = _h("aa:bb:cc:dd:ee:01", device_type="switch")
    cam = _h("aa:bb:cc:dd:ee:02", device_type="camera")
    out = render_html(_inv(sw, cam, links=[
        Link(mac_a=sw.mac, port_a=1, mac_b=cam.mac, port_b=1, poe=True)]))
    assert "#ff7f0e" in out
