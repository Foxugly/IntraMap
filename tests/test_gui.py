"""Tests d'interface (Qt offscreen) et helpers GUI testables sans affichage.

Couvre les correctifs : déduplication des liaisons via l'inspecteur (bug 1),
cible de suppression correcte (bug 4), clé d'arête indépendante de
l'orientation (bug 5), masquage persistant des poignées de coude (bug 6),
purge des labels de ports hors plage (bug 7).
"""
from datetime import datetime

import pytest

from intramap.models import Host, Inventory, Link

pytest.importorskip("PySide6.QtWidgets")


def _host(mac, **kw):
    now = datetime(2026, 5, 25)
    d = dict(ip=None, hostname=None, vendor=None, first_seen=now, last_seen=now)
    d.update(kw)
    return Host(mac=mac, **d)


def _inv(*hosts, links=None):
    return Inventory(hosts={h.mac: h for h in hosts}, links=list(links or []))


# ---------------------------------------------------------------------------
# Bug 5 — edge_key indépendant de l'ordre des extrémités (fonction pure)
# ---------------------------------------------------------------------------

def test_edge_key_is_orientation_independent():
    from intramap.gui.edge import edge_key
    a, b = "aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"
    assert edge_key(a, b, "wired") == edge_key(b, a, "wired")


def test_edge_key_distinguishes_kind():
    from intramap.gui.edge import edge_key
    a, b = "aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:02"
    assert edge_key(a, b, "wired") != edge_key(a, b, "wifi")


# ---------------------------------------------------------------------------
# Bug 7 — purge des labels de ports au-delà du nombre déclaré (fonction pure)
# ---------------------------------------------------------------------------

def test_clean_labels_drops_ports_beyond_count_and_blanks():
    from intramap.gui.switch_dialog import clean_labels
    cleaned = clean_labels({1: "câble 21", 2: "  ", 5: "jack hors plage"}, 4)
    assert cleaned == {1: "câble 21"}


# ---------------------------------------------------------------------------
# Bug 1 (frontend) — l'inspecteur ne crée pas de liaison en double
# ---------------------------------------------------------------------------

def test_inspector_apply_does_not_duplicate_existing_link(qapp):
    from intramap.gui.inspector import Inspector
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    b = _host("aa:bb:cc:dd:ee:02", custom_name="B")
    existing = Link(mac_a=a.mac, port_a=1, mac_b=b.mac, port_b=2)
    inv = _inv(a, b, links=[existing])

    insp = Inspector()
    insp.set_host(a, inv)
    insp._add_link()
    row = insp._link_rows[-1]
    row._this_port.setText("1")
    row._peer_port.setText("2")
    row._peer.setCurrentIndex(row._peer.findData(b.mac))
    insp._apply()

    assert len(inv.links) == 1


def test_inspector_apply_adds_genuinely_new_link(qapp):
    from intramap.gui.inspector import Inspector
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    b = _host("aa:bb:cc:dd:ee:02", custom_name="B")
    inv = _inv(a, b)

    insp = Inspector()
    insp.set_host(a, inv)
    insp._add_link()
    row = insp._link_rows[-1]
    row._this_port.setText("3")
    row._peer_port.setText("4")
    row._peer.setCurrentIndex(row._peer.findData(b.mac))
    insp._apply()

    assert len(inv.links) == 1
    assert inv.links[0].touches(a.mac) and inv.links[0].touches(b.mac)


# ---------------------------------------------------------------------------
# Bug 6 — les poignées de coude restent masquées après un déplacement de nœud
# ---------------------------------------------------------------------------

def test_edge_handle_stays_hidden_after_node_move(qapp):
    from PySide6.QtWidgets import QGraphicsScene
    from intramap.gui.node import DeviceNode
    from intramap.gui.edge import Edge

    scene = QGraphicsScene()
    a = DeviceNode(_host("aa:bb:cc:dd:ee:01"))
    b = DeviceNode(_host("aa:bb:cc:dd:ee:02"))
    scene.addItem(a)
    scene.addItem(b)
    edge = Edge(a, b, "wired", "", "ortho_h")
    scene.addItem(edge)

    edge.set_handles_visible(False)
    assert not edge.handle.isVisible()

    a.setPos(300.0, 200.0)  # déclenche Edge.adjust()
    assert not edge.handle.isVisible(), \
        "le coude doit rester masqué après un déplacement de nœud"


# ---------------------------------------------------------------------------
# Bug 4 — Supprimer agit sur l'appareil sélectionné sur la carte
# ---------------------------------------------------------------------------

def test_delete_selected_removes_canvas_selection_not_inspector_host(
        qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from intramap.gui.main_window import MainWindow

    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    b = _host("aa:bb:cc:dd:ee:02", custom_name="B")
    win.inv = _inv(a, b)
    win._reload_canvas()

    # Sélection carte = A, mais l'inspecteur affiche B (cas d'un « goto » pair).
    win.canvas.select_mac(a.mac)
    win.inspector.set_host(b, win.inv)

    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))
    win._delete_selected()

    assert a.mac not in win.inv.hosts, "l'appareil sélectionné doit être supprimé"
    assert b.mac in win.inv.hosts, "l'appareil non sélectionné doit rester"


# ---------------------------------------------------------------------------
# Rapport des chemins réseau (build_report) — fonction pure, sans QApplication
# ---------------------------------------------------------------------------

def test_path_report_traces_device_to_gateway():
    from intramap.gui.path_report_dialog import build_report
    gw = _host("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router",
               custom_name="Box")
    pc = _host("aa:bb:cc:dd:ee:02", device_type="laptop", custom_name="PC")
    inv = _inv(gw, pc,
               links=[Link(mac_a=pc.mac, port_a=1, mac_b=gw.mac, port_b=2)])
    report = build_report(inv)
    assert "Box" in report and "PC" in report
    assert "Passerelle Internet" in report
    assert "Accès Internet" in report


def test_path_report_flags_unreachable_device():
    from intramap.gui.path_report_dialog import build_report
    gw = _host("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    orphan = _host("aa:bb:cc:dd:ee:02", device_type="laptop",
                   custom_name="Isolé")
    report = build_report(_inv(gw, orphan))
    assert "aucun chemin" in report


# ---------------------------------------------------------------------------
# ScanWorker — logique de run() et cycle de vie du thread à la fermeture
# ---------------------------------------------------------------------------

def test_scan_worker_emits_succeeded_with_results(qapp, monkeypatch):
    from intramap.gui import scan_worker
    from intramap.models import DiscoveredHost
    fake = [DiscoveredHost(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
                           hostname=None, vendor=None)]
    monkeypatch.setattr(scan_worker.scanner, "scan", lambda net: fake)
    w = scan_worker.ScanWorker("192.168.1.0/24")
    got = []
    w.succeeded.connect(got.append)
    w.run()  # exécution synchrone : on teste la logique hors thread
    assert got == [fake]


def test_scan_worker_emits_failed_on_error(qapp, monkeypatch):
    from intramap.gui import scan_worker

    def boom(net):
        raise RuntimeError("nmap introuvable")

    monkeypatch.setattr(scan_worker.scanner, "scan", boom)
    w = scan_worker.ScanWorker("192.168.1.0/24")
    errs = []
    w.failed.connect(errs.append)
    w.run()
    assert errs and "nmap introuvable" in errs[0]


def test_close_waits_for_running_scan_worker(qapp, tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from intramap.gui.main_window import MainWindow

    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    monkeypatch.setattr(win, "_confirm_discard", lambda: True)
    worker = MagicMock()
    win._scan_worker = worker
    event = MagicMock()

    win.closeEvent(event)

    worker.wait.assert_called_once()
    event.accept.assert_called_once()
