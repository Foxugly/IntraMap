# Spec — Recherche / filtre sur le canvas

Date : 2026-05-26
Statut : validé (GO)

## Objectif

Une barre de recherche (texte libre) qui met en évidence les appareils
correspondants sur la carte en estompant les autres, et centre la vue sur le
premier résultat avec Entrée.

## Correspondance (fonction pure)

`intramap/gui/canvas.py` : `node_matches(host, query) -> bool`.
- Requête vide -> `True` (tout correspond, aucun filtre).
- Sinon : la requête (minuscules, trim) est cherchée comme sous-chaîne dans
  `custom_name`, `hostname`, `ip`, `mac`, `_resolve_device_type(host)`,
  `location.floor`, `location.room` (champs `None` ignorés), insensible à la
  casse.

## Canvas (`MapView`)

- `DeviceNode.set_dimmed(dimmed: bool)` : `setOpacity(0.25 if dimmed else 1.0)`.
- `MapView.filter_nodes(query) -> int` : pour chaque nœud, estompe s'il ne
  correspond pas (requête non vide) ; renvoie le nombre de correspondances.
  Requête vide -> tout ré-affiché plein.
- `MapView.center_on_first_match(query)` : centre la vue sur le premier nœud
  correspondant (ordre MAC), no-op si requête vide / aucun résultat.

## UI

- Un `QLineEdit` dans la barre d'outils (placeholder « Rechercher… », bouton
  d'effacement). `textChanged` -> `filter_nodes` + compte dans la barre de
  statut ; `returnPressed` -> `center_on_first_match`.

## Tests

`tests/test_gui.py` :
- `node_matches` : nom, IP, MAC, type, étage ; vide -> True ; insensible à la
  casse ; non-correspondance -> False.
- `MapView.filter_nodes("switch")` : le switch reste opaque (1.0), les autres
  estompés (<1.0) ; requête vide -> tout à 1.0 ; nombre renvoyé correct.
- `center_on_first_match` ne lève pas.

## Fichiers

- Modifier : `intramap/gui/canvas.py`, `intramap/gui/node.py`,
  `intramap/gui/main_window.py`, `tests/test_gui.py`.

## Hors périmètre (v1)

Réapplication automatique du filtre après un rechargement du canvas (ajout de
device, etc.) ; l'utilisateur réinteragit avec le champ si besoin.
