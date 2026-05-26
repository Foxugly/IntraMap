"""Dialogue « Diagnostics réseau » : liste les anomalies de câblage détectées.

Double-cliquer une anomalie ferme le dialogue et demande à la fenêtre
principale de sélectionner l'appareil concerné sur la carte.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout,
)

from intramap.diagnostics import diagnose
from intramap.models import Inventory

_COLOR = {"error": "#c0392b", "warning": "#e67e22", "info": "#2c3e50"}
_PREFIX = {"error": "● ERREUR", "warning": "● ATTENTION", "info": "● INFO"}


class DiagnoseDialog(QDialog):
    """Affiche les :class:`Finding` de :func:`diagnose`. Après fermeture,
    :attr:`selected_mac` contient l'appareil à sélectionner (ou ``None``)."""

    def __init__(self, inv: Inventory, parent=None):
        super().__init__(parent)
        self.selected_mac: str | None = None
        self._findings = diagnose(inv)

        self.setWindowTitle("Diagnostics réseau")
        self.resize(640, 460)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Anomalies de câblage détectées. Double-cliquez une ligne pour "
            "sélectionner l'appareil concerné sur la carte.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        if not self._findings:
            self._list.addItem("Aucune anomalie détectée. ✓")
        for f in self._findings:
            item = QListWidgetItem(f"{_PREFIX.get(f.severity, '●')}  {f.message}")
            item.setForeground(QColor(_COLOR.get(f.severity, "#000000")))
            item.setData(Qt.UserRole, list(f.macs))
            self._list.addItem(item)
        layout.addWidget(self._list)

        btns = QHBoxLayout()
        btns.addStretch(1)
        close = QPushButton("Fermer")
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        layout.addLayout(btns)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        macs = item.data(Qt.UserRole)
        if macs:
            self.selected_mac = macs[0]
            self.accept()
