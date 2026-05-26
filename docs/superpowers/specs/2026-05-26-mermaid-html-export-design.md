# Spec — Export Mermaid + HTML interactif

Date : 2026-05-26
Statut : validé (GO)

## A. Renderer Mermaid (`intramap/renderers/mermaid.py`)

`render(inv) -> str` :
- `flowchart TB`, sous-graphes imbriqués étage / pièce / baie (réutilise
  `_common.bucket`, même découpage que Graphviz/PlantUML). Hôtes non localisés
  sous un sous-graphe « Non localisé ».
- Nœuds : `hN["Nom<br/>IP<br/>MAC"]` (IDs `h1…` triés par MAC, comme les autres
  renderers). Labels échappés en entités HTML (`&` `"` `<` `>`).
- Liens issus de `inv.links` : `---` (filaire) ou `===` (PoE, trait épais),
  label `port_a↔port_b` via `_common.edge_label`, forme
  `a ===|"label"| b`. Wi-Fi : `a -.->|"Wi-Fi"| b`.
- Couleurs par type : `classDef <type> fill:<DEVICE_COLORS[type]>…;` puis
  `class <ids> <type>;`.
- Inventaire vide → `flowchart TB\n`.

## B. Renderer HTML interactif (`intramap/renderers/html.py`)

`render(inv) -> str` : page HTML autonome.
- Embarque **vis-network via CDN jsdelivr** ; `<div id="net">` plein écran.
- Nœuds/arêtes sérialisés avec `json.dumps(..., ensure_ascii=False)`
  (échappement sûr) injectés dans un gabarit via `str.replace` sur des
  marqueurs `__CDN__`/`__NODES__`/`__EDGES__` (pas `str.format`, à cause des
  accolades JS/CSS).
- Nœud : `{id, label (nom\nIP\nMAC), shape:"box", title (vendor — type),
  color}` ; hors-ligne → gris + texte estompé.
- Arête : `{from, to, label}` ; PoE → `color:#ff7f0e`, `width:3` ; Wi-Fi →
  `dashes:true`, couleur bleue.

## C. CLI

- `render --format` accepte `plantuml | graphviz | mermaid | html | all`.
- Refactor de `_cmd_render` : chaque format porte sa fonction de rendu dans le
  dictionnaire `targets` (Graphviz garde `copy_assets_to=out_dir`), au lieu du
  `if graphviz / else plantuml` actuel qui ne passait pas à l'échelle.
- Sorties : `network.mmd`, `network.html` (+ `network.puml`, `network.dot`).
  `all` produit les **quatre**.

## Tests

`tests/test_renderers_export.py` :
- mermaid : contient `flowchart TB` ; un nœud labellisé ; sous-graphe d'étage ;
  lien PoE `===` ; Wi-Fi `-.->` ; guillemets d'un nom échappés (`&quot;`) ;
  inventaire vide → `flowchart TB`.
- html : contient `<!DOCTYPE html>` et `vis-network` ; le JSON nœuds contient un
  hôte ; un nom avec guillemets/backslash ne casse pas le JSON
  (`json.loads` du bloc nœuds réussit) ; couleur PoE présente.

`tests/test_cli.py` :
- `render --format mermaid` → `network.mmd` créé et commence par `flowchart`.
- `render --format html` → `network.html` créé, contient `vis-network`.
- `render --format all` → les 4 fichiers présents.

## Fichiers

- Créer : `intramap/renderers/mermaid.py`, `intramap/renderers/html.py`,
  `tests/test_renderers_export.py`.
- Modifier : `intramap/cli.py`, `tests/test_cli.py`.
