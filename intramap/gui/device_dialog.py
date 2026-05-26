"""Dialogue de création d'un device manuel."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
    QMessageBox, QVBoxLayout,
)

from intramap.models import DEVICE_TYPES, Host, Inventory, Location, normalize_mac

_AUTO = "(auto)"


def _next_free_mac(existing: set[str]) -> str:
    """Génère une MAC locale (préfixe 02:) non utilisée dans l'inventaire.

    Le bit « localement administré » (02:) garantit l'absence de collision
    avec une MAC réelle de constructeur.
    """
    for n in range(1, 0xFFFF):
        candidate = f"02:00:00:00:{(n >> 8) & 0xFF:02x}:{n & 0xFF:02x}"
        if candidate not in existing:
            return candidate
    return "02:00:00:00:ff:ff"


class AddDeviceDialog(QDialog):
    """Saisie d'un nouveau device ajouté à la main (``manual=True``)."""

    def __init__(self, inv: Inventory, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un device")
        self.setMinimumWidth(360)
        self._inv = inv
        self.result_host: Host | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._mac = QLineEdit(_next_free_mac(set(inv.hosts.keys())))
        self._name = QLineEdit()
        self._name.setPlaceholderText("ex. : Switch garage")
        self._ip = QLineEdit()
        self._ip.setPlaceholderText("optionnel")
        self._dtype = QComboBox()
        self._dtype.addItem(_AUTO, None)
        for t in sorted(DEVICE_TYPES):
            self._dtype.addItem(t, t)
        self._floor = QLineEdit()
        self._room = QLineEdit()

        form.addRow("MAC :", self._mac)
        form.addRow("Nom :", self._name)
        form.addRow("IP :", self._ip)
        form.addRow("Type :", self._dtype)
        form.addRow("Étage :", self._floor)
        form.addRow("Pièce :", self._room)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        try:
            mac = normalize_mac(self._mac.text())
        except ValueError as e:
            QMessageBox.warning(self, "MAC invalide", str(e))
            return
        if mac in self._inv.hosts:
            QMessageBox.warning(
                self, "MAC déjà présente",
                f"Un device avec la MAC {mac} existe déjà.")
            return

        now = datetime.now()
        self.result_host = Host(
            mac=mac,
            ip=(self._ip.text().strip() or None),
            hostname=None,
            vendor=None,
            first_seen=now,
            last_seen=now,
            custom_name=(self._name.text().strip() or None),
            location=Location(
                floor=(self._floor.text().strip() or None),
                room=(self._room.text().strip() or None),
            ),
            device_type=self._dtype.currentData(),
            manual=True,
            online=True,
        )
        self.accept()
