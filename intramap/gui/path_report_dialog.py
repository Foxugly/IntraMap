"""Dialogue « Rapport des chemins réseau » — traceroute physique complet.

Pour chaque appareil de la carte, suit les liaisons jusqu'à la passerelle
Internet (l'appareil coché « Passerelle Internet »), et présente le chemin
en texte lisible, copiable et exportable.

Le traceroute est **non-directionnel** : un câble entre A et B est suivi dans
les deux sens, peu importe qui le détient dans le modèle. Le calcul part de
la passerelle et ne transite que par des appareils d'infrastructure
(outlet/switch/router/patchpanel/ap/controller). Le PoE est respecté : un
appareil PoE reste en PoE jusqu'à son switch PoE, puis hors PoE.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from intramap.gui.i18n import tr
from intramap.models import Inventory
from intramap.path_report import build_report


class PathReportDialog(QDialog):
    """Affiche le traceroute physique de tous les appareils de l'inventaire."""

    def __init__(self, inv: Inventory, parent=None):
        super().__init__(parent)
        self._text = build_report(inv)

        self.setWindowTitle(tr("Rapport des chemins réseau"))
        self.resize(660, 580)
        layout = QVBoxLayout(self)

        intro = QLabel(tr(
            "Chemin physique de chaque appareil jusqu'à la passerelle "
            "Internet, hop par hop.\nLe parcours est non-directionnel et ne "
            "transite que par les appareils d'infrastructure (switch, patch "
            "panel, prise, routeur, AP)."))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.NoWrap)
        font = QFont("monospace")
        font.setStyleHint(QFont.Monospace)
        view.setFont(font)
        view.setPlainText(self._text)
        layout.addWidget(view)

        btns = QHBoxLayout()
        copy_btn = QPushButton(tr("Copier"))
        copy_btn.clicked.connect(self._copy)
        export_btn = QPushButton(tr("Exporter en .txt…"))
        export_btn.clicked.connect(self._export)
        close_btn = QPushButton(tr("Fermer"))
        close_btn.clicked.connect(self.accept)
        btns.addWidget(copy_btn)
        btns.addWidget(export_btn)
        btns.addStretch(1)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, tr("Exporter le rapport"), "chemins-reseau.txt",
            tr("Fichier texte (*.txt)"))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text)
        except OSError as e:
            QMessageBox.critical(
                self, tr("Échec de l'export"),
                tr("Impossible d'écrire le fichier :\n{err}").format(err=e))
            return
        QMessageBox.information(
            self, tr("Export"),
            tr("Rapport exporté vers\n{name}").format(name=Path(path).name))
