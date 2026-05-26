"""Tests de la couche de mise en page (``intramap.gui.layout``).

Ce module ne dépend pas de Qt : il se teste directement, sans QApplication.
Couvre la sérialisation aller-retour, la robustesse aux entrées invalides,
le déterminisme de l'auto-layout et la migration du fichier compagnon.
"""
from datetime import datetime

from intramap.gui.layout import (
    DEFAULT_ROUTING_STYLE, LayoutData, auto_layout, layout_from_dict,
    layout_to_dict, positions_for, read_legacy_sidecar,
)
from intramap.models import Host, Inventory, Location


def _h(mac, **kw):
    now = datetime(2026, 5, 25)
    d = dict(ip=None, hostname=None, vendor=None, first_seen=now, last_seen=now)
    d.update(kw)
    return Host(mac=mac, **d)


def _inv(*hosts):
    return Inventory(hosts={h.mac: h for h in hosts})


def test_layout_round_trip():
    data = LayoutData(
        positions={"aa:bb:cc:dd:ee:01": (10.0, 20.0)},
        edge_bends={"aa:bb:cc:dd:ee:01|aa:bb:cc:dd:ee:02|wired": 5.5},
        routing_style="ortho_v",
        switch_ports={"aa:bb:cc:dd:ee:01": 24},
    )
    assert layout_from_dict(layout_to_dict(data)) == data


def test_layout_from_dict_ignores_invalid_entries():
    ld = layout_from_dict({
        "positions": {"aa:bb:cc:dd:ee:01": {"x": "bad"},
                      "not-a-mac": {"x": 1, "y": 2}},
        "edges": {"k": {"split": "nope"}},
        "routing_style": "diagonal",
        "switch_ports": {"aa:bb:cc:dd:ee:01": "x"},
    })
    assert ld.positions == {}
    assert ld.edge_bends == {}
    assert ld.routing_style == DEFAULT_ROUTING_STYLE
    assert ld.switch_ports == {}


def test_layout_from_dict_empty():
    ld = layout_from_dict({})
    assert ld == LayoutData()


def test_auto_layout_is_deterministic():
    inv = _inv(
        _h("aa:bb:cc:dd:ee:01", location=Location(floor="RDC", room="salon")),
        _h("aa:bb:cc:dd:ee:02", location=Location(floor="RDC", room="cuisine")),
        _h("aa:bb:cc:dd:ee:03", location=Location(floor="Étage")),
        _h("aa:bb:cc:dd:ee:04"),
    )
    assert auto_layout(inv) == auto_layout(inv)


def test_positions_for_keeps_saved_and_places_new():
    a = _h("aa:bb:cc:dd:ee:01")
    b = _h("aa:bb:cc:dd:ee:02")
    inv = _inv(a, b)
    pos = positions_for(inv, {a.mac: (100.0, 200.0)})
    assert pos[a.mac] == (100.0, 200.0)
    assert b.mac in pos  # nouveau placé par l'auto-layout


def test_read_legacy_sidecar_missing_returns_empty(tmp_path):
    assert read_legacy_sidecar(tmp_path / "inv.yaml") == {}


def test_read_legacy_sidecar_reads_json(tmp_path):
    (tmp_path / "inv.layout.json").write_text(
        '{"routing_style": "straight"}', encoding="utf-8")
    assert read_legacy_sidecar(tmp_path / "inv.yaml") == {
        "routing_style": "straight"}


def test_read_legacy_sidecar_corrupt_returns_empty(tmp_path):
    (tmp_path / "inv.layout.json").write_text("{not json", encoding="utf-8")
    assert read_legacy_sidecar(tmp_path / "inv.yaml") == {}
