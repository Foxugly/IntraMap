"""Internationalisation légère (catalogue FR -> EN), **sans dépendance Qt**.

Le français est la langue **source** (les chaînes dans le code sont en
français). ``tr(text)`` renvoie la source en mode français, sinon la
traduction du catalogue (repli sur la source si absente — jamais d'exception).

Cœur partagé par le CLI, les builders de rapports et le GUI. La couche Qt
(préférence QSettings, menu de langue) vit dans :mod:`intramap.gui.i18n`.
"""
from __future__ import annotations

import locale

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
        "Langue appliquée": "Language applied",
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
        # --- Relier deux appareils ---
        "Relier deux appareils": "Connect two devices",
        "Toutes ces liaisons sont alimentées en PoE":
            "All these links are PoE-powered",
        "Appareil A :": "Device A:",
        "Appareil B :": "Device B:",
        "Remplir une plage de ports": "Fill a port range",
        "Ports A": "Ports A",
        "    Port B de départ": "    Starting port B",
        "Générer": "Generate",
        "+ Ligne": "+ Row",
        "− Ligne": "− Row",
        "Port côté {name}": "Port on {name} side",
        "{n} liaison(s) seront créées : {a} <-> {b}.":
            "{n} link(s) will be created: {a} <-> {b}.",
        "Sélection incomplète": "Incomplete selection",
        "Choisissez les deux appareils.": "Choose both devices.",
        "Même appareil": "Same device",
        "Les deux appareils doivent être différents.":
            "The two devices must be different.",
        "Aucune liaison": "No link",
        "Ajoutez au moins une paire de ports.": "Add at least one port pair.",
        # --- Ports (switch/outlet/patch panel) ---
        " — port {p}": " — port {p}",
        "  (PoE)": "  (PoE)",
        "Ports — {name}": "Ports — {name}",
        "Nombre de ports :": "Number of ports:",
        "Gris : libre   —   Vert : occupé   —   Orange : occupé (PoE)."
        "  Survolez un port pour voir ses liaisons. Le label éventuel "
        "apparaît entre crochets sous le numéro.":
            "Grey: free   —   Green: used   —   Orange: used (PoE)."
            "  Hover a port to see its links. Any label appears in brackets "
            "under the number.",
        "Labels des jacks — ex. n° du câble UTP dans le patch panel :":
            "Jack labels — e.g. UTP cable no. in the patch panel:",
        "Jack": "Jack",
        "Label": "Label",
        "Port {port}": "Port {port}",
        "{used} port(s) occupé(s), {free} libre(s) sur {count}.":
            "{used} port(s) used, {free} free out of {count}.",
        "Port {port} :": "Port {port}:",
        "Aucune liaison sur cet appareil.": "No link on this device.",
        "Attention : des liaisons utilisent des ports au-delà du nombre "
        "déclaré ({ports}). Augmentez le nombre de ports.":
            "Warning: some links use ports beyond the declared count "
            "({ports}). Increase the number of ports.",
        # --- Liste des devices ---
        "Liste des devices — Type / MAC / IP":
            "Device list — Type / MAC / IP",
        "Types affichés :": "Types shown:",
        "Nom": "Name",
        "Type": "Type",
        "Adresse MAC": "MAC address",
        "IP": "IP",
        "Exporter en CSV…": "Export to CSV…",
        "  (aucun type dans l'inventaire)  ":
            "  (no type in the inventory)  ",
        "Tout cocher": "Check all",
        "Tout décocher": "Uncheck all",
        "Tous les types ▾": "All types ▾",
        "Aucun type ▾": "No type ▾",
        "{n} / {total} types ▾": "{n} / {total} types ▾",
        "{shown} device(s)": "{shown} device(s)",
        "{shown} / {total} device(s)": "{shown} / {total} device(s)",
        "Exporter la liste en CSV": "Export the list to CSV",
        "Fichier CSV (*.csv)": "CSV file (*.csv)",
        "Impossible d'écrire le CSV :\n{err}":
            "Could not write the CSV:\n{err}",
        "Export CSV": "CSV export",
        "{n} device(s) exporté(s) vers\n{name}":
            "{n} device(s) exported to\n{name}",
        # --- Export PDF (dialogue d'options) ---
        "Tout sur une seule page": "All on one page",
        "Mosaique - 2 pages de large": "Mosaic - 2 pages wide",
        "Mosaique - 3 pages de large": "Mosaic - 3 pages wide",
        "Mosaique - 4 pages de large": "Mosaic - 4 pages wide",
        "Exporter en PDF": "Export to PDF",
        "Les proportions de la carte sont toujours conservees.\n"
        "Choisissez la taille de page et la repartition.":
            "The map proportions are always preserved.\n"
            "Choose the page size and layout.",
        "Taille de page :": "Page size:",
        "Répartition :": "Layout:",
        "Ajouter le detail des branchements\n"
        "(routeurs, switchs, patch panels, outlets)":
            "Add the wiring detail\n"
            "(routers, switches, patch panels, outlets)",
        "Ajoute, apres la carte, des pages texte qui listent pour chaque "
        "appareil d'infrastructure tous les ports utilises et l'appareil "
        "branche en face.":
            "Adds, after the map, text pages listing for each infrastructure "
            "device all the used ports and the device plugged in opposite.",
        "-> 1 page : la carte entiere, ajustee a la page.":
            "-> 1 page: the whole map, fitted to the page.",
        "-> {cols} x {rows} = {total} pages a assembler "
        "(meilleure lisibilite, qualite maximale).":
            "-> {cols} x {rows} = {total} pages to assemble "
            "(better readability, maximum quality).",
        # --- Cadres de groupe ---
        "Glisser l'en-tête pour déplacer tout l'étage":
            "Drag the header to move the whole floor",
        # --- Rapport de câblage (contenu) ---
        "Aucun appareil dans l'inventaire.": "No device in the inventory.",
        "Aucun appareil d'infrastructure (routeur, switch, patch panel, "
        "outlet) dans l'inventaire.":
            "No infrastructure device (router, switch, patch panel, outlet) "
            "in the inventory.",
        "Branchements des appareils d'infrastructure":
            "Infrastructure device wiring",
        "Routeur": "Router",
        "Outlet (prise murale)": "Outlet (wall jack)",
        "(aucun branchement)": "(no connection)",
        "port {p}": "port {p}",
        "(port ?)": "(port ?)",
        "PoE": "PoE",
        # --- Rapport des chemins (contenu) ---
        "Aucun appareil sur la carte.": "No device on the map.",
        "Wi-Fi": "Wi-Fi",
        "→ port {p}": "→ port {p}",
        "alimenté en PoE": "PoE-powered",
        "Passerelle Internet (accès box).": "Internet gateway (box access).",
        "aucun chemin PoE trouvé jusqu'à la passerelle Internet (PoE rompu, "
        "ou pas de chemin par les appareils d'infrastructure)":
            "no PoE path found to the Internet gateway (PoE broken, or no "
            "path through infrastructure devices)",
        "aucun chemin trouvé jusqu'à la passerelle Internet (pas de liaison "
        "vers un switch / patch panel qui y mène)":
            "no path found to the Internet gateway (no link to a switch / "
            "patch panel leading there)",
        "Accès Internet ✓": "Internet access ✓",
        "chemin partiel — «{prev}» n'atteint pas la passerelle Internet":
            "partial path — «{prev}» does not reach the Internet gateway",
        # --- Diagnostics (messages) ---
        "Câble en boucle sur un même appareil ({mac}).":
            "Cable looping on the same device ({mac}).",
        "Câble vers une MAC absente de l'inventaire : {macs}.":
            "Cable to a MAC missing from the inventory: {macs}.",
        "Aucune passerelle Internet déclarée (cochez « Passerelle Internet » "
        "sur la box).":
            "No Internet gateway declared (check « Internet gateway » on the "
            "box).",
        "« {name} » n'atteint aucune passerelle Internet.":
            "« {name} » does not reach any Internet gateway.",
        "Port {p} de « {name} » (patch panel) : {c} câbles "
        "(2 max en pass-through).":
            "Port {p} of « {name} » (patch panel): {c} cables "
            "(2 max in pass-through).",
        "Port {p} de « {name} » : {c} câbles branchés (un seul attendu).":
            "Port {p} of « {name} »: {c} cables plugged in (only one "
            "expected).",
        "« {name} » est associé en Wi-Fi à une MAC inconnue ({ap}).":
            "« {name} » is Wi-Fi-associated to an unknown MAC ({ap}).",
        "« {name} » est associé en Wi-Fi à « {peer} », qui n'est pas un "
        "point d'accès.":
            "« {name} » is Wi-Fi-associated to « {peer} », which is not an "
            "access point.",
        # --- Diff de scan (contenu) ---
        "Nouveaux ({n}) :": "New ({n}):",
        "Passés hors ligne ({n}) :": "Gone offline ({n}):",
        "Revenus en ligne ({n}) :": "Back online ({n}):",
        "IP modifiée ({n}) :": "IP changed ({n}):",
        "Aucun changement depuis le dernier scan.":
            "No change since the last scan.",
        # --- Messages du CLI ---
        "Fichier d'inventaire introuvable : {path}":
            "Inventory file not found: {path}",
        "Lancez d'abord `intramap scan` pour en créer un.":
            "Run `intramap scan` first to create one.",
        "Échec du chargement de l'inventaire {path} :\n{err}":
            "Failed to load inventory {path}:\n{err}",
        "Écrit : {path}": "Wrote {path}",
        "Avertissement : « dot » (Graphviz) introuvable dans le PATH. "
        "Rendu image ignoré. Installez depuis https://graphviz.org/download/ "
        "ou lancez `dot` manuellement depuis {dir}.":
            "Warning: 'dot' (Graphviz) not found in PATH. Skipping image "
            "rendering. Install from https://graphviz.org/download/ or run "
            "`dot` manually from {dir}.",
        "Échec de dot pour {fmt} : {err}": "dot failed for {fmt}: {err}",
        "--format csv n'est possible que pour le rapport « wiring ».":
            "--format csv is only supported for the 'wiring' report.",
        "Aucune anomalie détectée.": "No anomaly detected.",
        "ERREUR": "ERROR",
        "ATTENTION": "WARNING",
        "INFO": "INFO",
        "{n} anomalie(s) détectée(s).": "{n} anomaly(ies) detected.",
        "Aucun sous-réseau IPv4 local détecté. Passez --network "
        "explicitement.":
            "No local IPv4 subnet detected. Pass --network explicitly.",
        "Plusieurs sous-réseaux locaux détectés :":
            "Multiple local subnets detected:",
        "Passez --network <CIDR> explicitement.":
            "Pass --network <CIDR> explicitly.",
        "Sous-réseau auto-détecté : {network}":
            "Auto-detected subnet: {network}",
        "Échec du chargement de l'inventaire existant {path} :\n{err}":
            "Failed to load existing inventory {path}:\n{err}",
        "Corrigez le fichier (ou supprimez-le pour repartir de zéro) puis "
        "relancez.":
            "Fix the file (or remove it to start fresh) and re-run.",
        "Scan terminé : {n} détecté(s) ({new} nouveau(x)), {off} hors ligne, "
        "{unn} sans nom personnalisé.":
            "Scan complete: {n} discovered ({new} new), {off} offline, "
            "{unn} without custom name.",
        "Inventaire : {path}": "Inventory: {path}",
        "Avertissement : le scan n'a retourné aucun hôte. Sur macOS/Linux, "
        "la découverte MAC (ARP) nécessite `sudo`. Sur Windows, lancez le "
        "terminal en administrateur.":
            "Warning: scan returned zero hosts. On macOS/Linux, MAC discovery "
            "(ARP) requires `sudo`. On Windows, run the terminal as "
            "administrator.",
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


def resolve_system_language() -> str:
    """Mappe la locale système vers ``fr`` (préfixe « fr ») ou ``en``."""
    try:
        code = (locale.getlocale()[0] or "")
    except (ValueError, TypeError):
        code = ""
    return "fr" if code.lower().startswith("fr") else "en"
