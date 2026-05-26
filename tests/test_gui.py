"""Tests d'interface (Qt offscreen) et helpers GUI testables sans affichage.

Couvre les correctifs : déduplication des liaisons via l'inspecteur (bug 1),
cible de suppression correcte (bug 4), clé d'arête indépendante de
l'orientation (bug 5), masquage persistant des poignées de coude (bug 6),
purge des labels de ports hors plage (bug 7).
"""
from datetime import datetime
from pathlib import Path

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
# Menu Fichier : Nouveau / Fermer / Récemment ouverts
# ---------------------------------------------------------------------------

def test_push_recent_moves_existing_to_front_and_dedups(tmp_path):
    from intramap.gui.main_window import _push_recent
    a = str(tmp_path / "a.yaml")
    b = str(tmp_path / "b.yaml")
    r = _push_recent([], a)
    r = _push_recent(r, b)
    assert r[0] == str(Path(b).resolve())
    r = _push_recent(r, a)  # déjà présent → revient en tête, pas de doublon
    assert r[0] == str(Path(a).resolve())
    assert len(r) == 2


def test_push_recent_caps_length(tmp_path):
    from intramap.gui.main_window import _push_recent
    r: list[str] = []
    for i in range(15):
        r = _push_recent(r, str(tmp_path / f"f{i}.yaml"), cap=10)
    assert len(r) == 10


def test_new_inventory_resets_to_empty(qapp, tmp_path, monkeypatch):
    from intramap.gui.main_window import MainWindow
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    win.inv = _inv(_host("aa:bb:cc:dd:ee:01"), _host("aa:bb:cc:dd:ee:02"))
    win._reload_canvas()
    monkeypatch.setattr(win, "_confirm_discard", lambda: True)
    monkeypatch.setattr(win, "_persist_recents", lambda: None)
    win._new_inventory()
    assert win.inv.hosts == {}
    assert win.canvas.nodes == {}


def test_close_inventory_resets_to_empty(qapp, tmp_path, monkeypatch):
    from intramap.gui.main_window import MainWindow
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    win.inv = _inv(_host("aa:bb:cc:dd:ee:01"))
    win._reload_canvas()
    monkeypatch.setattr(win, "_confirm_discard", lambda: True)
    monkeypatch.setattr(win, "_persist_recents", lambda: None)
    win._close_inventory()
    assert win.inv.hosts == {}
    assert win.canvas.nodes == {}


def test_loading_inventory_adds_to_recents(qapp, tmp_path, monkeypatch):
    from intramap.gui.main_window import MainWindow
    from intramap.inventory import save
    inv_file = tmp_path / "net.yaml"
    save(_inv(_host("aa:bb:cc:dd:ee:01")), inv_file)
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    monkeypatch.setattr(win, "_persist_recents", lambda: None)
    win._recents = []
    win._load_inventory(inv_file)
    assert str(Path(inv_file).resolve()) in win._recents


def test_recent_menu_lists_existing_files_only(qapp, tmp_path, monkeypatch):
    from intramap.gui.main_window import MainWindow
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    monkeypatch.setattr(win, "_persist_recents", lambda: None)
    present = tmp_path / "here.yaml"
    present.write_text("hosts: {}\n", encoding="utf-8")
    missing = tmp_path / "gone.yaml"
    win._recents = [str(present), str(missing)]
    win._rebuild_recent_menu()
    labels = [a.text() for a in win.menu_recent.actions()]
    assert "here.yaml" in labels
    assert "gone.yaml" not in labels


# ---------------------------------------------------------------------------
# Dialogue Diagnostics
# ---------------------------------------------------------------------------

def test_diagnose_dialog_lists_one_row_per_finding(qapp):
    from intramap.diagnostics import diagnose
    from intramap.gui.diagnose_dialog import DiagnoseDialog
    # Inventaire sans passerelle -> au moins un finding.
    inv = _inv(_host("aa:bb:cc:dd:ee:01", device_type="laptop"))
    dlg = DiagnoseDialog(inv)
    assert dlg._list.count() == len(diagnose(inv))
    assert dlg._list.count() >= 1


def test_diagnose_dialog_double_click_selects_device(qapp):
    from PySide6.QtCore import Qt
    from intramap.gui.diagnose_dialog import DiagnoseDialog
    a = _host("aa:bb:cc:dd:ee:01", device_type="laptop")
    inv = _inv(a, links=[Link(mac_a=a.mac, mac_b="ff:ff:ff:ff:ff:ff")])
    dlg = DiagnoseDialog(inv)
    item = next(dlg._list.item(i) for i in range(dlg._list.count())
                if dlg._list.item(i).data(Qt.UserRole))
    dlg._on_double_click(item)
    assert dlg.selected_mac == a.mac


def test_diagnose_dialog_empty_shows_clean_message(qapp):
    from intramap.gui.diagnose_dialog import DiagnoseDialog
    gw = _host("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router")
    pc = _host("aa:bb:cc:dd:ee:02", device_type="laptop")
    inv = _inv(gw, pc,
               links=[Link(mac_a=pc.mac, port_a=1, mac_b=gw.mac, port_b=1)])
    dlg = DiagnoseDialog(inv)
    assert dlg._list.count() == 1
    assert "Aucune anomalie" in dlg._list.item(0).text()


# ---------------------------------------------------------------------------
# Undo / redo par instantanés
# ---------------------------------------------------------------------------

def _win_with(tmp_path, *hosts, links=None):
    from intramap.gui.main_window import MainWindow
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    win.inv = _inv(*hosts, links=links)
    win._reload_canvas()
    win._reset_history()
    return win


def test_undo_redo_add_device(qapp, tmp_path):
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    win = _win_with(tmp_path, a)
    b = _host("aa:bb:cc:dd:ee:02", custom_name="B")
    win.inv.hosts[b.mac] = b
    win._reload_canvas()
    win._record_history()
    assert b.mac in win.inv.hosts
    win._undo()
    assert b.mac not in win.inv.hosts
    assert a.mac in win.inv.hosts
    win._redo()
    assert b.mac in win.inv.hosts


def test_undo_delete_restores_device_and_link(qapp, tmp_path):
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    b = _host("aa:bb:cc:dd:ee:02", custom_name="B")
    link = Link(mac_a=a.mac, port_a=1, mac_b=b.mac, port_b=2)
    win = _win_with(tmp_path, a, b, links=[link])
    win._on_host_deleted(b.mac)
    assert b.mac not in win.inv.hosts
    assert win.inv.links == []
    win._undo()
    assert b.mac in win.inv.hosts
    assert len(win.inv.links) == 1
    assert win.inv.links[0].touches(a.mac) and win.inv.links[0].touches(b.mac)


def test_undo_reverts_inspector_edit(qapp, tmp_path):
    a = _host("aa:bb:cc:dd:ee:01", custom_name="Old")
    win = _win_with(tmp_path, a)
    win.inv.hosts[a.mac].custom_name = "New"
    win._on_host_changed(a.mac)
    assert win.inv.hosts[a.mac].custom_name == "New"
    win._undo()
    assert win.inv.hosts[a.mac].custom_name == "Old"


def test_undo_preserves_node_positions(qapp, tmp_path):
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    win = _win_with(tmp_path, a)
    win.canvas.nodes[a.mac].setPos(123.0, 456.0)
    win._reset_history()  # baseline avec la position connue
    b = _host("aa:bb:cc:dd:ee:02", custom_name="B")
    win.inv.hosts[b.mac] = b
    win._reload_canvas()
    win._record_history()
    win._undo()
    pos = win.canvas.nodes[a.mac].pos()
    assert (pos.x(), pos.y()) == (123.0, 456.0)


def test_undo_redo_action_enablement(qapp, tmp_path):
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    win = _win_with(tmp_path, a)
    assert not win.act_undo.isEnabled()
    assert not win.act_redo.isEnabled()
    win.inv.hosts["aa:bb:cc:dd:ee:02"] = _host("aa:bb:cc:dd:ee:02")
    win._reload_canvas()
    win._record_history()
    assert win.act_undo.isEnabled()
    assert not win.act_redo.isEnabled()
    win._undo()
    assert not win.act_undo.isEnabled()
    assert win.act_redo.isEnabled()


def test_new_change_after_undo_clears_redo(qapp, tmp_path):
    a = _host("aa:bb:cc:dd:ee:01", custom_name="A")
    win = _win_with(tmp_path, a)
    win.inv.hosts["aa:bb:cc:dd:ee:02"] = _host("aa:bb:cc:dd:ee:02")
    win._reload_canvas()
    win._record_history()
    win._undo()
    assert win.act_redo.isEnabled()
    # Nouvelle action après undo : la branche redo doit être purgée.
    win.inv.hosts["aa:bb:cc:dd:ee:03"] = _host("aa:bb:cc:dd:ee:03")
    win._reload_canvas()
    win._record_history()
    assert not win.act_redo.isEnabled()


# ---------------------------------------------------------------------------
# Validation IP dans les dialogues
# ---------------------------------------------------------------------------

def test_add_device_dialog_rejects_invalid_ip(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from intramap.gui.device_dialog import AddDeviceDialog
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    dlg = AddDeviceDialog(Inventory())
    dlg._mac.setText("02:00:00:00:00:01")
    dlg._ip.setText("999.1.2.3")
    dlg._accept()
    assert dlg.result_host is None


def test_add_device_dialog_accepts_valid_ip(qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from intramap.gui.device_dialog import AddDeviceDialog
    # _accept appelle self.accept() ; on neutralise pour éviter tout effet.
    monkeypatch.setattr(QDialog, "accept", lambda self: None)
    dlg = AddDeviceDialog(Inventory())
    dlg._mac.setText("02:00:00:00:00:01")
    dlg._ip.setText("192.168.1.42")
    dlg._accept()
    assert dlg.result_host is not None
    assert dlg.result_host.ip == "192.168.1.42"


def test_inspector_keeps_previous_ip_on_invalid_input(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from intramap.gui.inspector import Inspector
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: None))
    a = _host("aa:bb:cc:dd:ee:01", ip="192.168.1.10")
    inv = _inv(a)
    insp = Inspector()
    insp.set_host(a, inv)
    insp._ip.setText("nope")
    insp._apply()
    assert a.ip == "192.168.1.10"


# ---------------------------------------------------------------------------
# Diff de scan (dialogue post-scan)
# ---------------------------------------------------------------------------

def test_scan_done_shows_diff_dialog_on_changes(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from intramap.gui.main_window import MainWindow
    from intramap.models import DiscoveredHost
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    win.inv = _inv(_host("aa:bb:cc:dd:ee:01", ip="192.168.1.1"))
    win._reload_canvas()
    win._reset_history()
    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: calls.append(a)))
    win._on_scan_done([DiscoveredHost(mac="aa:bb:cc:dd:ee:09",
                                      ip="192.168.1.9", hostname=None,
                                      vendor=None)])
    assert calls, "un changement doit ouvrir le dialogue récapitulatif"
    assert "aa:bb:cc:dd:ee:09" in calls[0][2]


def test_scan_done_no_dialog_when_no_change(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from intramap.gui.main_window import MainWindow
    from intramap.models import DiscoveredHost
    win = MainWindow(inventory_path=str(tmp_path / "none.yaml"))
    win.inv = _inv(_host("aa:bb:cc:dd:ee:01", ip="192.168.1.1"))
    win._reload_canvas()
    win._reset_history()
    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: calls.append(a)))
    win._on_scan_done([DiscoveredHost(mac="aa:bb:cc:dd:ee:01",
                                      ip="192.168.1.1", hostname=None,
                                      vendor=None)])
    assert not calls


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
