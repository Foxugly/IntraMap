"""Chargement et mise en cache des icônes de devices pour le canvas Qt.

Réutilise les PNG fournis dans ``intramap/renderers/icons/`` — la même
banque d'icônes que les renderers Graphviz/PlantUML, pour une cohérence
visuelle entre la carte interactive et les exports statiques.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPixmap

from intramap.models import DEVICE_TYPES
from intramap.renderers.icons import DEVICE_COLORS

_ICON_DIR = Path(__file__).resolve().parent.parent / "renderers" / "icons"

_pixmap_cache: dict[str, QPixmap] = {}


def icon_pixmap(device_type: str) -> QPixmap:
    """Retourne le QPixmap de l'icône d'un device_type (mis en cache).

    Retombe sur l'icône ``other`` si le type est inconnu ou le fichier
    manquant.
    """
    if device_type not in DEVICE_TYPES:
        device_type = "other"
    if device_type in _pixmap_cache:
        return _pixmap_cache[device_type]

    path = _ICON_DIR / f"{device_type}.png"
    pm = QPixmap(str(path))
    if pm.isNull() and device_type != "other":
        pm = icon_pixmap("other")
    _pixmap_cache[device_type] = pm
    return pm


def device_color(device_type: str) -> QColor:
    """Couleur d'accent associée à un device_type (cf. renderers)."""
    return QColor(DEVICE_COLORS.get(device_type, DEVICE_COLORS["other"]))
