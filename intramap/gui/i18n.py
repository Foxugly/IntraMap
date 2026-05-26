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
        # --- Chargement / sauvegarde / export ---
        "Ouvrir un inventaire": "Open inventory",
        "Inventaire illisible": "Unreadable inventory",
        "Impossible de charger {path} :\n{err}":
            "Could not load {path}:\n{err}",
        "{n} device(s) chargé(s) depuis {name}":
            "{n} device(s) loaded from {name}",
        "Inventaire YAML (*.yaml *.yml);;Tous les fichiers (*)":
            "YAML inventory (*.yaml *.yml);;All files (*)",
        "Échec de l'enregistrement": "Save failed",
        "Impossible d'écrire {path} :\n{err}":
            "Could not write {path}:\n{err}",
        "Enregistré : {name}": "Saved: {name}",
        "Enregistrer l'inventaire sous": "Save inventory as",
        "Inventaire YAML (*.yaml)": "YAML inventory (*.yaml)",
        "Rien à exporter": "Nothing to export",
        "La carte est vide. Scannez le réseau ou ajoutez un device.":
            "The map is empty. Scan the network or add a device.",
        "Exporter la carte en PDF": "Export the map to PDF",
        "Document PDF (*.pdf)": "PDF document (*.pdf)",
        "Échec de l'export": "Export failed",
        "Impossible d'écrire le PDF :\n{err}":
            "Could not write the PDF:\n{err}",
        "PDF exporté : {name} ({n} page(s))":
            "PDF exported: {name} ({n} page(s))",
        # --- Scan ---
        "Aucun sous-réseau détecté. Saisissez un CIDR :":
            "No subnet detected. Enter a CIDR:",
        "Sous-réseau à scanner :": "Subnet to scan:",
        "Plusieurs sous-réseaux détectés :": "Several subnets detected:",
        "Scan de {network} en cours…": "Scanning {network}…",
        "Scan terminé : {n} device(s) détecté(s), {new} nouveau(x).":
            "Scan complete: {n} device(s) found, {new} new.",
        "Changements du scan": "Scan changes",
        "Échec du scan": "Scan failed",
        "Scan échoué": "Scan failed",
        # --- Édition ---
        "Device ajouté : {name}": "Device added: {name}",
        "Pas assez d'appareils": "Not enough devices",
        "Il faut au moins deux appareils sur la carte pour créer une liaison.":
            "You need at least two devices on the map to create a link.",
        "{n} liaison(s) créée(s) avec {peer}":
            "{n} link(s) created with {peer}",
        "Aucun device sélectionné": "No device selected",
        "Modifications appliquées": "Changes applied",
        "Device supprimé": "Device deleted",
        "Carte réorganisée par étage et pièce":
            "Map rearranged by floor and room",
        "Style de liaison appliqué": "Link style applied",
        "Coudes des liaisons réinitialisés": "Link bends reset",
        "{n} appareil(s) correspondant(s)": "{n} matching device(s)",
        "Double-clic : gestion des ports réservée aux switches, "
        "prises murales et patch panels":
            "Double-click: port management is reserved for switches, outlets "
            "and patch panels",
        "{name} : {count} ports déclarés": "{name}: {count} ports declared",
        "Modifications non enregistrées": "Unsaved changes",
        "Enregistrer les modifications avant de continuer ?":
            "Save changes before continuing?",
        # --- Nœud (tooltip) ---
        "MAC :": "MAC:",
        "IP :": "IP:",
        "Type :": "Type:",
        "Constructeur :": "Vendor:",
        "État :": "State:",
        "en ligne": "online",
        "hors ligne": "offline",
        "(device ajouté manuellement)": "(manually added device)",
        # --- Inspecteur ---
        "(auto)": "(auto)",
        "Port ici": "Port here",
        "n°": "no.",
        "Ouvrir l'appareil en face": "Open the peer device",
        "Supprimer cette liaison": "Delete this link",
        "port de l'appareil en face": "peer device port",
        "Liaison alimentée en PoE": "PoE-powered link",
        "Port en face :": "Peer port:",
        "Identité": "Identity",
        "Nom :": "Name:",
        "Hostname :": "Hostname:",
        "En ligne": "Online",
        "Passerelle Internet (accès box)": "Internet gateway (box access)",
        "Switch PoE qui alimente cet appareil. Renseigné = appareil "
        "PoE : son chemin reste en PoE jusqu'à ce switch, puis hors PoE.":
            "PoE switch that powers this device. Set = PoE device: its path "
            "stays PoE up to this switch, then non-PoE.",
        "Passerelle PoE :": "PoE gateway:",
        "Emplacement": "Location",
        "n° U (optionnel)": "U number (optional)",
        "Étage :": "Floor:",
        "Pièce :": "Room:",
        "Baie :": "Rack:",
        "Unité (U) :": "Unit (U):",
        "Liaisons": "Links",
        "Aucune liaison.": "No link.",
        "+ Ajouter une liaison": "+ Add a link",
        "Association Wi-Fi": "Wi-Fi association",
        "Point d'accès :": "Access point:",
        "Les modifications sont appliquées automatiquement.":
            "Changes are applied automatically.",
        "Supprimer le device": "Delete the device",
        " — manuel": " — manual",
        "IP invalide": "Invalid IP",
        "« {ip} » n'est pas une adresse IP valide ; valeur "
        "précédente conservée.":
            "« {ip} » is not a valid IP address; previous value kept.",
        "Liaison invalide": "Invalid link",
        "Supprimer « {name} » de la carte ?":
            "Remove « {name} » from the map?",
        # --- Ajouter un device ---
        "ex. : Switch garage": "e.g. Garage switch",
        "optionnel": "optional",
        "MAC invalide": "Invalid MAC",
        "MAC déjà présente": "MAC already present",
        "Un device avec la MAC {mac} existe déjà.":
            "A device with MAC {mac} already exists.",
        "« {ip} » n'est pas une adresse IP valide.":
            "« {ip} » is not a valid IP address.",
        # --- Diagnostics (dialogue) ---
        "Diagnostics réseau": "Network diagnostics",
        "Anomalies de câblage détectées. Double-cliquez une ligne pour "
        "sélectionner l'appareil concerné sur la carte.":
            "Cabling anomalies detected. Double-click a row to select the "
            "device on the map.",
        "Aucune anomalie détectée. ✓": "No anomaly detected. ✓",
        "Fermer": "Close",
        "● ERREUR": "● ERROR",
        "● ATTENTION": "● WARNING",
        "● INFO": "● INFO",
        # --- Rapport des chemins (dialogue) ---
        "Rapport des chemins réseau": "Network paths report",
        "Chemin physique de chaque appareil jusqu'à la passerelle "
        "Internet, hop par hop.\nLe parcours est non-directionnel et ne "
        "transite que par les appareils d'infrastructure (switch, patch "
        "panel, prise, routeur, AP).":
            "Physical path of each device to the Internet gateway, hop by "
            "hop.\nThe route is non-directional and only transits through "
            "infrastructure devices (switch, patch panel, outlet, router, AP).",
        "Copier": "Copy",
        "Exporter en .txt…": "Export to .txt…",
        "Exporter le rapport": "Export the report",
        "Fichier texte (*.txt)": "Text file (*.txt)",
        "Impossible d'écrire le fichier :\n{err}":
            "Could not write the file:\n{err}",
        "Export": "Export",
        "Rapport exporté vers\n{name}": "Report exported to\n{name}",
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
