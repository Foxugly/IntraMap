# IntraMap — Icônes et hosts manuels (Design)

**Date :** 2026-05-25
**Auteur :** rvilain@foxugly.com
**Statut :** Design approuvé, prêt pour planification d'implémentation
**Spec parent :** [`2026-05-24-intramap-design.md`](2026-05-24-intramap-design.md)

## 1. But

Enrichir le rendu IntraMap en attachant une icône à chaque host (au lieu d'une simple boîte texte), et permettre d'inclure dans l'inventaire des appareils que le scan ne peut pas voir (switches non managés, sans IP), sans que ces entrées soient écrasées ou marquées `offline` à chaque scan.

## 2. Portée

**Inclus :**
- Nouveau champ `Host.device_type: str | None` — catégorie d'appareil (router, switch, ap, nas, tv, etc.)
- Nouveau champ `Host.manual: bool` — entrée gérée à la main, exemptée du cycle merge/discover
- Catalogue figé de 15 valeurs `device_type` avec icône FontAwesome 6 associée
- Auto-détection du `device_type` depuis le `vendor` au moment du rendu (table de patterns substring)
- Override manuel : `device_type` rempli explicitement dans le YAML écrase l'auto-détection
- Rendu PlantUML avec sprites FontAwesome 6 (via stdlib intégrée, pas d'asset externe)
- Rendu Graphviz avec icônes PNG bundlées dans le package, copiées dans `<output_dir>/icons/` au rendu
- Logique de merge : les hosts `manual: true` ne sont pas modifiés ni marqués offline par les scans
- Colonne `Type` et filtre `--type` dans `intramap list`
- Round-trip YAML des deux nouveaux champs, backward-compatible avec inventaires existants

**Exclus (YAGNI) :**
- Logos de marques (Synology, Sagemcom, etc.)
- Couleur par catégorie d'icône
- Icône par host via chemin de fichier custom (override uniquement via catalogue)
- SVG (PNG suffit pour `dot -Tpng` et `dot -Tsvg`)
- Auto-détection à partir d'autres signaux (hostname, ports ouverts, OS fingerprint)

## 3. Modèle de données

### 3.1 Nouveaux champs sur `Host`

```python
@dataclass
class Host:
    # ... champs existants (mac, ip, hostname, vendor, custom_name,
    # location, uplink, first_seen, last_seen, online) ...
    device_type: str | None = None  # catégorie de l'appareil, ex "router"
    manual: bool = False             # True = entrée éditée à la main
```

### 3.2 Sémantique

- **`device_type=None`** (défaut) : au rendu, le renderer appelle `infer_device_type(host.vendor)`. Si le vendor matche un pattern de la table 3.4, le type inféré est utilisé ; sinon → `"other"`.
- **`device_type="<value>"`** : utilisé tel quel, écrase toute auto-détection. Si la valeur n'est pas dans le catalogue 3.3, fallback silencieux vers `"other"` au rendu (pas d'erreur).
- **`manual=False`** (défaut) : comportement actuel — le merge met à jour `ip/hostname/vendor/last_seen` au scan suivant et marque `online=False` si absent.
- **`manual=True`** : le merge **ignore complètement** ce host à toutes les étapes (pas d'update, pas de marquage offline). Pour resynchroniser une entrée avec le scanner, il faut retirer `manual: true` à la main.

### 3.3 Catalogue des `device_type` (15 valeurs)

| `device_type` | Icône FontAwesome 6 | Usage type |
|---|---|---|
| `router` | `network_wired` | Box internet, gateway |
| `switch` | `share_nodes` | Switch managé ou non |
| `ap` | `wifi` | Point d'accès Wi-Fi |
| `controller` | `sliders` | Contrôleur Wi-Fi (Omada, UniFi) |
| `nas` | `hard_drive` | NAS, stockage réseau |
| `tv` | `tv` | Téléviseur |
| `stb` | `clapperboard` | Set-top box, décodeur |
| `phone` | `mobile_screen_button` | Smartphone |
| `tablet` | `tablet_screen_button` | Tablette |
| `laptop` | `laptop` | Laptop / PC |
| `iot` | `house_signal` | Domotique, capteurs |
| `camera` | `video` | Caméra IP, vidéophone |
| `printer` | `print` | Imprimante réseau |
| `voip` | `phone_volume` | Téléphone IP, ATA |
| `other` | `question` | Inconnu / fallback |

### 3.4 Table d'auto-détection (`infer_device_type`)

Patterns case-insensitive en substring sur `vendor`. Première règle qui matche gagne. Aucun match → renvoie `None` (le renderer transforme en `"other"`).

| Patterns vendor | → `device_type` |
|---|---|
| `sagemcom`, `vantiva`, `technicolor`, `arris` | `router` |
| `synology`, `qnap`, `western digital`, `seagate` | `nas` |
| `cisco`, `juniper`, `aruba`, `mikrotik`, `netgear` | `switch` |
| `tp-link`, `ubiquiti`, `unifi` | `ap` |
| `lg electronics`, `samsung electronics`, `sony`, `philips` | `tv` |
| `apple`, `google`, `xiaomi`, `huawei`, `oneplus` | `phone` |
| `hikvision`, `dahua`, `axis`, `bticino` | `camera` |
| `intel corporate`, `dell`, `lenovo`, `asus`, `hp inc`, `universal global scientific` | `laptop` |
| `tuya`, `tado`, `nest`, `ring`, `philips hue`, `eedomus`, `davicom` | `iot` |
| `grandstream`, `yealink`, `polycom`, `snom` | `voip` |
| `canon`, `epson`, `brother industries` | `printer` |
| (aucun match) | `None` → rendu en `other` |

**Note d'ambiguïté** : « Samsung Electronics » → `tv` mais « Samsung » seul → `phone`. C'est l'utilisateur qui tranche via override.

### 3.5 Résolution finale (`_resolve_device_type`)

Helper interne utilisé par les deux renderers :

```python
def _resolve_device_type(host: Host) -> str:
    """Return the device_type to render for this host.

    Priority: explicit host.device_type > auto-inferred from vendor > 'other'.
    Values not in the catalogue silently fall back to 'other'.
    """
    if host.device_type and host.device_type in DEVICE_TYPES:
        return host.device_type
    if host.device_type:  # value exists but not in catalogue
        return "other"
    inferred = infer_device_type(host.vendor)
    return inferred or "other"
```

## 4. Comportement du merge

### 4.1 Règles (mises à jour par rapport à la spec parent)

| Situation | Action |
|---|---|
| Host avec `manual=True` | **Ignoré complètement** par le merge. Aucun champ touché, ni `online`. |
| MAC découverte non présente dans l'inventaire | Inchangé : ajout avec `device_type=None`, `manual=False`, autres défauts. |
| MAC découverte déjà présente, `manual=False` | Inchangé : update `ip/hostname/vendor/last_seen`, préserve annotations. |
| MAC présente dans l'inventaire mais absente du scan, `manual=False` | Inchangé : `online=False`. |

### 4.2 Cas limite : MAC manuelle qui apparaît au scan

Un host avec `manual=True` dont la MAC apparaît dans la liste découverte par le scanner : le merge **ne le met pas à jour** non plus. L'utilisateur a explicitement pris le contrôle de cette entrée. Pour rebasculer en gestion automatique, il retire `manual: true` du YAML.

Rationale : l'inverse (un scan qui écrase une saisie manuelle) serait surprenant et destructeur. Le flag est binaire et explicite.

## 5. Format YAML

### 5.1 Backward compatibility

Les YAML existants sans les nouveaux champs se chargent avec `device_type=None` et `manual=False`. Le `save()` qui suit réécrit le YAML en incluant les nouveaux champs avec ces défauts.

### 5.2 Exemple

```yaml
hosts:
  # Host vu par le scan, avec catégorie auto-inférée (device_type vide)
  00:11:32:41:bb:85:
    ip: 192.168.1.10
    hostname: null
    vendor: Synology Incorporated
    custom_name: NAS Synology
    location: {floor: cave, room: cave technique, rack: baie principale, rack_unit: 1}
    uplink:
      switch_mac: aa:aa:aa:11:11:11
      switch_port: 3
      patch_port: null
      poe: false
    device_type: null              # → auto-détecté en "nas"
    manual: false
    first_seen: 2026-05-25T00:00:00
    last_seen: 2026-05-25T00:00:00
    online: true

  # Host scanné mais override de l'auto-détection (TP-Link → 'ap' par défaut, on force 'controller')
  ac:15:a2:e1:4c:e8:
    ip: 192.168.1.4
    hostname: null
    vendor: TP-Link Systems
    custom_name: Controleur Omada
    location: {floor: cave, room: cave technique, rack: baie principale, rack_unit: 4}
    uplink: null
    device_type: controller        # override explicite
    manual: false
    first_seen: 2026-05-25T00:00:00
    last_seen: 2026-05-25T00:00:00
    online: true

  # Switch non managé ajouté à la main (jamais vu par nmap)
  aa:aa:aa:11:11:11:
    ip: null
    hostname: null
    vendor: null
    custom_name: Switch principal
    location: {floor: cave, room: cave technique, rack: baie principale, rack_unit: 5}
    uplink:
      switch_mac: 38:e1:f4:85:aa:42
      switch_port: null
      patch_port: null
      poe: false
    device_type: switch
    manual: true                   # exempté du marquage offline par les scans
    first_seen: 2026-05-25T00:00:00
    last_seen: 2026-05-25T00:00:00
    online: true
```

## 6. Rendu

### 6.1 PlantUML

PlantUML embarque FontAwesome 6 dans sa stdlib. Le renderer fonctionne en deux passes :

1. **Collecte des types utilisés** : pour chaque host, calculer `_resolve_device_type(host)` ; dédupliquer.
2. **Émission** :
   - Au début du fichier, après `@startuml` et `skinparam`, émettre un `!include <font-awesome-6/<sprite>>` pour chaque sprite utilisé (ordre lexicographique).
   - Pour chaque node : `node "<$<sprite>>\n<label>" as h<id>` (sprite préfixé en première ligne du label, suivi du `\n<label>` existant).

Exemple :
```
@startuml
skinparam node<<offline>> {
  BackgroundColor #DDDDDD
  BorderColor #888888
}
!include <font-awesome-6/hard_drive>
!include <font-awesome-6/network_wired>
!include <font-awesome-6/wifi>

package "cave" {
  package "cave technique" {
    package "baie principale" {
      node "<$network_wired>\nBBox Proximus\n192.168.1.1\n38:e1:f4:85:aa:42" as h1
      node "<$hard_drive>\nNAS Synology\n192.168.1.10\n00:11:32:41:bb:85" as h2
    }
  }
}
package "Rez-de-chaussée" {
  package "couloir" {
    node "<$wifi>\nAccess Point RDC\n192.168.1.6\nac:15:a2:de:bd:84" as h3
  }
}

h2 -- h1
h3 -[#orange,thickness=2]- h1 : "sw:1 PoE"
@enduml
```

Offline : le stéréotype `<<offline>>` existant continue à fonctionner (grisé, l'icône reste visible).

### 6.2 Graphviz

Pas de sprite intégré → on bundle les PNG et on les copie au rendu.

**Bundling** : `intramap/renderers/icons/<type>.png` pour les 15 types (FontAwesome Free 6, ~2 KB par fichier, ~30 KB total). Inclure également `intramap/renderers/icons/LICENSE` (CC BY 4.0).

**Au rendu** :
1. Collecter les types utilisés (même logique que PlantUML).
2. Créer `<output_dir>/icons/` si besoin.
3. Copier `<package>/renderers/icons/<type>.png` → `<output_dir>/icons/<type>.png` pour chaque type utilisé.
4. Émettre les nodes avec :
   ```
   h1 [label="<label>", image="icons/<type>.png", labelloc="b", imagescale=true, shape=box];
   ```
5. Pour offline : ajouter `style=dashed, color="#888888"`.

Le chemin `image="icons/<type>.png"` est relatif au fichier `.dot` → le résultat est portable tant qu'on conserve `network.dot` et son dossier `icons/` ensemble.

### 6.3 Arbre de sortie après `intramap render`

```
output/
├── network.puml         # autonome (sprites résolus par PlantUML)
├── network.dot
└── icons/               # créé/maintenu par le renderer
    ├── router.png
    ├── nas.png
    ├── ap.png
    └── ...              # uniquement les icônes des types présents
```

Les anciens fichiers `icons/*.png` d'un rendu précédent restent en place (pas de nettoyage agressif). Acceptable car ils ne perturbent pas Graphviz.

## 7. Impact CLI

### 7.1 `intramap list`

Nouvelle colonne `Type` insérée entre `Name` et `Vendor`. La valeur affichée est le résultat de `_resolve_device_type(host)` (donc auto-inférée si vide).

### 7.2 Filtre `--type`

```
intramap list --type ap            # tous les access points
intramap list --type switch        # tous les switches
intramap list --type other         # hosts non catégorisés (à annoter)
```

Sémantique : match exact (pas de substring), case-insensitive. Comparaison contre le `device_type` résolu (déclaré OU inféré OU `other`). Composable avec `--vendor`, `--offline`, `--unnamed`.

### 7.3 `intramap render`

Aucun changement de surface CLI. Les flags existants (`--format`, `--output-dir`) restent. Le renderer produit en plus le dossier `icons/` quand le format Graphviz est demandé.

## 8. Gestion d'erreurs

| Frontière | Erreur | Comportement |
|---|---|---|
| Chargement YAML | `device_type` ou `manual` typage incorrect | `Host.from_dict` valide : `device_type` doit être `str | None`, `manual` doit être `bool`. Sinon `ValueError` avec MAC + champ + valeur (pattern identique à l'erreur uplink déjà en place). |
| Copie d'icônes Graphviz | Fichier source manquant dans le package | Erreur claire au render : « Icon file missing: <path>. Reinstall the package. » exit code 4 (cohérent avec autres erreurs de rendu). |
| Copie d'icônes Graphviz | `<output_dir>/icons/` non writable | Erreur claire au render, exit code 4. |

## 9. Tests

Stratégie : tests unitaires aux frontières, comme le reste du projet.

### 9.1 Modules

- **`tests/test_models.py`** (extensions) :
  - `infer_device_type` : matches connus, miss → None, case-insensitivity, substring match.
  - `_resolve_device_type` : explicit > inferred > 'other', invalid explicit → 'other'.
  - Host round-trip : `device_type=None`, `device_type="ap"`, `manual=True/False`.
  - Backward compat : YAML sans les nouveaux champs charge avec les défauts corrects.
- **`tests/test_inventory.py`** (extensions) :
  - Merge ignore les hosts `manual=True` (pas d'update, pas d'offline).
  - Merge sur un host `manual=True` dont la MAC est dans le scan : aucun changement.
- **`tests/test_renderers.py`** (extensions PlantUML + Graphviz) :
  - PlantUML : `!include` émis pour les sprites utilisés, dédupliqués, ordre lexicographique.
  - PlantUML : node label commence par `<$sprite>`.
  - PlantUML : un type non-catalogue dans le YAML → fallback sur `<$question>`.
  - Graphviz : node a l'attribut `image="icons/<type>.png"`.
  - Graphviz : avec offline → `style=dashed` ET image toujours présente.
  - Graphviz : `copy_icons_to(output_dir, types)` crée le sous-dossier et les bons fichiers.
- **`tests/test_cli.py`** (extensions) :
  - `list` affiche la colonne `Type`.
  - `list --type ap` filtre correctement (sur device_type résolu).
  - `render` Graphviz crée `output/icons/` avec uniquement les icônes nécessaires.

### 9.2 Pas de tests d'intégration

Les renderers sont testés sur le texte produit (assertions sur le `.puml`/`.dot`). Aucun test ne lance PlantUML ou `dot` — on fait confiance à la sortie.

## 10. Licence et attribution

Les icônes proviennent de [FontAwesome Free 6](https://fontawesome.com/), licence **CC BY 4.0**.

- Le texte de la licence est ajouté à `intramap/renderers/icons/LICENSE`.
- Le README mentionne : « Icons by [Font Awesome](https://fontawesome.com/), licensed under CC BY 4.0. »

## 11. Hors-portée (futurs travaux possibles)

- Logos réels des fabricants (Synology, Sagemcom, etc.) — assets lourds, licence à vérifier marque par marque
- Couleur par catégorie pour visibilité accrue
- Icône custom par host (chemin de fichier dans le YAML)
- Détection du `device_type` à partir d'autres signaux (hostname patterns, ports ouverts via `nmap -sV`)
- SVG en plus du PNG si `dot -Tsvg` veut des icônes vectorielles natives
- Validation stricte du catalogue : refuser un `device_type` non listé au load (actuellement fallback silencieux)
