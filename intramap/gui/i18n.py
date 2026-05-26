"""Internationalisation légère du chrome GUI (catalogue FR -> EN).

Le français est la langue **source** (les chaînes dans le code sont en
français). ``tr(text)`` renvoie la source en mode français, sinon la
traduction du catalogue (repli sur la source si absente — jamais d'exception).

Pas de fichiers Qt ``.ts/.qm`` : catalogue Python explicite, testable sans
outillage externe.
"""
from __future__ import annotations

import locale

from PySide6.QtCore import QSettings

_SETTINGS_KEY = "language"

# Catalogue des traductions : _CATALOG[langue][source_FR] = traduction.
_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        # --- Fenêtre principale : menus / actions / barre d'outils ---
        "Nouveau": "New",
        "Ouvrir un inventaire…": "Open inventory…",
        "Enregistrer": "Save",
        "Enregistrer sous…": "Save as…",
        "Fermer l'inventaire": "Close inventory",
        "Exporter en PDF…": "Export to PDF…",
        "Quitter": "Quit",
        "Récemment ouverts": "Recently opened",
        "(aucun)": "(none)",
        "Vider la liste": "Clear list",
        "Annuler": "Undo",
        "Rétablir": "Redo",
        "Scanner le réseau": "Scan the network",
        "Ajouter un device": "Add a device",
        "Relier deux appareils…": "Connect two devices…",
        "Supprimer le device sélectionné": "Delete the selected device",
        "Ajuster à la fenêtre": "Fit to window",
        "Zoom avant": "Zoom in",
        "Zoom arrière": "Zoom out",
        "Panneau latéral": "Side panel",
        "Masquer / réafficher le panneau d'édition à droite":
            "Hide / show the editing panel on the right",
        "Réorganiser automatiquement": "Auto-arrange",
        "Liste des devices (MAC / IP)…": "Device list (MAC / IP)…",
        "Rapport des chemins réseau…": "Network paths report…",
        "Diagnostics réseau…": "Network diagnostics…",
        "Angles droits — horizontal d'abord":
            "Right angles — horizontal first",
        "Angles droits — vertical d'abord": "Right angles — vertical first",
        "Lignes droites": "Straight lines",
        "Réinitialiser les coudes": "Reset bends",
        "&Fichier": "&File",
        "&Édition": "&Edit",
        "&Affichage": "&View",
        "Langue": "Language",
        "Style des liaisons": "Link style",
        "Principale": "Main",
        "Rechercher (nom, IP, type, étage…)":
            "Search (name, IP, type, floor…)",
        # --- Barre de statut / messages ---
        "Prêt": "Ready",
        "Nouvel inventaire": "New inventory",
        "Inventaire fermé": "Inventory closed",
        "Annulé": "Undone",
        "Rétabli": "Redone",
        # --- Dialogues : langue ---
        "Langue modifiée": "Language changed",
        "La langue sera appliquée au prochain démarrage.":
            "The language will be applied on the next start.",
    },
}

_lang = "fr"


def set_language(lang: str) -> None:
    """Définit la langue courante (``fr`` ou ``en`` ; sinon ``fr``)."""
    global _lang
    _lang = lang if lang in ("fr", "en") else "fr"


def current_language() -> str:
    return _lang


def tr(text: str) -> str:
    """Traduit ``text`` (source française) vers la langue courante."""
    if _lang == "fr":
        return text
    return _CATALOG.get(_lang, {}).get(text, text)


def available_languages() -> list[tuple[str, str]]:
    """Codes/libellés proposés dans le menu Langue."""
    return [("system", "Système"), ("fr", "Français"), ("en", "English")]


def resolve_system_language() -> str:
    """Mappe la locale système vers ``fr`` (préfixe « fr ») ou ``en``."""
    try:
        code = (locale.getlocale()[0] or "")
    except (ValueError, TypeError):
        code = ""
    return "fr" if code.lower().startswith("fr") else "en"


def load_saved_language() -> str:
    return str(QSettings("Foxugly", "IntraMap").value(_SETTINGS_KEY, "system"))


def save_language(choice: str) -> None:
    QSettings("Foxugly", "IntraMap").setValue(_SETTINGS_KEY, choice)


def apply_saved_language() -> None:
    """Applique la préférence enregistrée (en résolvant « system »)."""
    saved = load_saved_language()
    set_language(resolve_system_language() if saved == "system" else saved)
