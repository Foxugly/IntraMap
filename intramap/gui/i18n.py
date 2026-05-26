"""Couche Qt de l'i18n : préférence de langue (QSettings) et libellés du menu.

Le cœur (catalogue, ``tr``, ``set_language``…) vit dans
:mod:`intramap.i18n`, **sans Qt**, pour être partagé par le CLI et les
builders de rapports. Ce module le ré-exporte pour que le code GUI puisse
faire ``from intramap.gui.i18n import tr`` comme avant.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

from intramap.i18n import (  # noqa: F401  (ré-exports pour le GUI)
    _CATALOG, current_language, resolve_system_language, set_language, tr,
)

_SETTINGS_KEY = "language"


def available_languages() -> list[tuple[str, str]]:
    """Codes/libellés proposés dans le menu Langue."""
    return [("system", "Système"), ("fr", "Français"), ("en", "English")]


def load_saved_language() -> str:
    return str(QSettings("Foxugly", "IntraMap").value(_SETTINGS_KEY, "system"))


def save_language(choice: str) -> None:
    QSettings("Foxugly", "IntraMap").setValue(_SETTINGS_KEY, choice)


def apply_saved_language() -> None:
    """Applique la préférence enregistrée (en résolvant « system »)."""
    saved = load_saved_language()
    set_language(resolve_system_language() if saved == "system" else saved)
