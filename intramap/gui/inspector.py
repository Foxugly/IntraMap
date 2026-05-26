"""Panneau latéral d'édition des informations d'un device.

Les modifications sont appliquées **automatiquement**. Le panneau est organisé
en deux onglets : « Identité » (MAC, identité, emplacement) et « Liaisons »
(tous les câbles reliés à l'appareil + l'association Wi-Fi).

Le modèle de câbles est **symétrique** : un câble est un :class:`Link`
indépendant, sans direction, stocké dans :data:`Inventory.links`. Le panneau
liste donc simplement les câbles qui touchent l'appareil affiché — chacun a
un port côté ici, un port côté pair, et un état PoE.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget,
)

from intramap.models import (
    DEVICE_TYPES, Host, Inventory, Link, Location, is_valid_ip,
    links_touching, normalize_mac,
)

_AUTO = "(auto)"
_NONE = "(aucun)"
_FAR = 10 ** 9


def _opt_int(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _opt_str(text: str) -> str | None:
    text = text.strip()
    return text or None


class LinkRow(QFrame):
    """Une ligne pour éditer un :class:`Link` du point de vue de l'appareil
    affiché. Symétrique : le « port ici » est le port côté de cet appareil,
    le « port en face » est celui de l'autre extrémité.
    """

    changed = Signal()
    removed = Signal()
    goto = Signal(str)

    def __init__(self, inv: Inventory, this_mac: str,
                 link: Link | None = None, parent=None):
        super().__init__(parent)
        self._loading = False
        self._inv = inv
        self._this_mac = this_mac
        self.link = link

        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "LinkRow { background:#f6f7f9; border:1px solid #d8dadf;"
            " border-radius:6px; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 8)
        outer.setSpacing(5)

        header = QHBoxLayout()
        header.addWidget(QLabel("Port ici"))
        self._this_port = QLineEdit()
        self._this_port.setFixedWidth(52)
        self._this_port.setPlaceholderText("n°")
        header.addWidget(self._this_port)
        header.addWidget(QLabel("↔"))
        self._peer = QComboBox()
        self._peer.addItem(_NONE, None)
        for mac in sorted(inv.hosts):
            if mac == this_mac:
                continue
            h = inv.hosts[mac]
            self._peer.addItem(f"{h.custom_name or mac}  [{mac}]", mac)
        header.addWidget(self._peer, 1)
        self._goto_btn = QPushButton("↗")
        self._goto_btn.setFixedWidth(28)
        self._goto_btn.setToolTip("Ouvrir l'appareil en face")
        self._goto_btn.clicked.connect(self._emit_goto)
        header.addWidget(self._goto_btn)
        self._remove_btn = QPushButton("✕")
        self._remove_btn.setFixedWidth(28)
        self._remove_btn.setStyleSheet("color:#c0392b;")
        self._remove_btn.setToolTip("Supprimer cette liaison")
        self._remove_btn.clicked.connect(self.removed.emit)
        header.addWidget(self._remove_btn)
        outer.addLayout(header)

        form = QFormLayout()
        form.setSpacing(5)
        self._peer_port = QLineEdit()
        self._peer_port.setPlaceholderText("port de l'appareil en face")
        self._poe = QCheckBox("Liaison alimentée en PoE")
        form.addRow("Port en face :", self._peer_port)
        form.addRow("", self._poe)
        outer.addLayout(form)

        # Pré-remplissage à partir du Link.
        self._loading = True
        if link is not None:
            this_p, peer_p, peer_mac = self._sides_for(link, this_mac)
            self._this_port.setText("" if this_p is None else str(this_p))
            self._peer_port.setText("" if peer_p is None else str(peer_p))
            self._poe.setChecked(link.poe)
            idx = self._peer.findData(peer_mac)
            self._peer.setCurrentIndex(idx if idx >= 0 else 0)
        self._loading = False

        for w in (self._this_port, self._peer_port):
            w.editingFinished.connect(self._on_change)
        self._poe.toggled.connect(self._on_change)
        self._peer.currentIndexChanged.connect(self._on_change)

    @staticmethod
    def _sides_for(link: Link, this_mac: str):
        m = normalize_mac(this_mac)
        if link.mac_a == m:
            return link.port_a, link.port_b, link.mac_b
        return link.port_b, link.port_a, link.mac_a

    def _on_change(self) -> None:
        if not self._loading:
            self.changed.emit()

    def _emit_goto(self) -> None:
        mac = self._peer.currentData()
        if mac:
            self.goto.emit(mac)

    def _this_port_val(self) -> int | None:
        return _opt_int(self._this_port.text())

    def sort_key(self) -> int:
        v = self._this_port_val()
        return v if v is not None else _FAR

    def is_empty(self) -> bool:
        return self._peer.currentData() is None

    def to_link(self) -> Link | None:
        """Crée ou met à jour le :class:`Link` à partir des champs."""
        peer = self._peer.currentData()
        if peer is None:
            return None
        this_p = self._this_port_val()
        peer_p = _opt_int(self._peer_port.text())
        poe = self._poe.isChecked()
        if self.link is None:
            self.link = Link(mac_a=self._this_mac, port_a=this_p,
                             mac_b=peer, port_b=peer_p, poe=poe)
        else:
            m = normalize_mac(self._this_mac)
            if self.link.mac_a == m:
                self.link.port_a = this_p
                self.link.mac_b = normalize_mac(peer)
                self.link.port_b = peer_p
            else:
                self.link.port_b = this_p
                self.link.mac_a = normalize_mac(peer)
                self.link.port_a = peer_p
            self.link.poe = poe
        return self.link


class Inspector(QWidget):
    """Édite un :class:`Host` sélectionné, en deux onglets."""

    host_changed = Signal(str)
    host_deleted = Signal(str)
    select_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(300)

        self._host: Host | None = None
        self._inv: Inventory | None = None
        self._loading = False
        self._link_rows: list[LinkRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._title = QLabel("Aucun device sélectionné")
        self._title.setStyleSheet(
            "font-weight:bold; font-size:13px; padding:10px 12px 4px 12px;")
        self._title.setWordWrap(True)
        root.addWidget(self._title)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)

        # --- onglet 1 : Identité ----------------------------------------
        tab1 = QScrollArea()
        tab1.setWidgetResizable(True)
        tab1.setFrameShape(QFrame.NoFrame)
        t1 = QWidget()
        tab1.setWidget(t1)
        v1 = QVBoxLayout(t1)
        v1.setContentsMargins(12, 12, 12, 12)
        v1.setSpacing(10)

        self._mac_label = QLabel("—")
        self._mac_label.setStyleSheet("color:#888;")
        self._mac_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v1.addWidget(self._mac_label)

        ident = QGroupBox("Identité")
        f1 = QFormLayout(ident)
        self._name = QLineEdit()
        self._ip = QLineEdit()
        self._hostname = QLineEdit()
        self._vendor = QLineEdit()
        self._dtype = QComboBox()
        self._dtype.addItem(_AUTO, None)
        for t in sorted(DEVICE_TYPES):
            self._dtype.addItem(t, t)
        self._online = QCheckBox("En ligne")
        self._gateway = QCheckBox("Passerelle Internet (accès box)")
        self._poe_gateway = QComboBox()
        self._poe_gateway.setToolTip(
            "Switch PoE qui alimente cet appareil. Renseigné = appareil "
            "PoE : son chemin reste en PoE jusqu'à ce switch, puis hors PoE.")
        f1.addRow("Nom :", self._name)
        f1.addRow("IP :", self._ip)
        f1.addRow("Hostname :", self._hostname)
        f1.addRow("Constructeur :", self._vendor)
        f1.addRow("Type :", self._dtype)
        f1.addRow("", self._online)
        f1.addRow("", self._gateway)
        f1.addRow("Passerelle PoE :", self._poe_gateway)
        v1.addWidget(ident)

        loc = QGroupBox("Emplacement")
        f2 = QFormLayout(loc)
        self._floor = QLineEdit()
        self._room = QLineEdit()
        self._rack = QLineEdit()
        self._rack_unit = QLineEdit()
        self._rack_unit.setPlaceholderText("n° U (optionnel)")
        f2.addRow("Étage :", self._floor)
        f2.addRow("Pièce :", self._room)
        f2.addRow("Baie :", self._rack)
        f2.addRow("Unité (U) :", self._rack_unit)
        v1.addWidget(loc)
        v1.addStretch(1)
        self._tabs.addTab(tab1, "Identité")

        # --- onglet 2 : Liaisons ----------------------------------------
        tab2 = QScrollArea()
        tab2.setWidgetResizable(True)
        tab2.setFrameShape(QFrame.NoFrame)
        t2 = QWidget()
        tab2.setWidget(t2)
        v2 = QVBoxLayout(t2)
        v2.setContentsMargins(12, 12, 12, 12)
        v2.setSpacing(10)

        links = QGroupBox("Liaisons")
        links_outer = QVBoxLayout(links)
        links_outer.setSpacing(8)
        self._links_container = QVBoxLayout()
        self._links_container.setSpacing(8)
        links_outer.addLayout(self._links_container)
        self._empty_links = QLabel("Aucune liaison.")
        self._empty_links.setStyleSheet("color:#999; font-style:italic;")
        self._links_container.addWidget(self._empty_links)
        self._add_link_btn = QPushButton("+ Ajouter une liaison")
        self._add_link_btn.clicked.connect(self._add_link)
        links_outer.addWidget(self._add_link_btn)
        v2.addWidget(links)

        wifi = QGroupBox("Association Wi-Fi")
        f4 = QFormLayout(wifi)
        self._wifi_ap = QComboBox()
        f4.addRow("Point d'accès :", self._wifi_ap)
        v2.addWidget(wifi)
        v2.addStretch(1)
        self._tabs.addTab(tab2, "Liaisons")

        bottom = QVBoxLayout()
        bottom.setContentsMargins(12, 6, 12, 10)
        bottom.setSpacing(6)
        note = QLabel("Les modifications sont appliquées automatiquement.")
        note.setStyleSheet("color:#777; font-style:italic;")
        note.setWordWrap(True)
        bottom.addWidget(note)
        btns = QHBoxLayout()
        btns.addStretch(1)
        self._delete_btn = QPushButton("Supprimer le device")
        self._delete_btn.setStyleSheet("color:#c0392b;")
        self._delete_btn.clicked.connect(self._delete)
        btns.addWidget(self._delete_btn)
        bottom.addLayout(btns)
        root.addLayout(bottom)

        self._wire_signals()
        self._set_enabled(False)

    def _wire_signals(self) -> None:
        for w in (self._name, self._ip, self._hostname, self._vendor,
                  self._floor, self._room, self._rack, self._rack_unit):
            w.editingFinished.connect(self._apply)
        for w in (self._online, self._gateway):
            w.toggled.connect(self._apply)
        for w in (self._dtype, self._wifi_ap, self._poe_gateway):
            w.currentIndexChanged.connect(self._apply)

    def set_host(self, host: Host | None, inv: Inventory) -> None:
        self._loading = True
        try:
            self._host = host
            self._inv = inv
            if host is None:
                self._title.setText("Aucun device sélectionné")
                self._mac_label.setText("—")
                self._rebuild_links()
                self._set_enabled(False)
                return

            self._set_enabled(True)
            self.refresh_title()
            self._mac_label.setText(host.mac)

            self._name.setText(host.custom_name or "")
            self._ip.setText(host.ip or "")
            self._hostname.setText(host.hostname or "")
            self._vendor.setText(host.vendor or "")
            idx = self._dtype.findData(host.device_type)
            self._dtype.setCurrentIndex(idx if idx >= 0 else 0)
            self._online.setChecked(host.online)
            self._gateway.setChecked(host.is_gateway)

            self._floor.setText(host.location.floor or "")
            self._room.setText(host.location.room or "")
            self._rack.setText(host.location.rack or "")
            self._rack_unit.setText(
                "" if host.location.rack_unit is None
                else str(host.location.rack_unit))

            self._populate_peer_combo(self._wifi_ap, inv, host.mac)
            self._select_data(self._wifi_ap, host.wifi_ap_mac)
            self._populate_peer_combo(self._poe_gateway, inv, host.mac)
            self._select_data(self._poe_gateway, host.poe_gateway)

            self._rebuild_links()
        finally:
            self._loading = False

    def refresh_title(self) -> None:
        h = self._host
        if h is None:
            self._title.setText("Aucun device sélectionné")
            return
        suffix = " — manuel" if h.manual else ""
        self._title.setText((h.custom_name or h.mac) + suffix)

    def _populate_peer_combo(self, combo: QComboBox, inv: Inventory,
                             self_mac: str) -> None:
        combo.clear()
        combo.addItem(_NONE, None)
        for mac in sorted(inv.hosts):
            if mac == self_mac:
                continue
            h = inv.hosts[mac]
            combo.addItem(f"{h.custom_name or mac}  [{mac}]", mac)

    @staticmethod
    def _select_data(combo: QComboBox, data) -> None:
        idx = combo.findData(data)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _rebuild_links(self) -> None:
        for row in self._link_rows:
            row.setParent(None)
            row.deleteLater()
        self._link_rows.clear()
        host = self._host
        if host is not None and self._inv is not None:
            def key(lk: Link) -> int:
                p = lk.port_at(host.mac)
                return p if p is not None else _FAR
            for lk in sorted(links_touching(self._inv, host.mac), key=key):
                self._append_link_row(lk)
        self._empty_links.setVisible(not self._link_rows)

    def _append_link_row(self, link: Link | None = None) -> LinkRow:
        row = LinkRow(self._inv, self._host.mac, link=link)
        row.changed.connect(self._apply)
        row.removed.connect(lambda r=row: self._remove_link_row(r))
        row.goto.connect(self.select_requested.emit)
        self._links_container.insertWidget(
            self._links_container.indexOf(self._empty_links), row)
        self._link_rows.append(row)
        self._empty_links.setVisible(False)
        return row

    def _add_link(self) -> None:
        if self._host is None:
            return
        self._append_link_row(None)

    def _remove_link_row(self, row: LinkRow) -> None:
        if row.link is not None and self._inv is not None:
            try:
                self._inv.links.remove(row.link)
            except ValueError:
                pass
        if row in self._link_rows:
            self._link_rows.remove(row)
        row.setParent(None)
        row.deleteLater()
        self._empty_links.setVisible(not self._link_rows)
        self._apply()

    def _set_enabled(self, on: bool) -> None:
        for w in (self._name, self._ip, self._hostname, self._vendor,
                  self._dtype, self._online, self._gateway, self._poe_gateway,
                  self._floor, self._room, self._rack, self._rack_unit,
                  self._add_link_btn, self._wifi_ap, self._delete_btn):
            w.setEnabled(on)

    def _apply(self) -> None:
        if self._loading or self._host is None:
            return
        h = self._host
        h.custom_name = _opt_str(self._name.text())
        ip_text = self._ip.text().strip()
        if ip_text and not is_valid_ip(ip_text):
            QMessageBox.warning(
                self, "IP invalide",
                f"« {ip_text} » n'est pas une adresse IP valide ; "
                "valeur précédente conservée.")
            self._ip.setText(h.ip or "")  # revert vers l'ancienne valeur
        else:
            h.ip = ip_text or None
        h.hostname = _opt_str(self._hostname.text())
        h.vendor = _opt_str(self._vendor.text())
        h.device_type = self._dtype.currentData()
        h.online = self._online.isChecked()
        h.is_gateway = self._gateway.isChecked()
        h.poe_gateway = self._poe_gateway.currentData()

        h.location = Location(
            floor=_opt_str(self._floor.text()),
            room=_opt_str(self._room.text()),
            rack=_opt_str(self._rack.text()),
            rack_unit=_opt_int(self._rack_unit.text()),
        )

        # Réconcilier les liaisons : on retire les câbles déjà gérés par les
        # lignes, puis on réinsère l'état courant via Inventory.add_link (qui
        # déduplique par identité canonique). Évite les doublons quand une
        # ligne reproduit un câble existant ou est ré-appliquée plusieurs fois.
        try:
            managed = {id(row.link)
                       for row in self._link_rows if row.link is not None}
            desired = [lk for lk in (row.to_link() for row in self._link_rows)
                       if lk is not None]
        except ValueError as e:
            QMessageBox.warning(self, "Liaison invalide", str(e))
            return
        self._inv.links = [lk for lk in self._inv.links
                           if id(lk) not in managed]
        for lk in desired:
            self._inv.add_link(lk)

        wifi = self._wifi_ap.currentData()
        h.wifi_ap_mac = normalize_mac(wifi) if wifi else None

        self.host_changed.emit(h.mac)

    def _delete(self) -> None:
        if self._host is None:
            return
        mac = self._host.mac
        name = self._host.custom_name or mac
        if QMessageBox.question(
            self, "Supprimer le device",
            f"Supprimer « {name} » de la carte ?",
        ) == QMessageBox.Yes:
            self.host_deleted.emit(mac)
