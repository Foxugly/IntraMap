# IntraMap — Render Improvements (Design)

**Date :** 2026-05-25
**Auteur :** rvilain@foxugly.com
**Statut :** Design approuvé (issu de la conversation directe), prêt pour planification d'implémentation
**Spec parent :** [`2026-05-25-icons-and-manual-hosts-design.md`](2026-05-25-icons-and-manual-hosts-design.md)

## 1. But

Cinq améliorations visuelles cumulatives sur les renderers PlantUML et Graphviz, motivées par l'usage réel : un diagramme rendu sur un réseau maison de 20 hosts qui est encore peu lisible (graphe étalé, monochrome, sans légende, pas de Wi-Fi). Toutes les modifs sont rétrocompatibles avec les inventaires existants.

## 2. Portée

**Inclus — 5 features cumulatives :**

1. **Layout hiérarchique** : Graphviz `rankdir=TB; splines=ortho;`, PlantUML `top to bottom direction`. Arbre lisible (BBox en haut, leaves en bas).
2. **Couleur par catégorie** : 8 couleurs distinctes mappées aux 15 `device_type`. Fond coloré des nodes.
3. **Visualisation Wi-Fi** : nouveau champ `Host.wifi_ap_mac: str | None` indépendant de `uplink`. Arête pointillée vers l'AP référencé. Backward-compatible (défaut `None`).
4. **Légende automatique** : cluster `Légende` séparé en fin de diagramme, listant chaque `device_type` utilisé avec son icône, plus la sémantique des arêtes (wired / PoE / Wi-Fi).
5. **Labels plus propres + tooltips SVG (Graphviz)** : omission des hostnames null, IP/MAC en plus petit (HTML labels), attribut `tooltip` avec vendor + dates pour le hover SVG.

**Exclus (YAGNI) :**
- Détection automatique des associations Wi-Fi (le scan ne voit pas ça côté client)
- Multi-page / per-floor rendering
- Edge styling par vitesse de lien (Gbit, 10Gbit, etc.)
- Logos de marques
- Tooltips PlantUML (support natif limité, hors scope)

## 3. Feature 1 — Layout hiérarchique

**Graphviz** : insérer en tête du graphe, juste après `graph network {` :
```
  rankdir=TB;
  splines=ortho;
  nodesep=0.5;
  ranksep=0.8;
```

**PlantUML** : insérer juste après `@startuml` :
```
top to bottom direction
```

Aucun impact sur le modèle de données ou les autres features. Le layout devient déterministe et lisible : les hôtes sans uplink restent en haut/en bas selon la topologie déclarée.

## 4. Feature 2 — Couleur par catégorie

### 4.1 Table de couleurs (`DEVICE_COLORS`)

Définie dans `intramap/renderers/icons.py` (à côté de `PLANTUML_SPRITES`) :

| `device_type` | Couleur (hex) | Famille |
|---|---|---|
| `router` | `#1f77b4` | bleu — passerelle internet |
| `switch` | `#2ca02c` | vert — infra réseau |
| `ap` | `#2ca02c` | vert — infra réseau |
| `controller` | `#2ca02c` | vert — infra réseau |
| `nas` | `#9467bd` | violet — stockage |
| `tv` | `#ff7f0e` | orange — multimédia |
| `stb` | `#ff7f0e` | orange — multimédia |
| `phone` | `#7f7f7f` | gris — client mobile |
| `tablet` | `#7f7f7f` | gris — client mobile |
| `laptop` | `#7f7f7f` | gris — client mobile |
| `iot` | `#e377c2` | rose — domotique |
| `camera` | `#e377c2` | rose — domotique |
| `voip` | `#bcbd22` | olive — services |
| `printer` | `#bcbd22` | olive — services |
| `other` | `#cccccc` | gris clair — fallback |

### 4.2 Application

**PlantUML** : suffixe `#<color>` après la déclaration du node :
```
node "<$network_wired>\nBBox\n192.168.1.1" as h1 #1f77b4
```

**Graphviz** : attributs `fillcolor` et `style="filled"` par node. Combiné avec offline (`style="filled,dashed"`).
```
h1 [label="BBox\n192.168.1.1", image="icons/router.svg",
    labelloc=b, imagescale=true, fillcolor="#1f77b4", style=filled];
```

### 4.3 Interaction avec offline

- PlantUML : le stéréotype `<<offline>>` reste prioritaire visuellement (grisé). La couleur n'est pas appliquée aux nodes offline (préserve la lecture rapide).
- Graphviz : `style="filled,dashed"` combine remplissage de couleur ET bordure pointillée. La couleur reste visible mais atténuée par la bordure pointillée. Acceptable.

## 5. Feature 3 — Visualisation Wi-Fi

### 5.1 Nouveau champ `Host.wifi_ap_mac`

```python
@dataclass
class Host:
    # ... champs existants ...
    wifi_ap_mac: str | None = None  # MAC de l'AP associé (Wi-Fi), normalisée
```

Normalisation : dans `__post_init__`, si non-None, normalisée via `normalize_mac`.

### 5.2 Sémantique

- `wifi_ap_mac=None` : le host n'a pas de Wi-Fi déclaré (cas par défaut).
- `wifi_ap_mac="aa:bb:cc:dd:ee:ff"` : le host est associé à cet AP via Wi-Fi.
  - Si la MAC matche un host de l'inventaire → arête Wi-Fi tracée.
  - Sinon → silencieusement ignorée (même comportement que `uplink.switch_mac` inconnu).
- Un host peut avoir À LA FOIS `uplink` (Ethernet) et `wifi_ap_mac` (Wi-Fi de backup) → les deux arêtes sont dessinées.

### 5.3 Validation et round-trip

- `from_dict` valide : `wifi_ap_mac` doit être `str | None` (sinon `ValueError` avec MAC du host).
- `to_dict` inclut le champ.
- Backward compat : YAML sans le champ → défaut `None`.

### 5.4 Merge

Pas d'impact. Le champ est une annotation utilisateur (comme `custom_name`, `location`, `uplink`), donc préservé par le merge — déjà couvert par la logique « update discovery fields, preserve annotations » existante. À ajouter explicitement dans le docstring du merge.

### 5.5 Rendu

Arête pointillée bleue distincte des uplinks filaires :

**PlantUML** : `h2 ..> h1 : "Wi-Fi"` (`..>` est la flèche pointillée en PlantUML)

**Graphviz** : `h2 -- h1 [style=dashed, color="#1f77b4", label="Wi-Fi", fontsize=10];`

Tracée uniquement si `wifi_ap_mac` matche un host de l'inventaire (déduplication MAC normalisée).

### 5.6 Impact CLI

Aucune nouvelle colonne ni filtre. Le champ se documente dans `inventory.yaml`.

## 6. Feature 4 — Légende automatique

### 6.1 Structure

Cluster séparé `Légende` émis APRÈS toutes les arêtes, contenant :
- Un node par `device_type` **utilisé** dans l'inventaire (déduplication) — icône + nom du type
- Trois nodes de référence pour les styles d'arêtes :
  - `wired-ref` (carré quelconque) — `--` arête solide vers `wired-target` — label "wired"
  - `poe-ref` — arête orange épaisse vers `poe-target` — label "PoE"
  - `wifi-ref` — arête pointillée bleue vers `wifi-target` — label "Wi-Fi"

### 6.2 Émission

**PlantUML** :
```
package "Légende" {
  node "<$network_wired>\nrouter" as legend_router #1f77b4
  node "<$share_nodes>\nswitch" as legend_switch #2ca02c
  ...
  node "─── wired" as legend_wired
  node "━━━ PoE" as legend_poe
  node "─ ─ Wi-Fi" as legend_wifi
}
```

Pour la sémantique des arêtes, utiliser des labels texte (avec caractères Unicode) plutôt que des arêtes réelles entre nodes factices (plus simple à layout).

**Graphviz** :
```
subgraph cluster_legend {
  label="Légende";
  legend_router [label="router", image="icons/router.svg", labelloc=b,
                 fillcolor="#1f77b4", style=filled];
  ...
}
```

### 6.3 Position

Le cluster `Légende` est émis EN DERNIER, après toutes les autres clusters et arêtes. Avec `rankdir=TB` (Graphviz) ou `top to bottom direction` (PlantUML), il apparaît naturellement en bas du diagramme.

## 7. Feature 5 — Labels plus propres + tooltips SVG

### 7.1 Omission des champs null dans les labels

Actuellement le label est `name\nip\nmac` (3 lignes). Avec hostname=null, c'est pas une question — le hostname n'a JAMAIS été dans le label.

Mais : si `host.ip` est None (host manuel non scanné), on affiche "?" ou "-". Préférable : omettre la ligne IP entièrement.

Nouvelle logique de label :
```python
def _label_lines(host: Host) -> list[str]:
    """Build the non-empty label lines for a host."""
    name = host.custom_name or host.mac
    lines = [name]
    if host.ip:
        lines.append(host.ip)
    lines.append(host.mac)
    return lines
```

PlantUML utilise `"\\n".join(lines)` (déjà fait).
Graphviz idem.

### 7.2 HTML labels pour Graphviz (taille différenciée)

Remplacer le label texte simple par un HTML label permettant des tailles différentes par ligne :

```python
def _html_label(host: Host) -> str:
    name = _escape_html(host.custom_name or host.mac)
    parts = [f'<B>{name}</B>']
    if host.ip:
        parts.append(f'<FONT POINT-SIZE="10">{host.ip}</FONT>')
    parts.append(f'<FONT POINT-SIZE="9" COLOR="#666666">{host.mac}</FONT>')
    return "<" + "<BR/>".join(parts) + ">"
```

Node Graphviz devient :
```
h1 [label=<<B>BBox</B><BR/><FONT POINT-SIZE="10">192.168.1.1</FONT>...>,
    image="...", ...];
```

Note : les HTML labels Graphviz ne prennent pas de guillemets autour du label (entourage `< >`), à l'inverse du label texte (`"..."`)..

### 7.3 Tooltip SVG Graphviz

Attribut `tooltip` par node, visible au hover dans un viewer SVG :
```
h1 [..., tooltip="Sagemcom | last seen 2026-05-25"];
```

Tooltip content : `f"{vendor or 'unknown'} | last seen {host.last_seen.date()}"`.

### 7.4 PlantUML — pas de tooltips

PlantUML SVG output supporte les tooltips via `[[url{tooltip}]]` mais c'est lourd et pas un cas d'usage prioritaire. Hors scope cette itération.

## 8. Architecture

### 8.1 Nouveau / modifié

- `intramap/renderers/icons.py` : ajout de `DEVICE_COLORS: dict[str, str]`
- `intramap/models.py` : ajout du champ `Host.wifi_ap_mac` + validation + round-trip
- `intramap/renderers/plantuml.py` : intègre layout + couleurs + Wi-Fi edges + labels propres + légende
- `intramap/renderers/graphviz.py` : intègre layout + couleurs + Wi-Fi edges + HTML labels + tooltips + légende
- Tests : extensions test_models, test_renderers

### 8.2 Boundaries

- Pas de nouveau module (les ajouts s'insèrent dans les renderers existants).
- `_resolve_device_type` et `infer_device_type` continuent d'être la source unique pour la résolution.
- `DEVICE_COLORS` partagée par les deux renderers (single source of truth).
- La fonction `_label_lines` (text) reste dans chaque renderer (légèrement différente entre PlantUML et Graphviz HTML).

## 9. Gestion d'erreurs

| Frontière | Erreur | Comportement |
|---|---|---|
| `from_dict` | `wifi_ap_mac` typage incorrect | `ValueError` avec MAC + champ + valeur (pattern existant) |
| Rendu | `wifi_ap_mac` non vide pointe vers MAC inconnue | Silencieusement ignoré (idem `uplink.switch_mac`) |
| Rendu | `device_type` non dans `DEVICE_COLORS` | Fallback sur couleur `other` (`#cccccc`) |

## 10. Tests

### 10.1 Modèle (`tests/test_models.py`)

- `wifi_ap_mac` défaut None
- `wifi_ap_mac` normalisé via `__post_init__`
- Round-trip `to_dict`/`from_dict` avec et sans `wifi_ap_mac`
- Validation `wifi_ap_mac` type incorrect → ValueError
- Backward compat : YAML sans le champ charge proprement

### 10.2 Renderers (`tests/test_renderers.py`)

**Layout :**
- PlantUML output contient `top to bottom direction`
- Graphviz output contient `rankdir=TB` et `splines=ortho`

**Couleur :**
- PlantUML : node de type `nas` a `#9467bd` en suffixe
- PlantUML : offline host n'a PAS de couleur (stereotype prend le dessus)
- Graphviz : node a `fillcolor="#9467bd"` et `style="filled"`
- Graphviz : offline + couleur → `style="filled,dashed"`

**Wi-Fi :**
- PlantUML : arête `..>` avec label `"Wi-Fi"` quand `wifi_ap_mac` valide
- Graphviz : arête `style=dashed, color="#1f77b4", label="Wi-Fi"`
- Wi-Fi vers MAC inconnue → aucune arête
- Host avec BOTH uplink et wifi_ap_mac → 2 arêtes distinctes

**Légende :**
- PlantUML : présence du `package "Légende"`
- Graphviz : présence du `subgraph cluster_legend` (avec `label="Légende"`)
- Contient uniquement les device_types utilisés (dédupliqués)

**Labels propres :**
- Host sans IP → pas de ligne IP dans le label
- Graphviz utilise HTML labels (start with `<`, end with `>`, contains `<BR/>`)
- Graphviz a `tooltip="..."` par node avec vendor + last_seen

## 11. Hors-portée (futures itérations)

- Détection automatique Wi-Fi via scan (impossible côté client, demanderait l'accès au routeur/AP)
- Customisation utilisateur des couleurs (override via config)
- Multi-page rendering (un diagramme par étage)
- Tooltips PlantUML
- Edge styling par vitesse / media physique
