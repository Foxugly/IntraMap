"""Dialogue « Relier deux appareils » — création groupée de câbles.

On choisit deux appareils, on précise si les liens sont en PoE, on indique
les paires de ports (un câble = un port de chaque côté), un bouton génère
le tableau à partir d'une plage. Le résultat est une liste de :class:`Link`
à ajouter à :data:`Inventory.links`.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from intramap.gui.i18n import tr
from intramap.models import Host, Inventory, Link, _resolve_device_type

_MAX_PORT = 96

# Types « infrastructure » : ce qui transporte/relaie le reseau et qu'on veut
# voir remonter quand on cherche un point de raccordement hors-etage.
_INFRA_TYPES: frozenset[str] = frozenset({
    "router", "switch", "patchpanel", "ap", "controller", "outlet",
})


def _group_for(host: Host, ref: Host | None) -> int:
    """Renvoie l'indice de groupe d'un appareil par rapport au point de
    reference ``ref`` (l'autre extremite de la liaison en cours d'edition).

    0 = meme piece que ``ref``
    1 = meme etage que ``ref`` (mais autre piece)
    2 = infrastructure situee hors de l'etage de ``ref``
    3 = tout le reste
    """
    if ref is not None:
        rf = ref.location.floor
        rr = ref.location.room
        hf = host.location.floor
        hr = host.location.room
        if rf and rr and hf == rf and hr == rr:
            return 0
        if rf and hf == rf:
            return 1
    if _resolve_device_type(host) in _INFRA_TYPES:
        return 2
    return 3


class ConnectDialog(QDialog):
    """Cree plusieurs cables entre deux appareils en une fois.

    Apres acceptation, :attr:`new_links` contient la liste des :class:`Link`
    a ajouter a ``inv.links``.
    """

    def __init__(self, inv: Inventory, source_mac: str | None = None,
                 dest_mac: str | None = None, parent=None):
        super().__init__(parent)
        self._inv = inv
        self.new_links: list[Link] = []

        self.setWindowTitle(tr("Relier deux appareils"))
        self.setMinimumWidth(540)
        self.resize(540, 500)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._source = QComboBox()
        self._dest = QComboBox()
        # Garde-fou anti-recursion : repeupler un combo modifie son index
        # courant et declencherait la repopulation de l'autre, etc.
        self._refilling = False

        # Premier remplissage sans reference (alphabetique), pour pouvoir
        # appliquer les pre-selections du canvas.
        self._populate(self._source, ref_mac=None, keep_mac=source_mac)
        self._populate(self._dest, ref_mac=source_mac or None,
                       keep_mac=dest_mac)
        # Repasse pour que A soit ordonne autour de B.
        self._populate(self._source, ref_mac=self._dest.currentData(),
                       keep_mac=self._source.currentData())
        # Si A == B par defaut, on bascule B sur le premier autre.
        if (self._dest.count() > 1
                and self._dest.currentData() == self._source.currentData()):
            for i in range(self._dest.count()):
                data = self._dest.itemData(i)
                if data and data != self._source.currentData():
                    self._dest.setCurrentIndex(i)
                    break

        self._poe = QCheckBox(tr("Toutes ces liaisons sont alimentées en PoE"))
        form.addRow(tr("Appareil A :"), self._source)
        form.addRow(tr("Appareil B :"), self._dest)
        form.addRow("", self._poe)
        layout.addLayout(form)

        rng = QGroupBox(tr("Remplir une plage de ports"))
        rl = QHBoxLayout(rng)
        self._a_from = QSpinBox()
        self._a_to = QSpinBox()
        self._b_from = QSpinBox()
        for sb, val in ((self._a_from, 1), (self._a_to, 10),
                        (self._b_from, 1)):
            sb.setRange(1, _MAX_PORT)
            sb.setValue(val)
        rl.addWidget(QLabel(tr("Ports A")))
        rl.addWidget(self._a_from)
        rl.addWidget(QLabel("→"))
        rl.addWidget(self._a_to)
        rl.addWidget(QLabel(tr("    Port B de départ")))
        rl.addWidget(self._b_from)
        gen = QPushButton(tr("Générer"))
        gen.clicked.connect(self._generate)
        rl.addWidget(gen)
        layout.addWidget(rng)

        self._table = QTableWidget(0, 2)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        layout.addWidget(self._table)

        row_btns = QHBoxLayout()
        add = QPushButton(tr("+ Ligne"))
        add.clicked.connect(lambda: self._add_row())
        rm = QPushButton(tr("− Ligne"))
        rm.clicked.connect(self._remove_row)
        row_btns.addWidget(add)
        row_btns.addWidget(rm)
        row_btns.addStretch(1)
        layout.addLayout(row_btns)

        self._summary = QLabel()
        self._summary.setStyleSheet("color:#555;")
        layout.addWidget(self._summary)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._source.currentIndexChanged.connect(self._on_source_changed)
        self._dest.currentIndexChanged.connect(self._on_dest_changed)
        self._table.itemChanged.connect(lambda *_: self._update_summary())

        self._refresh_headers()
        self._generate()

    # ------------------------------------------------------------------ #
    # Remplissage groupe des combos (piece -> etage -> infra -> autres)
    # ------------------------------------------------------------------ #
    def _label(self, mac: str, host: Host) -> str:
        return f"{host.custom_name or mac}  [{mac}]"

    def _populate(self, combo: QComboBox, ref_mac: str | None,
                  keep_mac: str | None) -> None:
        """Repeuple ``combo`` en quatre groupes separes par des separateurs,
        ordonnes autour de l'appareil ``ref_mac``. Restaure la selection
        ``keep_mac`` si possible.
        """
        ref_host = self._inv.hosts.get(ref_mac) if ref_mac else None
        by_group: dict[int, list[tuple[str, str]]] = {
            0: [], 1: [], 2: [], 3: [],
        }
        for mac, host in self._inv.hosts.items():
            g = _group_for(host, ref_host)
            by_group[g].append((self._label(mac, host), mac))
        for items in by_group.values():
            items.sort(key=lambda t: t[0].lower())

        self._refilling = True
        try:
            combo.clear()
            first = True
            for g in (0, 1, 2, 3):
                items = by_group[g]
                if not items:
                    continue
                if not first:
                    combo.insertSeparator(combo.count())
                first = False
                for label, mac in items:
                    combo.addItem(label, mac)
            if keep_mac:
                idx = combo.findData(keep_mac)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        finally:
            self._refilling = False

    def _on_source_changed(self) -> None:
        if self._refilling:
            return
        # Quand A change, on reordonne B autour de la nouvelle reference A,
        # en preservant la selection courante de B.
        self._populate(self._dest, ref_mac=self._source.currentData(),
                       keep_mac=self._dest.currentData())
        self._refresh_headers()

    def _on_dest_changed(self) -> None:
        if self._refilling:
            return
        self._populate(self._source, ref_mac=self._dest.currentData(),
                       keep_mac=self._source.currentData())
        self._refresh_headers()

    def _name(self, combo: QComboBox) -> str:
        mac = combo.currentData()
        h = self._inv.hosts.get(mac) if mac else None
        return (h.custom_name or mac) if h else "?"

    def _refresh_headers(self) -> None:
        self._table.setHorizontalHeaderLabels([
            tr("Port côté {name}").format(name=self._name(self._source)),
            tr("Port côté {name}").format(name=self._name(self._dest)),
        ])
        self._update_summary()

    def _add_row(self, a: int | None = None, b: int | None = None) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        self._table.setItem(r, 0,
                            QTableWidgetItem("" if a is None else str(a)))
        self._table.setItem(r, 1,
                            QTableWidgetItem("" if b is None else str(b)))

    def _remove_row(self) -> None:
        r = self._table.currentRow()
        if r < 0:
            r = self._table.rowCount() - 1
        if r >= 0:
            self._table.removeRow(r)
        self._update_summary()

    def _generate(self) -> None:
        self._table.setRowCount(0)
        a, b = self._a_from.value(), self._a_to.value()
        if b < a:
            a, b = b, a
        d = self._b_from.value()
        for i, src in enumerate(range(a, b + 1)):
            self._add_row(src, d + i)
        self._update_summary()

    def _pairs(self) -> list[tuple[int | None, int | None]]:
        def cell(r: int, c: int) -> int | None:
            item = self._table.item(r, c)
            text = item.text().strip() if item is not None else ""
            if not text:
                return None
            try:
                return int(text)
            except ValueError:
                return None

        pairs: list[tuple[int | None, int | None]] = []
        for r in range(self._table.rowCount()):
            s, d = cell(r, 0), cell(r, 1)
            if s is not None or d is not None:
                pairs.append((s, d))
        return pairs

    def _update_summary(self) -> None:
        n = len(self._pairs())
        self._summary.setText(
            tr("{n} liaison(s) seront créées : {a} <-> {b}.").format(
                n=n, a=self._name(self._source), b=self._name(self._dest)))

    def _accept(self) -> None:
        a_mac = self._source.currentData()
        b_mac = self._dest.currentData()
        if not a_mac or not b_mac:
            QMessageBox.warning(self, tr("Sélection incomplète"),
                                tr("Choisissez les deux appareils."))
            return
        if a_mac == b_mac:
            QMessageBox.warning(self, tr("Même appareil"),
                                tr("Les deux appareils doivent être "
                                   "différents."))
            return
        pairs = self._pairs()
        if not pairs:
            QMessageBox.warning(self, tr("Aucune liaison"),
                                tr("Ajoutez au moins une paire de ports."))
            return
        poe = self._poe.isChecked()
        self.new_links = [
            Link(mac_a=a_mac, port_a=a, mac_b=b_mac, port_b=b, poe=poe)
            for a, b in pairs
        ]
        self.accept()
