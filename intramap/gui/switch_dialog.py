"""Dialogue de gestion des ports d'un appareil (switch, patch panel, prise).

Affiche les liaisons sur chaque port et permet d'attribuer un **label** à
chaque port (utile pour les prises murales où chaque jack a un numéro de
câble côté patch panel).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from intramap.models import Host, Inventory, Link, _resolve_device_type, links_touching

_MAX_PORTS = 96
_GRID_COLS = 12


def port_connections(device: Host, inv: Inventory) -> dict[int, list[Link]]:
    """Renvoie ``{n° port: [liaisons]}`` pour ``device``."""
    ports: dict[int, list[Link]] = {}
    for lk in links_touching(inv, device.mac):
        p = lk.port_at(device.mac)
        if p is None:
            continue
        ports.setdefault(p, []).append(lk)
    return ports


def _port_is_poe(links: list[Link]) -> bool:
    return any(lk.poe for lk in links)


def clean_labels(labels: dict[int, str], port_count: int) -> dict[int, str]:
    """Ne garde que les labels non vides des ports réellement déclarés.

    Réduire le nombre de ports ne doit pas laisser traîner le label d'un port
    qui n'existe plus (il serait persisté à tort).
    """
    return {p: lbl for p, lbl in labels.items()
            if lbl.strip() and 1 <= p <= port_count}


def _describe_port(device: Host, links: list[Link],
                   inv: Inventory) -> list[str]:
    out: list[str] = []
    for lk in links:
        other_mac = lk.other_mac(device.mac)
        other = inv.hosts.get(other_mac)
        name = (other.custom_name or other.mac) if other is not None else other_mac
        other_port = lk.port_at(other_mac)
        sp = f" — port {other_port}" if other_port is not None else ""
        tag = "  (PoE)" if lk.poe else ""
        out.append(f"↔ {name}{sp}{tag}")
    return out


class SwitchPortDialog(QDialog):
    """Déclare le nombre de ports, leurs labels, et affiche leur occupation.

    Après acceptation, :attr:`port_count` contient le nombre de ports choisi
    et ``device.port_labels`` est mis à jour avec les labels saisis.
    """

    def __init__(self, switch: Host, inv: Inventory,
                 current_count: int | None, parent=None):
        super().__init__(parent)
        self.switch = switch
        self._inv = inv
        self._ports = port_connections(switch, inv)
        self.port_count = current_count or 0
        # Copie de travail des labels — appliquée à l'appareil sur OK.
        self._labels: dict[int, str] = dict(switch.port_labels)

        self.setWindowTitle(f"Ports — {switch.custom_name or switch.mac}")
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Nombre de ports :"))
        self._spin = QSpinBox()
        self._spin.setRange(1, _MAX_PORTS)
        max_used = max(self._ports) if self._ports else 0
        max_labeled = max(self._labels) if self._labels else 0
        default = current_count or max(8, max_used, max_labeled)
        self._spin.setValue(
            min(_MAX_PORTS, max(default, max_used, max_labeled, 1)))
        self._spin.valueChanged.connect(self._rebuild)
        top.addWidget(self._spin)
        top.addStretch(1)
        layout.addLayout(top)

        legend = QLabel(
            "Gris : libre   —   Vert : occupé   —   Orange : occupé (PoE)."
            "  Survolez un port pour voir ses liaisons. Le label éventuel "
            "apparaît entre crochets sous le numéro.")
        legend.setStyleSheet("color:#555;")
        legend.setWordWrap(True)
        layout.addWidget(legend)

        # Grille d'occupation des ports.
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(4)
        self._grid.setContentsMargins(2, 2, 2, 2)
        grid_scroll = QScrollArea()
        grid_scroll.setWidgetResizable(True)
        grid_scroll.setWidget(self._grid_host)
        grid_scroll.setMinimumHeight(160)
        layout.addWidget(grid_scroll)

        # Détail des liaisons (texte).
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._detail = QLabel()
        self._detail.setWordWrap(True)
        self._detail.setAlignment(Qt.AlignTop)
        self._detail.setStyleSheet("color:#333;")
        detail_scroll = QScrollArea()
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self._detail)
        detail_scroll.setMinimumHeight(120)
        layout.addWidget(detail_scroll)

        # Tableau d'édition des labels par port — réservé aux prises murales
        # (un jack de prise porte typiquement le n° du câble côté patch panel).
        self._show_labels = _resolve_device_type(switch) == "outlet"
        self._labels_table: QTableWidget | None = None
        if self._show_labels:
            layout.addWidget(QLabel("Labels des jacks — ex. n° du câble UTP "
                                    "dans le patch panel :"))
            self._labels_table = QTableWidget(0, 2)
            self._labels_table.setHorizontalHeaderLabels(["Jack", "Label"])
            self._labels_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeToContents)
            self._labels_table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.Stretch)
            self._labels_table.verticalHeader().setVisible(False)
            self._labels_table.setMinimumHeight(140)
            self._labels_table.itemChanged.connect(self._on_label_changed)
            layout.addWidget(self._labels_table)

        self._warning = QLabel()
        self._warning.setStyleSheet("color:#c0392b;")
        self._warning.setWordWrap(True)
        layout.addWidget(self._warning)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._rebuild()

    def _rebuild(self) -> None:
        # Vide la grille.
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        count = self._spin.value()
        for port in range(1, count + 1):
            label_txt = self._labels.get(port, "").strip()
            cell_text = str(port) if not label_txt else f"{port}\n[{label_txt}]"
            cell = QLabel(cell_text)
            cell.setAlignment(Qt.AlignCenter)
            cell.setFixedSize(52, 40)
            cell.setStyleSheet(cell.styleSheet())   # init
            links = self._ports.get(port)
            if not links:
                cell.setStyleSheet(
                    "background:#eeeeee; border:1px solid #cccccc;"
                    " border-radius:4px; font-size:10px;")
            else:
                if _port_is_poe(links):
                    cell.setStyleSheet(
                        "background:#ffe0b3; border:1px solid #ff7f0e;"
                        " border-radius:4px; font-size:10px;")
                else:
                    cell.setStyleSheet(
                        "background:#cfe8cf; border:1px solid #2ca02c;"
                        " border-radius:4px; font-size:10px;")
                cell.setToolTip(
                    f"Port {port}\n"
                    + "\n".join(_describe_port(self.switch, links, self._inv))
                )
            r, c = divmod(port - 1, _GRID_COLS)
            self._grid.addWidget(cell, r, c)

        used = sum(1 for p in self._ports if p <= count)
        self._summary.setText(
            f"{used} port(s) occupé(s), {count - used} libre(s) sur {count}.")

        if self._ports:
            lines: list[str] = []
            for port in sorted(self._ports):
                lines.append(f"Port {port} :")
                for d in _describe_port(self.switch, self._ports[port],
                                        self._inv):
                    lines.append(f"    {d}")
            self._detail.setText("\n".join(lines))
        else:
            self._detail.setText("Aucune liaison sur cet appareil.")

        # Tableau des labels (uniquement pour les prises).
        if self._labels_table is not None:
            self._labels_table.blockSignals(True)
            self._labels_table.setRowCount(count)
            for i in range(count):
                port = i + 1
                port_item = QTableWidgetItem(str(port))
                port_item.setFlags(port_item.flags() & ~Qt.ItemIsEditable)
                port_item.setTextAlignment(Qt.AlignCenter)
                self._labels_table.setItem(i, 0, port_item)
                label_item = QTableWidgetItem(self._labels.get(port, ""))
                self._labels_table.setItem(i, 1, label_item)
            self._labels_table.blockSignals(False)

        over = sorted(p for p in self._ports if p > count)
        if over:
            self._warning.setText(
                "Attention : des liaisons utilisent des ports au-delà du "
                f"nombre déclaré ({', '.join(map(str, over))}). "
                "Augmentez le nombre de ports.")
        else:
            self._warning.setText("")

    def _on_label_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 1:
            return
        port = item.row() + 1
        txt = item.text().strip()
        if txt:
            self._labels[port] = txt
        else:
            self._labels.pop(port, None)
        # Mettre à jour la cellule correspondante dans la grille en relisant.
        # (rebuild léger : on touche juste la cell concernée — on rebuild tout
        # pour rester simple.)
        self._rebuild()

    def _accept(self) -> None:
        self.port_count = self._spin.value()
        if self._show_labels:
            # Appliquer les labels — uniquement pour les prises, et en écartant
            # ceux des ports hors du nombre déclaré (bug : labels périmés).
            self.switch.port_labels = clean_labels(self._labels, self.port_count)
        self.accept()
