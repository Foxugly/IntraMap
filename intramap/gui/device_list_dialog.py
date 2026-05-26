"""Dialogue : liste de tous les devices, avec filtre multi-types et export CSV."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QMenu, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout, QWidgetAction,
)

from intramap.models import Inventory, _resolve_device_type

# Ordre des colonnes : Type est désormais la 2e colonne.
_HEADERS = ["Nom", "Type", "Adresse MAC", "IP"]
_COL_NAME, _COL_TYPE, _COL_MAC, _COL_IP = 0, 1, 2, 3


def _row_values(host) -> tuple[str, str, str, str]:
    """Valeurs des cellules dans l'ordre des colonnes (Nom, Type, MAC, IP)."""
    name = host.custom_name or host.hostname or ""
    return name, _resolve_device_type(host), host.mac, (host.ip or "")


def _ip_sort_key(ip: str) -> tuple:
    """Clé de tri d'une adresse IPv4 : tuple d'entiers (1.10.x trié comme un
    humain s'y attend, pas en lexico). Les non-IP partent à la fin.
    """
    if not ip:
        return (1, ())  # vides en dernier
    parts = ip.split(".")
    try:
        nums = tuple(int(p) for p in parts)
        if len(nums) != 4 or any(n < 0 or n > 255 for n in nums):
            raise ValueError
        return (0, nums)
    except ValueError:
        return (1, (ip,))  # tout ce qui n'est pas une IPv4 valide après


class _DeviceItem(QTableWidgetItem):
    """Item de tableau qui trie selon une clé stockée (et pas le texte brut).

    Permet d'avoir un texte affichable lisible (« — » pour vide, IP avec
    point-séparateur) tout en triant intelligemment côté IP.
    """

    def __init__(self, text: str, sort_key) -> None:
        super().__init__(text)
        self._sort_key = sort_key

    def __lt__(self, other) -> bool:  # type: ignore[override]
        if isinstance(other, _DeviceItem):
            return self._sort_key < other._sort_key
        return super().__lt__(other)


class DeviceListDialog(QDialog):
    """Tableau en lecture seule des devices, filtrable par type (multi) et
    exportable en CSV.
    """

    def __init__(self, inv: Inventory, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Liste des devices — Type / MAC / IP")
        self.resize(720, 520)

        self._hosts_all = sorted(
            inv.hosts.values(),
            key=lambda h: ((h.custom_name or h.hostname or h.mac).lower(),
                           h.mac))

        # Types présents dans l'inventaire (triés). Le filtre multi-cases
        # n'expose que ce qui existe — pas tout DEVICE_TYPES.
        self._present_types: list[str] = sorted(
            {_resolve_device_type(h) for h in self._hosts_all})
        # Toutes les cases cochées par défaut = aucun filtrage.
        self._checked: set[str] = set(self._present_types)

        layout = QVBoxLayout(self)

        # --- Barre de filtre -------------------------------------------------
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Types affichés :"))

        self._filter_btn = QToolButton()
        self._filter_btn.setPopupMode(QToolButton.InstantPopup)
        self._filter_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._build_filter_menu()
        filter_row.addWidget(self._filter_btn)

        filter_row.addStretch(1)
        self._count_label = QLabel("")
        filter_row.addWidget(self._count_label)
        layout.addLayout(filter_row)

        # --- Tableau ---------------------------------------------------------
        self._table = QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        # Tri : clic sur l'en-tête bascule asc/desc, indicateur flèche visible.
        self._table.setSortingEnabled(True)
        header = self._table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(_COL_NAME, Qt.AscendingOrder)
        # Nom prend la place restante ; les autres s'adaptent au contenu.
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

        # --- Boutons bas -----------------------------------------------------
        buttons = QHBoxLayout()
        export_btn = QPushButton("Exporter en CSV…")
        export_btn.clicked.connect(self._export_csv)
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(export_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        # État courant filtré + premier remplissage.
        self._hosts: list = list(self._hosts_all)
        self._refresh()

    # ------------------------------------------------------------------ #
    # Menu déroulant de filtres : une case par type présent.
    # ------------------------------------------------------------------ #
    def _build_filter_menu(self) -> None:
        menu = QMenu(self._filter_btn)
        self._type_checks: dict[str, QCheckBox] = {}

        if not self._present_types:
            empty = QWidgetAction(menu)
            lbl = QLabel("  (aucun type dans l'inventaire)  ")
            lbl.setStyleSheet("color:#888; padding:6px;")
            empty.setDefaultWidget(lbl)
            menu.addAction(empty)
        else:
            for t in self._present_types:
                act = QWidgetAction(menu)
                cb = QCheckBox(t)
                cb.setChecked(True)
                cb.setStyleSheet("padding:4px 16px;")
                cb.toggled.connect(
                    lambda checked, name=t: self._on_check(name, checked))
                act.setDefaultWidget(cb)
                menu.addAction(act)
                self._type_checks[t] = cb

            menu.addSeparator()
            all_btn = QPushButton("Tout cocher")
            all_btn.setFlat(True)
            all_btn.clicked.connect(lambda: self._set_all(True))
            none_btn = QPushButton("Tout décocher")
            none_btn.setFlat(True)
            none_btn.clicked.connect(lambda: self._set_all(False))
            for b in (all_btn, none_btn):
                act = QWidgetAction(menu)
                act.setDefaultWidget(b)
                menu.addAction(act)

        self._filter_btn.setMenu(menu)
        self._update_filter_button_text()

    def _on_check(self, name: str, checked: bool) -> None:
        if checked:
            self._checked.add(name)
        else:
            self._checked.discard(name)
        self._update_filter_button_text()
        self._refresh()

    def _set_all(self, value: bool) -> None:
        for name, cb in self._type_checks.items():
            cb.blockSignals(True)
            cb.setChecked(value)
            cb.blockSignals(False)
            if value:
                self._checked.add(name)
            else:
                self._checked.discard(name)
        self._update_filter_button_text()
        self._refresh()

    def _update_filter_button_text(self) -> None:
        total = len(self._present_types)
        n = len(self._checked)
        if n == total:
            txt = "Tous les types ▾"
        elif n == 0:
            txt = "Aucun type ▾"
        elif n == 1:
            (only,) = self._checked
            txt = f"{only} ▾"
        else:
            txt = f"{n} / {total} types ▾"
        self._filter_btn.setText(txt)

    # ------------------------------------------------------------------ #
    def _refresh(self) -> None:
        self._hosts = [h for h in self._hosts_all
                       if _resolve_device_type(h) in self._checked]

        # Mémoriser le tri courant pour le restaurer après remplissage.
        hdr = self._table.horizontalHeader()
        sort_col = hdr.sortIndicatorSection()
        sort_order = hdr.sortIndicatorOrder()

        # Désactiver le tri pendant le remplissage (sinon Qt réordonne après
        # chaque setItem et les lignes finissent mélangées).
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._hosts))
        for row, host in enumerate(self._hosts):
            name, dtype, mac, ip = _row_values(host)
            # La colonne IP a une clé de tri numérique pour ranger 10.x après
            # 2.x au lieu d'avant (tri lexico naïf).
            cells = (
                _DeviceItem(name or "—", (name or "").lower()),
                _DeviceItem(dtype or "—", dtype or ""),
                _DeviceItem(mac or "—", mac or ""),
                _DeviceItem(ip or "—", _ip_sort_key(ip)),
            )
            for col, item in enumerate(cells):
                self._table.setItem(row, col, item)
        self._table.setSortingEnabled(True)
        # Restaurer l'indicateur de tri (et appliquer le tri sur les nouvelles
        # données).
        self._table.sortItems(sort_col, sort_order)

        total = len(self._hosts_all)
        shown = len(self._hosts)
        if shown == total:
            self._count_label.setText(f"{shown} device(s)")
        else:
            self._count_label.setText(f"{shown} / {total} device(s)")

    # ------------------------------------------------------------------ #
    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la liste en CSV", "devices.csv",
            "Fichier CSV (*.csv)")
        if not path:
            return
        try:
            # utf-8-sig : Excel ouvre correctement les accents.
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(_HEADERS)
                for host in self._hosts:
                    writer.writerow(_row_values(host))
        except OSError as e:
            QMessageBox.critical(
                self, "Echec de l'export", f"Impossible d'ecrire le CSV :\n{e}")
            return
        QMessageBox.information(
            self, "Export CSV",
            f"{len(self._hosts)} device(s) exporte(s) vers\n{Path(path).name}")
