"""Fenêtre principale de l'application IntraMap."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSettings, QSizeF, Qt
from PySide6.QtGui import (
    QAbstractTextDocumentLayout, QAction, QActionGroup, QFont, QKeySequence,
    QPageLayout, QPageSize, QPainter, QPdfWriter, QTextDocument,
)
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QLineEdit, QMainWindow, QMessageBox, QSplitter,
    QStyle, QWidget,
)

from intramap import inventory as inventory_mod
from intramap.wiring_report import build_wiring_report
from intramap.gui import layout as layout_mod
from intramap.gui.canvas import MapView
from intramap.gui.device_dialog import AddDeviceDialog
from intramap.gui.device_list_dialog import DeviceListDialog
from intramap.gui.diagnose_dialog import DiagnoseDialog
from intramap.gui.export_dialog import ExportPdfDialog, page_grid
from intramap.gui import i18n
from intramap.gui.i18n import tr
from intramap.gui.inspector import Inspector
from intramap.gui.link_dialog import ConnectDialog
from intramap.gui.path_report_dialog import PathReportDialog
from intramap.gui.scan_worker import ScanWorker, detect_subnets
from intramap.gui.switch_dialog import SwitchPortDialog
from intramap.models import Inventory, _resolve_device_type
from intramap.scan_diff import diff_inventories, format_scan_diff

_DEFAULT_INVENTORY = "inventory.yaml"
_RECENTS_KEY = "recent_files"
_RECENTS_MAX = 10


def _push_recent(recents: list[str], path: str,
                 cap: int = _RECENTS_MAX) -> list[str]:
    """Insère ``path`` en tête de la liste des récents (chemin absolu),
    sans doublon, plafonné à ``cap``. Fonction pure (testable sans Qt)."""
    p = str(Path(path).resolve())
    return ([p] + [x for x in recents if x != p])[:cap]


class MainWindow(QMainWindow):
    """Assemble le canvas, le panneau d'édition et les actions de l'app."""

    def __init__(self, inventory_path: str | None = None):
        super().__init__()
        self.setWindowTitle("IntraMap")
        self.resize(1180, 760)

        self.inv = Inventory()
        self.inventory_path = Path(inventory_path or _DEFAULT_INVENTORY)
        self._dirty = False
        self._scan_worker: ScanWorker | None = None
        # Nombre de ports déclaré par switch (MAC -> n), persisté dans layout.
        self._switch_ports: dict[str, int] = {}
        # Liste des inventaires récemment ouverts (chemins absolus), persistée
        # via QSettings.
        self._recents: list[str] = self._load_recents()
        # Historique undo/redo : pile d'instantanés du document.
        self._restoring = False
        self._history: list[dict] = []
        self._hist_pos = -1
        # Le tout premier auto-fit doit attendre que la fenêtre soit visible
        # (sinon le canvas est encore à sa taille par défaut et le fit est
        # calculé sur la mauvaise géométrie).
        self._pending_initial_fit = False

        # --- widgets -----------------------------------------------------
        self.canvas = MapView()
        self.inspector = Inspector()
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([860, 320])
        self.setCentralWidget(splitter)
        self.splitter = splitter

        self.canvas.node_moved.connect(self._on_node_moved)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.node_double_clicked.connect(self._on_node_double_clicked)
        self.inspector.host_changed.connect(self._on_host_changed)
        self.inspector.host_deleted.connect(self._on_host_deleted)
        self.inspector.select_requested.connect(self._on_inspector_select)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.statusBar().showMessage(tr("Prêt"))

        # --- chargement initial -----------------------------------------
        if self.inventory_path.exists():
            self._load_inventory(self.inventory_path)
        else:
            self._refresh_title()
            self._reset_history()

    # -- actions & menus ---------------------------------------------------
    def _icon(self, sp: QStyle.StandardPixmap):
        return self.style().standardIcon(sp)

    def _build_actions(self) -> None:
        st = QStyle
        self.act_new = QAction(self._icon(st.SP_FileIcon),
                               tr("Nouveau"), self)
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.triggered.connect(self._new_inventory)

        self.act_open = QAction(self._icon(st.SP_DialogOpenButton),
                                tr("Ouvrir un inventaire…"), self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self._open_inventory)

        self.act_close = QAction(tr("Fermer l'inventaire"), self)
        self.act_close.setShortcut("Ctrl+W")
        self.act_close.triggered.connect(self._close_inventory)

        self.act_save = QAction(self._icon(st.SP_DialogSaveButton),
                                tr("Enregistrer"), self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self._save)

        self.act_save_as = QAction(tr("Enregistrer sous…"), self)
        self.act_save_as.setShortcut(QKeySequence.SaveAs)
        self.act_save_as.triggered.connect(self._save_as)

        self.act_export = QAction(self._icon(st.SP_FileIcon),
                                  tr("Exporter en PDF…"), self)
        self.act_export.setShortcut("Ctrl+E")
        self.act_export.triggered.connect(self._export_pdf)

        self.act_undo = QAction(self._icon(st.SP_ArrowBack), tr("Annuler"),
                                self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setEnabled(False)
        self.act_undo.triggered.connect(self._undo)

        self.act_redo = QAction(self._icon(st.SP_ArrowForward), tr("Rétablir"),
                                self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.setEnabled(False)
        self.act_redo.triggered.connect(self._redo)

        self.act_scan = QAction(self._icon(st.SP_BrowserReload),
                                tr("Scanner le réseau"), self)
        self.act_scan.setShortcut("Ctrl+R")
        self.act_scan.triggered.connect(self._scan)

        self.act_add = QAction(self._icon(st.SP_FileDialogNewFolder),
                               tr("Ajouter un device"), self)
        # Ctrl+N est réservé à « Nouveau » (convention) ; l'ajout d'appareil
        # passe sur Ctrl+Shift+N.
        self.act_add.setShortcut("Ctrl+Shift+N")
        self.act_add.triggered.connect(self._add_device)

        self.act_connect = QAction(self._icon(st.SP_FileLinkIcon),
                                   tr("Relier deux appareils…"), self)
        self.act_connect.setShortcut("Ctrl+L")
        self.act_connect.triggered.connect(self._connect_devices)

        self.act_delete = QAction(tr("Supprimer le device sélectionné"), self)
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.triggered.connect(self._delete_selected)

        self.act_fit = QAction(self._icon(st.SP_FileDialogContentsView),
                               tr("Ajuster à la fenêtre"), self)
        self.act_fit.setShortcut("Ctrl+0")
        self.act_fit.triggered.connect(self.canvas.fit_all)

        self.act_zoom_in = QAction(self._icon(st.SP_ArrowUp),
                                   tr("Zoom avant"), self)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(self.canvas.zoom_in)

        self.act_zoom_out = QAction(self._icon(st.SP_ArrowDown),
                                    tr("Zoom arrière"), self)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(self.canvas.zoom_out)

        self.act_toggle_inspector = QAction(tr("Panneau latéral"), self,
                                            checkable=True)
        self.act_toggle_inspector.setChecked(True)
        self.act_toggle_inspector.setShortcut("Ctrl+I")
        self.act_toggle_inspector.setToolTip(
            tr("Masquer / réafficher le panneau d'édition à droite"))
        self.act_toggle_inspector.toggled.connect(self.inspector.setVisible)

        self.act_relayout = QAction(tr("Réorganiser automatiquement"), self)
        self.act_relayout.triggered.connect(self._relayout)

        self.act_device_list = QAction(tr("Liste des devices (MAC / IP)…"),
                                       self)
        self.act_device_list.triggered.connect(self._show_device_list)

        self.act_path_report = QAction(tr("Rapport des chemins réseau…"), self)
        self.act_path_report.triggered.connect(self._show_path_report)

        self.act_diagnose = QAction(tr("Diagnostics réseau…"), self)
        self.act_diagnose.triggered.connect(self._show_diagnostics)

        # Style de routage des liaisons (exclusif).
        self.routing_group = QActionGroup(self)
        self.routing_group.setExclusive(True)
        self.routing_actions: dict[str, QAction] = {}
        for style, label in (
            ("ortho_h", tr("Angles droits — horizontal d'abord")),
            ("ortho_v", tr("Angles droits — vertical d'abord")),
            ("straight", tr("Lignes droites")),
        ):
            act = QAction(label, self, checkable=True)
            act.triggered.connect(
                lambda _checked, s=style: self._set_routing(s))
            self.routing_group.addAction(act)
            self.routing_actions[style] = act
        self.routing_actions["ortho_h"].setChecked(True)

        self.act_reset_bends = QAction(tr("Réinitialiser les coudes"), self)
        self.act_reset_bends.triggered.connect(self._reset_bends)

        self.act_quit = QAction(tr("Quitter"), self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.triggered.connect(self.close)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu(tr("&Fichier"))
        m_file.addAction(self.act_new)
        m_file.addAction(self.act_open)
        self.menu_recent = m_file.addMenu(tr("Récemment ouverts"))
        m_file.addAction(self.act_close)
        m_file.addSeparator()
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addSeparator()
        m_file.addAction(self.act_export)
        m_file.addSeparator()
        m_file.addAction(self.act_quit)
        self._rebuild_recent_menu()

        m_edit = mb.addMenu(tr("&Édition"))
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)
        m_edit.addSeparator()
        m_edit.addAction(self.act_scan)
        m_edit.addAction(self.act_add)
        m_edit.addAction(self.act_connect)
        m_edit.addAction(self.act_delete)

        m_view = mb.addMenu(tr("&Affichage"))
        m_view.addAction(self.act_fit)
        m_view.addAction(self.act_zoom_in)
        m_view.addAction(self.act_zoom_out)
        m_view.addAction(self.act_toggle_inspector)
        m_view.addSeparator()
        m_routing = m_view.addMenu(tr("Style des liaisons"))
        for style in ("ortho_h", "ortho_v", "straight"):
            m_routing.addAction(self.routing_actions[style])
        m_view.addAction(self.act_reset_bends)
        m_view.addSeparator()
        m_view.addAction(self.act_relayout)
        m_view.addSeparator()
        m_view.addAction(self.act_device_list)
        m_view.addAction(self.act_path_report)
        m_view.addAction(self.act_diagnose)
        m_view.addSeparator()
        m_lang = m_view.addMenu(tr("Langue"))
        self.lang_group = QActionGroup(self)
        self.lang_group.setExclusive(True)
        saved_lang = i18n.load_saved_language()
        for code, label in i18n.available_languages():
            act = QAction(label, self, checkable=True)
            act.setChecked(code == saved_lang)
            act.triggered.connect(lambda _c=False, lc=code: self._set_language(lc))
            self.lang_group.addAction(act)
            m_lang.addAction(act)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar(tr("Principale"))
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        tb.addAction(self.act_scan)
        tb.addAction(self.act_add)
        tb.addAction(self.act_connect)
        tb.addSeparator()
        tb.addAction(self.act_save)
        tb.addAction(self.act_export)
        tb.addSeparator()
        tb.addAction(self.act_zoom_out)
        tb.addAction(self.act_fit)
        tb.addAction(self.act_zoom_in)
        tb.addAction(self.act_toggle_inspector)
        tb.addSeparator()
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("Rechercher (nom, IP, type, étage…)"))
        self._search.setClearButtonEnabled(True)
        self._search.setFixedWidth(240)
        self._search.textChanged.connect(self._on_search)
        self._search.returnPressed.connect(self._on_search_enter)
        tb.addWidget(self._search)

    # -- état / titre ------------------------------------------------------
    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._refresh_title()

    def _refresh_title(self) -> None:
        star = "*" if self._dirty else ""
        self.setWindowTitle(f"IntraMap — {self.inventory_path.name}{star}")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Premier affichage : on déclenche l'auto-fit différé éventuellement
        # demandé pendant le chargement initial (cf. __init__).
        if self._pending_initial_fit:
            self._pending_initial_fit = False
            # QTimer.singleShot(0, ...) attendrait l'événement suivant, mais
            # un appel direct ici suffit : à ce stade, le widget a sa taille
            # finale via le splitter.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.canvas.fit_all)

    # -- chargement / sauvegarde ------------------------------------------
    def _load_inventory(self, path: Path) -> None:
        try:
            inv = inventory_mod.load(path)
        except Exception as e:
            QMessageBox.critical(
                self, tr("Inventaire illisible"),
                tr("Impossible de charger {path} :\n{err}").format(
                    path=path, err=e))
            return
        self.inv = inv
        self.inventory_path = path
        # La mise en page vit dans la section `layout` de l'inventaire ;
        # repli sur l'ancien fichier compagnon .layout.json (migration).
        layout_dict = inventory_mod.load_layout_dict(path)
        if not layout_dict:
            layout_dict = layout_mod.read_legacy_sidecar(path)
        data = layout_mod.layout_from_dict(layout_dict)
        self._switch_ports = dict(data.switch_ports)
        positions = layout_mod.positions_for(inv, data.positions)
        self.canvas.load(inv, positions, data.edge_bends, data.routing_style)
        self._sync_routing_menu()
        # Si la fenêtre n'est pas encore visible (chargement initial pendant
        # __init__), on diffère le fit au premier showEvent : sinon la
        # géométrie du canvas n'est pas encore stabilisée.
        if self.isVisible():
            self.canvas.fit_all()
        else:
            self._pending_initial_fit = True
        self.inspector.set_host(None, inv)
        self._set_dirty(False)
        self._reset_history()
        self._note_recent(path)
        self.statusBar().showMessage(
            tr("{n} device(s) chargé(s) depuis {name}").format(
                n=len(inv.hosts), name=path.name))

    def _reload_canvas(self) -> None:
        """Reconstruit le canvas en conservant positions, coudes et style."""
        positions = layout_mod.positions_for(
            self.inv, self.canvas.current_positions())
        self.canvas.load(self.inv, positions,
                         self.canvas.current_edge_bends(),
                         self.canvas.routing_style)

    def _open_inventory(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Ouvrir un inventaire"), str(self.inventory_path.parent),
            tr("Inventaire YAML (*.yaml *.yml);;Tous les fichiers (*)"))
        if path:
            self._load_inventory(Path(path))

    # -- nouveau / fermer --------------------------------------------------
    def _reset_to_empty(self) -> None:
        """Repart d'un inventaire vide « sans titre » (chemin par défaut)."""
        self.inv = Inventory()
        self.inventory_path = Path(_DEFAULT_INVENTORY)
        self._switch_ports = {}
        positions = layout_mod.positions_for(self.inv, {})
        self.canvas.load(self.inv, positions, {}, self.canvas.routing_style)
        self.inspector.set_host(None, self.inv)
        self._set_dirty(False)
        self._reset_history()

    def _new_inventory(self) -> None:
        if not self._confirm_discard():
            return
        self._reset_to_empty()
        self.statusBar().showMessage(tr("Nouvel inventaire"))

    def _close_inventory(self) -> None:
        if not self._confirm_discard():
            return
        self._reset_to_empty()
        self.statusBar().showMessage(tr("Inventaire fermé"))

    # -- récemment ouverts -------------------------------------------------
    @staticmethod
    def _settings() -> QSettings:
        return QSettings("Foxugly", "IntraMap")

    def _load_recents(self) -> list[str]:
        raw = self._settings().value(_RECENTS_KEY, [])
        if isinstance(raw, str):  # QSettings peut renvoyer un str si 1 entrée
            raw = [raw]
        return [str(x) for x in (raw or [])]

    def _persist_recents(self) -> None:
        self._settings().setValue(_RECENTS_KEY, self._recents)

    def _note_recent(self, path) -> None:
        self._recents = _push_recent(self._recents, str(path))
        self._persist_recents()
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        self.menu_recent.clear()
        existing = [p for p in self._recents if Path(p).exists()]
        if not existing:
            act = self.menu_recent.addAction(tr("(aucun)"))
            act.setEnabled(False)
            return
        for p in existing:
            act = self.menu_recent.addAction(Path(p).name)
            act.setToolTip(p)
            act.triggered.connect(
                lambda _checked=False, path=p: self._open_recent(path))
        self.menu_recent.addSeparator()
        clear = self.menu_recent.addAction(tr("Vider la liste"))
        clear.triggered.connect(self._clear_recents)

    def _open_recent(self, path: str) -> None:
        if not self._confirm_discard():
            return
        self._load_inventory(Path(path))

    def _clear_recents(self) -> None:
        self._recents = []
        self._persist_recents()
        self._rebuild_recent_menu()

    # -- historique undo / redo -------------------------------------------
    _HISTORY_MAX = 50

    def _capture_state(self) -> dict:
        """Instantané complet du document : inventaire + mise en page."""
        layout = layout_mod.LayoutData(
            positions=self.canvas.current_positions(),
            edge_bends=self.canvas.current_edge_bends(),
            routing_style=self.canvas.routing_style,
            switch_ports=self._switch_ports)
        return {"doc": self.inv.to_dict(),
                "layout": layout_mod.layout_to_dict(layout)}

    def _restore_state(self, state: dict) -> None:
        self._restoring = True
        try:
            self.inv = Inventory.from_dict(state["doc"])
            data = layout_mod.layout_from_dict(state["layout"])
            self._switch_ports = dict(data.switch_ports)
            positions = layout_mod.positions_for(self.inv, data.positions)
            self.canvas.load(self.inv, positions, data.edge_bends,
                             data.routing_style)
            self._sync_routing_menu()
            self.inspector.set_host(None, self.inv)
            self._set_dirty(True)
        finally:
            self._restoring = False

    def _reset_history(self) -> None:
        self._history = [self._capture_state()]
        self._hist_pos = 0
        self._update_undo_actions()

    def _record_history(self) -> None:
        if self._restoring:
            return
        del self._history[self._hist_pos + 1:]
        self._history.append(self._capture_state())
        if len(self._history) > self._HISTORY_MAX:
            self._history.pop(0)
        self._hist_pos = len(self._history) - 1
        self._update_undo_actions()

    def _undo(self) -> None:
        if self._hist_pos <= 0:
            return
        self._hist_pos -= 1
        self._restore_state(self._history[self._hist_pos])
        self._update_undo_actions()
        self.statusBar().showMessage(tr("Annulé"))

    def _redo(self) -> None:
        if self._hist_pos >= len(self._history) - 1:
            return
        self._hist_pos += 1
        self._restore_state(self._history[self._hist_pos])
        self._update_undo_actions()
        self.statusBar().showMessage(tr("Rétabli"))

    def _update_undo_actions(self) -> None:
        self.act_undo.setEnabled(self._hist_pos > 0)
        self.act_redo.setEnabled(self._hist_pos < len(self._history) - 1)

    def _save(self) -> bool:
        try:
            layout = layout_mod.LayoutData(
                positions=self.canvas.current_positions(),
                edge_bends=self.canvas.current_edge_bends(),
                routing_style=self.canvas.routing_style,
                switch_ports=self._switch_ports)
            inventory_mod.save(self.inv, self.inventory_path,
                               layout=layout_mod.layout_to_dict(layout))
        except Exception as e:
            QMessageBox.critical(
                self, tr("Échec de l'enregistrement"),
                tr("Impossible d'écrire {path} :\n{err}").format(
                    path=self.inventory_path, err=e))
            return False
        self._set_dirty(False)
        self.statusBar().showMessage(
            tr("Enregistré : {name}").format(name=self.inventory_path.name))
        return True

    def _save_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Enregistrer l'inventaire sous"),
            str(self.inventory_path), tr("Inventaire YAML (*.yaml)"))
        if not path:
            return False
        self.inventory_path = Path(path)
        self._refresh_title()
        ok = self._save()
        if ok:
            self._note_recent(self.inventory_path)
        return ok

    # -- export PDF --------------------------------------------------------
    def _export_pdf(self) -> None:
        if not self.canvas.nodes:
            QMessageBox.information(
                self, tr("Rien à exporter"),
                tr("La carte est vide. Scannez le réseau ou ajoutez un "
                   "device."))
            return

        scene = self.canvas.scene()
        source = scene.itemsBoundingRect().adjusted(-40, -40, 40, 40)

        dlg = ExportPdfDialog(source.width(), source.height(), self)
        if dlg.exec() != ExportPdfDialog.Accepted:
            return
        page_size_id, pages_wide, include_wiring = dlg.selection()

        default = str(self.inventory_path.with_suffix(".pdf"))
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Exporter la carte en PDF"), default,
            tr("Document PDF (*.pdf)"))
        if not path:
            return

        # On retire sélection et poignées pour un rendu propre.
        previously = self.canvas.selected_mac()
        scene.clearSelection()
        self.canvas.set_handles_visible(False)
        try:
            cols, rows = self._render_pdf_document(
                path, source, page_size_id, pages_wide,
                include_wiring=include_wiring)
        except Exception as e:
            QMessageBox.critical(
                self, tr("Échec de l'export"),
                tr("Impossible d'écrire le PDF :\n{err}").format(err=e))
            return
        finally:
            self.canvas.set_handles_visible(True)
            if previously:
                self.canvas.select_mac(previously)

        n = cols * rows
        self.statusBar().showMessage(
            tr("PDF exporté : {name} ({n} page(s))").format(
                name=Path(path).name, n=n))

    def _render_pdf_document(self, path: str, source: QRectF,
                             page_size_id, pages_wide: int,
                             include_wiring: bool = False) -> tuple[int, int]:
        """Écrit le PDF ; retourne (colonnes, lignes) de la mosaïque carte.

        Une seule page : la carte entière est ajustée en conservant les
        proportions. Mosaïque : la carte est agrandie puis découpée en
        tuiles, chaque tuile remplissant une page — proportions conservées,
        qualité maximale.

        Si ``include_wiring`` est vrai, des pages texte sont ajoutées après
        la carte avec le détail des branchements des appareils
        d'infrastructure (routeurs, switchs, patch panels, outlets).
        """
        W, H = source.width(), source.height()
        cols, rows, landscape = page_grid(W, H, page_size_id, pages_wide)

        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(page_size_id))
        writer.setPageOrientation(
            QPageLayout.Landscape if landscape else QPageLayout.Portrait)
        writer.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Millimeter)
        writer.setTitle(f"IntraMap — {self.inventory_path.stem}")

        painter = QPainter(writer)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            vp = painter.viewport()
            pw, ph = vp.width(), vp.height()
            page_target = QRectF(0, 0, pw, ph)
            scene = self.canvas.scene()

            if cols <= 1 and rows <= 1:
                scene.render(painter, page_target, source, Qt.KeepAspectRatio)
            else:
                k = W / (cols * pw)  # unités de scène par pixel device
                first = True
                for r in range(rows):
                    for c in range(cols):
                        if not first:
                            writer.newPage()
                        first = False
                        sub = QRectF(source.x() + c * pw * k,
                                     source.y() + r * ph * k,
                                     pw * k, ph * k)
                        scene.render(painter, page_target, sub,
                                     Qt.KeepAspectRatio)

            # Le rapport des branchements est rendu DANS LA MÊME session de
            # painter que la carte : si on faisait painter.end() puis un
            # nouveau painter, le QPdfWriter finaliserait le PDF et la
            # seconde session écraserait le fichier au lieu de l'étendre.
            if include_wiring:
                self._render_wiring_pages(writer, painter)
        finally:
            painter.end()
        return cols, rows

    def _render_wiring_pages(self, writer: QPdfWriter,
                             painter: QPainter) -> None:
        """Ajoute au PDF les pages texte du rapport des branchements, sur
        la session de painter déjà active (la même que pour la carte).

        Le piège DPI : par défaut QTextDocument fait son layout à 96 DPI,
        alors qu'un QPdfWriter rend à 1200 DPI. ``setPaintDevice(writer)``
        propage la vraie résolution au layout, de sorte qu'un 12 pt sort
        bien comme du 12 pt sur le papier.
        """
        text = build_wiring_report(self.inv)
        if not text.strip():
            return

        doc = QTextDocument()
        # Indispensable AVANT setHtml/setPageSize : oriente la conversion
        # pt → pixels device selon la résolution réelle du writer.
        doc.documentLayout().setPaintDevice(writer)

        font = QFont("Sans Serif")
        font.setPointSizeF(12)
        doc.setDefaultFont(font)
        doc.setDefaultStyleSheet(
            "h1 { font-size:18pt; font-weight:600; margin-bottom:12px; }"
            "h2 { font-size:14pt; font-weight:600;"
            "     margin-top:16px; margin-bottom:6px;"
            "     border-bottom:1px solid #888; padding-bottom:2px; }"
            "p  { margin:0; padding:0; }"
            "pre { font-family:monospace; font-size:12pt;"
            "      white-space:pre; margin:0; }"
        )
        doc.setHtml(self._wiring_text_to_html(text))

        # Taille de page utile : viewport moins marges (15 mm de chaque côté
        # converti en pixels device via le DPI du writer).
        vp = painter.viewport()
        pw, ph = float(vp.width()), float(vp.height())
        margin_x = writer.logicalDpiX() * 15.0 / 25.4
        margin_y = writer.logicalDpiY() * 15.0 / 25.4
        content_w = pw - 2 * margin_x
        content_h = ph - 2 * margin_y
        doc.setPageSize(QSizeF(content_w, content_h))

        n_pages = max(1, doc.pageCount())
        layout = doc.documentLayout()
        for p in range(n_pages):
            writer.newPage()
            painter.save()
            painter.translate(margin_x, margin_y - p * content_h)
            ctx = QAbstractTextDocumentLayout.PaintContext()
            ctx.clip = QRectF(0, p * content_h, content_w, content_h)
            layout.draw(painter, ctx)
            painter.restore()

    @staticmethod
    def _wiring_text_to_html(text: str) -> str:
        """Convertit le rapport plat en HTML simple pour QTextDocument.

        - Lignes ``## Titre`` -> ``<h2>``
        - Première ligne (titre) -> ``<h1>``
        - Autres lignes -> bloc ``<pre>`` pour conserver l'indentation.
        """
        from html import escape
        lines = text.splitlines()
        out: list[str] = []
        first = True
        buf: list[str] = []

        def flush() -> None:
            if buf:
                out.append("<pre>" + escape("\n".join(buf)) + "</pre>")
                buf.clear()

        for line in lines:
            if first and line.strip():
                flush()
                out.append(f"<h1>{escape(line)}</h1>")
                first = False
                continue
            if line.startswith("=="):
                # Soulignement ASCII du titre : on l'ignore (déjà h1).
                continue
            if line.startswith("## "):
                flush()
                out.append(f"<h2>{escape(line[3:])}</h2>")
            else:
                buf.append(line)
        flush()
        return "\n".join(out)

    # -- scan --------------------------------------------------------------
    def _scan(self) -> None:
        if self._scan_worker is not None:
            return  # un scan est déjà en cours
        subnets = detect_subnets()
        if not subnets:
            network, ok = QInputDialog.getText(
                self, tr("Scanner le réseau"),
                tr("Aucun sous-réseau détecté. Saisissez un CIDR :"),
                text="192.168.1.0/24")
        elif len(subnets) == 1:
            network, ok = QInputDialog.getText(
                self, tr("Scanner le réseau"), tr("Sous-réseau à scanner :"),
                text=subnets[0])
        else:
            network, ok = QInputDialog.getItem(
                self, tr("Scanner le réseau"),
                tr("Plusieurs sous-réseaux détectés :"), subnets, 0, True)
        if not ok or not network.strip():
            return

        self.act_scan.setEnabled(False)
        self.statusBar().showMessage(
            tr("Scan de {network} en cours…").format(network=network))
        worker = ScanWorker(network.strip(), self)
        worker.succeeded.connect(self._on_scan_done)
        worker.failed.connect(self._on_scan_failed)
        worker.finished.connect(self._on_scan_finished)
        # Laisser Qt libérer le thread après traitement de `finished` (évite la
        # course liée au déréférencement synchrone du QThread dans le slot).
        worker.finished.connect(worker.deleteLater)
        self._scan_worker = worker
        worker.start()

    def _on_scan_done(self, discovered: list) -> None:
        before = Inventory.from_dict(self.inv.to_dict())  # copie pour le diff
        inventory_mod.merge(self.inv, discovered, now=datetime.now())
        diff = diff_inventories(before, self.inv)
        self._reload_canvas()
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(
            tr("Scan terminé : {n} device(s) détecté(s), {new} nouveau(x).")
            .format(n=len(discovered), new=len(diff.appeared)))
        if diff.has_changes:
            QMessageBox.information(
                self, tr("Changements du scan"),
                format_scan_diff(diff, self.inv))

    def _on_scan_failed(self, message: str) -> None:
        QMessageBox.warning(self, tr("Échec du scan"), message)
        self.statusBar().showMessage(tr("Scan échoué"))

    def _on_scan_finished(self) -> None:
        self.act_scan.setEnabled(True)
        self._scan_worker = None

    # -- édition -----------------------------------------------------------
    def _add_device(self) -> None:
        dlg = AddDeviceDialog(self.inv, self)
        if dlg.exec() != AddDeviceDialog.Accepted or dlg.result_host is None:
            return
        host = dlg.result_host
        self.inv.hosts[host.mac] = host
        self._reload_canvas()
        self.canvas.select_mac(host.mac)
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(
            tr("Device ajouté : {name}").format(
                name=host.custom_name or host.mac))

    def _connect_devices(self) -> None:
        """Ouvre l'écran « Relier » pour créer plusieurs liaisons d'un coup.

        Si deux appareils sont sélectionnés sur la carte, ils pré-remplissent
        la source et la destination.
        """
        if len(self.inv.hosts) < 2:
            QMessageBox.information(
                self, tr("Pas assez d'appareils"),
                tr("Il faut au moins deux appareils sur la carte pour créer "
                   "une liaison."))
            return
        sel = self.canvas.selected_macs()
        source = sel[0] if len(sel) >= 1 else None
        dest = sel[1] if len(sel) >= 2 else None
        dlg = ConnectDialog(self.inv, source, dest, self)
        if dlg.exec() != ConnectDialog.Accepted or not dlg.new_links:
            return
        # add_link deduplique : relier deux appareils deja relies sur les memes
        # ports ne cree pas de cable fantome.
        for lk in dlg.new_links:
            self.inv.add_link(lk)
        first = dlg.new_links[0]
        a_host = self.inv.hosts.get(first.mac_a)
        self._reload_canvas()
        if a_host is not None:
            self.canvas.select_mac(a_host.mac)
            self.inspector.set_host(a_host, self.inv)
        self._set_dirty(True)
        self._record_history()
        b_host = self.inv.hosts.get(first.mac_b)
        peer_name = (b_host.custom_name or b_host.mac) if b_host else first.mac_b
        n = len(dlg.new_links)
        self.statusBar().showMessage(
            tr("{n} liaison(s) créée(s) avec {peer}").format(
                n=n, peer=peer_name))

    def _delete_selected(self) -> None:
        mac = self.canvas.selected_mac()
        if mac is None:
            self.statusBar().showMessage(tr("Aucun device sélectionné"))
            return
        host = self.inv.hosts.get(mac)
        if host is None:
            return
        # On supprime bien l'appareil sélectionné sur la carte : l'inspecteur
        # peut afficher un autre appareil (suite à un « ↗ » vers un pair).
        if self.inspector._host is not host:
            self.inspector.set_host(host, self.inv)
        self.inspector._delete()

    def _on_host_changed(self, mac: str) -> None:
        self._reload_canvas()
        self.canvas.select_mac(mac)
        self.inspector.refresh_title()
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(tr("Modifications appliquées"))

    def _on_host_deleted(self, mac: str) -> None:
        self.inv.hosts.pop(mac, None)
        self._switch_ports.pop(mac, None)
        self.inv.links = [lk for lk in self.inv.links if not lk.touches(mac)]
        for host in self.inv.hosts.values():
            if host.wifi_ap_mac == mac:
                host.wifi_ap_mac = None
        self._reload_canvas()
        self.inspector.set_host(None, self.inv)
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(tr("Device supprimé"))

    def _relayout(self) -> None:
        positions = layout_mod.auto_layout(self.inv)
        self.canvas.load(self.inv, positions,
                         self.canvas.current_edge_bends(),
                         self.canvas.routing_style)
        self.canvas.fit_all()
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(
            tr("Carte réorganisée par étage et pièce"))

    def _set_routing(self, style: str) -> None:
        self.canvas.set_routing_style(style)
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(tr("Style de liaison appliqué"))

    def _sync_routing_menu(self) -> None:
        act = self.routing_actions.get(self.canvas.routing_style)
        if act is not None:
            act.setChecked(True)

    def _reset_bends(self) -> None:
        self.canvas.reset_all_bends()
        self._set_dirty(True)
        self._record_history()
        self.statusBar().showMessage(tr("Coudes des liaisons réinitialisés"))

    def _set_language(self, code: str) -> None:
        i18n.save_language(code)
        i18n.set_language(
            i18n.resolve_system_language() if code == "system" else code)
        self._retranslate()
        self.statusBar().showMessage(tr("Langue appliquée"))

    def _retranslate(self) -> None:
        """Ré-applique la langue courante à l'UI persistante, sans redémarrer.

        Les dialogues sont recréés à chaque ouverture : ils suivent déjà la
        langue. On retraduit ici les actions, la barre de menus, l'inspecteur
        (libellés figés à la construction) et les tooltips du canvas.
        """
        self.act_new.setText(tr("Nouveau"))
        self.act_open.setText(tr("Ouvrir un inventaire…"))
        self.act_close.setText(tr("Fermer l'inventaire"))
        self.act_save.setText(tr("Enregistrer"))
        self.act_save_as.setText(tr("Enregistrer sous…"))
        self.act_export.setText(tr("Exporter en PDF…"))
        self.act_undo.setText(tr("Annuler"))
        self.act_redo.setText(tr("Rétablir"))
        self.act_scan.setText(tr("Scanner le réseau"))
        self.act_add.setText(tr("Ajouter un device"))
        self.act_connect.setText(tr("Relier deux appareils…"))
        self.act_delete.setText(tr("Supprimer le device sélectionné"))
        self.act_fit.setText(tr("Ajuster à la fenêtre"))
        self.act_zoom_in.setText(tr("Zoom avant"))
        self.act_zoom_out.setText(tr("Zoom arrière"))
        self.act_toggle_inspector.setText(tr("Panneau latéral"))
        self.act_toggle_inspector.setToolTip(
            tr("Masquer / réafficher le panneau d'édition à droite"))
        self.act_relayout.setText(tr("Réorganiser automatiquement"))
        self.act_device_list.setText(tr("Liste des devices (MAC / IP)…"))
        self.act_path_report.setText(tr("Rapport des chemins réseau…"))
        self.act_diagnose.setText(tr("Diagnostics réseau…"))
        self.act_reset_bends.setText(tr("Réinitialiser les coudes"))
        self.act_quit.setText(tr("Quitter"))
        for style, label in (
            ("ortho_h", tr("Angles droits — horizontal d'abord")),
            ("ortho_v", tr("Angles droits — vertical d'abord")),
            ("straight", tr("Lignes droites")),
        ):
            self.routing_actions[style].setText(label)
        self._search.setPlaceholderText(tr("Rechercher (nom, IP, type, étage…)"))

        self.menuBar().clear()
        self._build_menus()
        self._replace_inspector()
        self._reload_canvas()

    def _replace_inspector(self) -> None:
        """Recrée l'inspecteur (ses libellés sont figés) dans la langue
        courante, en conservant la sélection affichée."""
        mac = self.canvas.selected_mac()
        idx = self.splitter.indexOf(self.inspector)
        old = self.inspector
        self.inspector = Inspector()
        self.splitter.replaceWidget(idx, self.inspector)
        old.deleteLater()
        self.inspector.host_changed.connect(self._on_host_changed)
        self.inspector.host_deleted.connect(self._on_host_deleted)
        self.inspector.select_requested.connect(self._on_inspector_select)
        self.act_toggle_inspector.toggled.connect(self.inspector.setVisible)
        self.inspector.setVisible(self.act_toggle_inspector.isChecked())
        host = self.inv.hosts.get(mac) if mac else None
        self.inspector.set_host(host, self.inv)

    def _show_device_list(self) -> None:
        DeviceListDialog(self.inv, self).exec()

    def _show_path_report(self) -> None:
        """Ouvre le rapport traceroute."""
        PathReportDialog(self.inv, self).exec()

    def _show_diagnostics(self) -> None:
        """Ouvre le rapport de diagnostics ; un double-clic sur une anomalie
        sélectionne l'appareil concerné sur la carte."""
        dlg = DiagnoseDialog(self.inv, self)
        dlg.exec()
        mac = dlg.selected_mac
        if mac and mac in self.inv.hosts:
            self.canvas.select_mac(mac)
            self.inspector.set_host(self.inv.hosts[mac], self.inv)

    def _on_search(self, text: str) -> None:
        n = self.canvas.filter_nodes(text)
        if text.strip():
            self.statusBar().showMessage(
                tr("{n} appareil(s) correspondant(s)").format(n=n))

    def _on_search_enter(self) -> None:
        self.canvas.center_on_first_match(self._search.text())

    def _on_node_moved(self) -> None:
        self._set_dirty(True)

    def _on_selection_changed(self, mac: str) -> None:
        self.inspector.set_host(self.inv.hosts.get(mac) if mac else None,
                                self.inv)

    def _on_inspector_select(self, mac: str) -> None:
        if mac in self.inv.hosts:
            self.canvas.select_mac(mac)
            self.inspector.set_host(self.inv.hosts[mac], self.inv)

    def _on_node_double_clicked(self, mac: str) -> None:
        host = self.inv.hosts.get(mac)
        if host is None:
            return
        if _resolve_device_type(host) not in ("switch", "outlet", "patchpanel"):
            self.statusBar().showMessage(
                tr("Double-clic : gestion des ports réservée aux switches, "
                   "prises murales et patch panels"))
            return
        dlg = SwitchPortDialog(host, self.inv,
                               self._switch_ports.get(mac), self)
        if dlg.exec() == SwitchPortDialog.Accepted:
            self._switch_ports[mac] = dlg.port_count
            self._set_dirty(True)
            self._record_history()
            self.statusBar().showMessage(
                tr("{name} : {count} ports déclarés").format(
                    name=host.custom_name or mac, count=dlg.port_count))

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        choice = QMessageBox.question(
            self, tr("Modifications non enregistrées"),
            tr("Enregistrer les modifications avant de continuer ?"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if choice == QMessageBox.Save:
            return self._save()
        return choice == QMessageBox.Discard

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            # Attendre la fin d'un scan en cours avant de fermer, sinon le
            # QThread serait détruit alors qu'il tourne encore.
            if self._scan_worker is not None:
                self._scan_worker.wait()
            event.accept()
        else:
            event.ignore()
