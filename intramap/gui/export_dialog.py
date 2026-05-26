"""Dialogue d'options pour l'export PDF.

Permet de choisir la taille de page (A4 a A1), la repartition (carte sur une
ou plusieurs pages), et d'ajouter eventuellement le detail texte des
branchements des appareils d'infrastructure.
"""
from __future__ import annotations

import math

from PySide6.QtGui import QPageSize
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
    QVBoxLayout,
)

from intramap.gui.i18n import tr

# (libelle, identifiant QPageSize)
_PAGE_SIZES = [
    ("A4", QPageSize.A4),
    ("A3", QPageSize.A3),
    ("A2", QPageSize.A2),
    ("A1", QPageSize.A1),
]

# (libelle, nombre de pages en largeur)
_SPANS = [
    ("Tout sur une seule page", 1),
    ("Mosaique - 2 pages de large", 2),
    ("Mosaique - 3 pages de large", 3),
    ("Mosaique - 4 pages de large", 4),
]


def _oriented_page_points(page_size_id, landscape: bool) -> tuple[float, float]:
    """Dimensions de la page en points (1/72 pouce), orientee."""
    pt = QPageSize(page_size_id).sizePoints()
    w, h = float(pt.width()), float(pt.height())
    return (max(w, h), min(w, h)) if landscape else (min(w, h), max(w, h))


def page_grid(content_w: float, content_h: float,
              page_size_id, pages_wide: int) -> tuple[int, int, bool]:
    """Retourne (colonnes, lignes, paysage) pour la carte donnee.

    Les lignes sont calculees pour couvrir toute la hauteur en conservant
    les proportions de la carte.
    """
    if content_w <= 0 or content_h <= 0:
        return 1, 1, True
    landscape = content_w >= content_h
    if pages_wide <= 1:
        return 1, 1, landscape
    page_w, page_h = _oriented_page_points(page_size_id, landscape)
    total_w = pages_wide * page_w
    total_h = total_w * content_h / content_w
    pages_tall = max(1, math.ceil(total_h / page_h))
    return pages_wide, pages_tall, landscape


class ExportPdfDialog(QDialog):
    """Choix de la taille de page, de la repartition, et option branchements."""

    def __init__(self, content_w: float, content_h: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Exporter en PDF"))
        self.setMinimumWidth(400)
        self._w = content_w
        self._h = content_h

        layout = QVBoxLayout(self)
        intro = QLabel(tr(
            "Les proportions de la carte sont toujours conservees.\n"
            "Choisissez la taille de page et la repartition."))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        layout.addLayout(form)
        self.page_combo = QComboBox()
        for name, sid in _PAGE_SIZES:
            self.page_combo.addItem(name, sid)
        self.span_combo = QComboBox()
        for label, n in _SPANS:
            self.span_combo.addItem(tr(label), n)
        form.addRow(tr("Taille de page :"), self.page_combo)
        form.addRow(tr("Répartition :"), self.span_combo)

        self.include_wiring = QCheckBox(tr(
            "Ajouter le detail des branchements\n"
            "(routeurs, switchs, patch panels, outlets)"))
        self.include_wiring.setToolTip(tr(
            "Ajoute, apres la carte, des pages texte qui listent pour chaque "
            "appareil d'infrastructure tous les ports utilises et l'appareil "
            "branche en face."))
        layout.addWidget(self.include_wiring)

        self.estimate = QLabel()
        self.estimate.setStyleSheet("color:#555;")
        self.estimate.setWordWrap(True)
        layout.addWidget(self.estimate)

        self.page_combo.currentIndexChanged.connect(self._update_estimate)
        self.span_combo.currentIndexChanged.connect(self._update_estimate)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_estimate()

    def _update_estimate(self) -> None:
        cols, rows, _ = page_grid(self._w, self._h,
                                  self.page_combo.currentData(),
                                  self.span_combo.currentData())
        total = cols * rows
        if total == 1:
            self.estimate.setText(
                tr("-> 1 page : la carte entiere, ajustee a la page."))
        else:
            self.estimate.setText(
                tr("-> {cols} x {rows} = {total} pages a assembler "
                   "(meilleure lisibilite, qualite maximale).").format(
                    cols=cols, rows=rows, total=total))

    def selection(self) -> tuple[object, int, bool]:
        """Retourne (identifiant QPageSize, nb pages largeur, branchements).

        Le 3e element vaut True si l'utilisateur veut ajouter le detail
        texte des branchements apres la carte.
        """
        return (self.page_combo.currentData(),
                self.span_combo.currentData(),
                self.include_wiring.isChecked())
