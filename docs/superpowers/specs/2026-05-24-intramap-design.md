# IntraMap — Design

**Date :** 2026-05-24
**Auteur :** rvilain@foxugly.com
**Statut :** Design approuvé, prêt pour planification d'implémentation

## 1. But

IntraMap scanne un réseau IPv4 local, en extrait les appareils (IP, MAC, hostname, vendor), et produit un schéma de l'infrastructure regroupé par localisation physique (étage > pièce > baie). L'utilisateur enrichit l'inventaire automatiquement détecté en éditant un fichier YAML pour ajouter un nom personnalisé et la localisation de chaque appareil.

## 2. Portée

**Inclus :**
- Scan d'un subnet IPv4 (auto-détecté ou passé en argument)
- Identification des appareils par adresse MAC (clé stable même si l'IP change)
- Récupération IP, MAC, hostname (DNS/NetBIOS), vendor (OUI MAC)
- Fichier YAML d'inventaire éditable à la main, versionnable git
- Merge intelligent entre scans : annotations préservées, nouveaux appareils signalés, appareils absents marqués `offline`
- Génération de schémas PlantUML et Graphviz (DOT) en parallèle
- Regroupement visuel par étage > pièce > baie ; appareils sans localisation dans un groupe « non localisé »
- CLI avec sous-commandes `scan`, `render`, `list`

**Exclus :**
- IPv6
- Topologie L2 (qui-est-branché-où via SNMP)
- Scan inter-subnet, VLAN
- Interface web / GUI
- Rendu image (PNG/SVG) intégré : on génère seulement les fichiers texte `.puml` et `.dot` ; l'utilisateur les rend avec ses propres outils
- Historique des changements (peut être ajouté plus tard, hors v1)

## 3. Contexte cible

Réseau domestique ou petit bureau : moins de 30 appareils, un seul subnet, pas de VLAN, équipements mixtes (PC, smartphones, IoT, switches, NAS). L'utilisateur installe `nmap` séparément et lance les commandes avec des privilèges admin lorsque c'est nécessaire pour l'ARP scan.

## 4. Architecture

### 4.1 Structure des modules

```
intramap/
├── intramap/
│   ├── __init__.py
│   ├── scanner.py        # Wrapper python-nmap → liste de DiscoveredHost
│   ├── inventory.py      # Charge/sauve inventory.yaml + merge intelligent
│   ├── models.py         # Dataclasses : Host, Location, Inventory, DiscoveredHost
│   ├── renderers/
│   │   ├── __init__.py
│   │   ├── plantuml.py   # Inventory → texte .puml
│   │   └── graphviz.py   # Inventory → texte .dot
│   └── cli.py            # Point d'entrée argparse : scan, render, list
├── inventory.yaml        # Fichier d'inventaire édité à la main (versionné git)
├── output/
│   ├── network.puml
│   └── network.dot
├── tests/
├── pyproject.toml
└── README.md
```

### 4.2 Isolation des responsabilités

- **`scanner`** : connaît uniquement le réseau et nmap. Retourne des objets bruts. Ne lit ni n'écrit l'inventaire.
- **`inventory`** : gère le format YAML et la logique de merge. Ne sait rien du scan ni du rendu.
- **`renderers/*`** : transforment un `Inventory` en texte. Ne touchent ni au réseau ni au disque (le `cli` écrit le fichier).
- **`cli`** : orchestre les trois, gère les arguments et les messages utilisateur.

Chaque module est testable en isolation : le scanner avec un mock de `nmap.PortScanner`, les renderers avec un `Inventory` factice, `inventory.merge` en pur unit-test.

## 5. Modèle de données

### 5.1 Dataclasses (`models.py`)

```python
@dataclass
class Location:
    floor: str | None = None      # "RDC", "1er", "sous-sol"...
    room:  str | None = None      # "bureau", "salon", "local technique"
    rack:  str | None = None      # "baie-A", None si appareil non racké
    rack_unit: int | None = None  # position U dans la baie, optionnel

@dataclass
class DiscoveredHost:
    """Résultat brut d'un scan, avant intégration à l'inventaire."""
    mac: str            # toujours normalisée : lowercase, ':' comme séparateur
    ip: str
    hostname: str | None
    vendor: str | None

@dataclass
class Host:
    mac: str                        # clé d'identité, normalisée
    ip: str | None                  # dernière IP vue
    hostname: str | None            # nom DNS/NetBIOS découvert
    vendor: str | None              # depuis OUI de la MAC
    custom_name: str | None = None  # nom donné par l'utilisateur
    location: Location = field(default_factory=Location)
    first_seen: datetime            # auto à la première détection
    last_seen: datetime             # mis à jour à chaque scan où on le revoit
    online: bool = True             # False si absent du dernier scan

@dataclass
class Inventory:
    hosts: dict[str, Host]          # clé = MAC normalisée
    last_scan: datetime
```

### 5.2 Identité

L'**adresse MAC** est la clé d'identité d'un appareil :
- L'IP peut changer (DHCP, déplacement entre subnets)
- Le hostname peut changer (renommage, ou absent)
- La MAC est stable pour une carte réseau donnée

Conséquence : un appareil avec deux interfaces (filaire + Wi-Fi) apparaîtra comme **deux entrées distinctes**. Acceptable en v1 ; un mécanisme de regroupement pourra être ajouté plus tard.

### 5.3 Normalisation MAC

Toutes les MAC sont stockées et comparées en :
- lowercase
- séparateur `:` (pas `-` ni format compact)

Exemple : `AA-BB-CC-DD-EE-01` → `aa:bb:cc:dd:ee:01`.

Normalisation appliquée :
- à la sortie du scanner
- au chargement YAML (tolère que l'utilisateur ait édité avec une autre casse/séparateur)

### 5.4 Exemple de fichier `inventory.yaml`

```yaml
last_scan: 2026-05-24T14:30:00
hosts:
  aa:bb:cc:dd:ee:01:
    ip: 192.168.1.1
    hostname: livebox.home
    vendor: Sagemcom
    custom_name: Box internet
    location: {floor: RDC, room: salon, rack: null, rack_unit: null}
    first_seen: 2026-05-01T10:00:00
    last_seen: 2026-05-24T14:30:00
    online: true
  aa:bb:cc:dd:ee:02:
    ip: 192.168.1.10
    hostname: null
    vendor: Cisco
    custom_name: Switch principal
    location: {floor: sous-sol, room: local-tech, rack: baie-A, rack_unit: 12}
    first_seen: 2026-05-01T10:00:00
    last_seen: 2026-05-24T14:30:00
    online: true
```

## 6. Comportement du merge

Quand un scan produit une liste de `DiscoveredHost` et qu'il existe un `inventory.yaml` :

| Situation | Action |
|---|---|
| MAC découverte non présente dans l'inventaire | Ajout d'un `Host` avec `custom_name=None`, `location=Location()`, `first_seen=last_seen=now`, `online=true` |
| MAC découverte déjà présente | Mise à jour de `ip`, `hostname`, `vendor`, `last_seen=now`, `online=true`. **Préserve** `custom_name`, `location`, `first_seen` |
| MAC présente dans l'inventaire mais absente du scan | `online=false`. Aucun autre champ modifié |

Le champ `last_scan` de l'`Inventory` est mis à jour à chaque scan.

## 7. Flux de données

### 7.1 Commande `scan`

1. Auto-détection du subnet local (via `psutil` sur l'interface par défaut) si `--network` non fourni
2. `scanner.scan(network)` lance nmap en mode ARP/ping sweep, retourne `list[DiscoveredHost]`
3. `inventory.load("inventory.yaml")` → `Inventory` (vide si fichier absent)
4. `inventory.merge(discovered)` applique les règles de la section 6
5. `inventory.save("inventory.yaml")` écrit avec hosts triés par MAC (diff git lisible)
6. Affichage d'un résumé : `N appareils trouvés (X nouveaux, Y offline), Z sans custom_name`

### 7.2 Commande `render`

1. `inventory.load("inventory.yaml")`
2. Pour chaque format demandé (par défaut tous) :
   - Le renderer regroupe les hosts par `location.floor` → `location.room` → `location.rack`
   - Hosts sans `floor` (ou tout vide) vont dans un groupe spécial **« non localisé »**
   - Hosts avec `online=false` sont marqués visuellement (style pointillé/grisé selon le format)
3. Écriture des fichiers `output/network.puml` et `output/network.dot`

### 7.3 Commande `list`

Affiche l'inventaire en table console (colonnes : MAC, IP, hostname, custom_name, localisation, online).
Flags :
- `--offline` : filtre `online=false`
- `--unnamed` : filtre `custom_name=None` (utile pour savoir quoi éditer)

### 7.4 Exemple de sortie PlantUML

```
@startuml
package "RDC" {
  package "Salon" {
    node "Box internet\n192.168.1.1\naa:bb:cc:dd:ee:01" as h1
  }
}
package "Sous-sol" {
  package "Local technique" {
    package "Baie-A" {
      node "Switch principal\n192.168.1.10\naa:bb:cc:dd:ee:02" as h2
    }
  }
}
package "Non localisé" {
  node "?\n192.168.1.50\naa:bb:cc:dd:ee:99" as h3
}
@enduml
```

### 7.5 Pas de topologie L2 inférée

Le diagramme représente un **regroupement par localisation physique** déclarée par l'utilisateur, pas une topologie réseau découverte. On ne tente pas de déterminer quel appareil est branché sur quel port de quel switch (cela nécessiterait du SNMP sur les switches managés, hors portée).

## 8. CLI

```bash
# Scanner, merger dans inventory.yaml (créé s'il n'existe pas)
intramap scan
intramap scan --network 192.168.1.0/24

# Générer les diagrammes
intramap render                       # tous les formats → output/
intramap render --format plantuml     # un seul format

# Afficher l'inventaire en console
intramap list
intramap list --offline
intramap list --unnamed
```

Point d'entrée déclaré dans `pyproject.toml` (`[project.scripts]`).

## 9. Gestion d'erreurs

Erreurs gérées **aux frontières uniquement** (lancement de nmap, lecture/écriture disque, auto-détection réseau). Entre modules internes, on fait confiance aux invariants des dataclasses (MAC normalisée, etc.).

| Frontière | Erreur | Comportement |
|---|---|---|
| Lancement nmap | Binary introuvable | Message : « nmap non trouvé dans le PATH. Installation : https://nmap.org/download.html » ; exit code ≠ 0 |
| Lancement nmap | Privilèges insuffisants (pas d'ARP) | Message : « Le scan MAC nécessite admin/root. Relance avec privilèges élevés » ; exit code ≠ 0 |
| Auto-détection subnet | Plusieurs interfaces actives | Liste les subnets candidats, demande `--network` explicite |
| Lecture YAML | Fichier corrompu | Affiche la ligne fautive, **n'écrit rien** par-dessus |
| Lecture YAML | MAC non normalisée | Normalisée silencieusement au chargement |
| Écriture YAML | Permission refusée / disque plein | Erreur explicite ; l'ancien fichier reste intact grâce à l'écriture atomique |
| Rendu | `inventory.yaml` absent | Message : « Aucun inventaire. Lance d'abord `intramap scan` » |

### 9.1 Écriture atomique

`inventory.save` écrit d'abord dans `inventory.yaml.tmp`, puis renomme (`os.replace`) vers `inventory.yaml`. Un crash en plein write ne corrompt jamais le fichier existant.

## 10. Tests

Stratégie : tests unitaires par module, **avec mocks aux frontières externes**. Pas de tests d'intégration réseau réel dans la CI (non reproductibles, lents). Un essai manuel sur un vrai réseau fait partie de la validation finale.

### 10.1 Modules

- **`tests/test_models.py`** : normalisation MAC, valeurs par défaut, sérialisation/désérialisation YAML
- **`tests/test_inventory.py`** (cœur de la logique) :
  - Nouveau host ajouté avec champs vides
  - Host existant : préserve `custom_name`, `location`, `first_seen`
  - Host absent du scan : `online=false`, reste préservé
  - Round-trip YAML : `save` puis `load` redonne le même `Inventory`
  - Fichier corrompu : lève une exception sans écraser
  - Écriture atomique : simulation de crash en plein write, fichier original intact
- **`tests/test_renderers.py`** (chaque renderer) :
  - Regroupement floor > room > rack respecté
  - Hosts sans location → groupe « non localisé »
  - Hosts offline marqués visuellement
  - Caractères spéciaux dans les noms échappés correctement (`"`, retours ligne, etc.)
- **`tests/test_scanner.py`** (`nmap.PortScanner` mocké) :
  - Parsing résultat nmap → `list[DiscoveredHost]`
  - Hostname absent, vendor absent gérés
  - IPv6 ignorée silencieusement
- **`tests/test_cli.py`** : smoke tests des sous-commandes avec un inventaire factice

## 11. Dépendances

**Python (déclarées dans `pyproject.toml`) :**
- `python-nmap` — wrapper nmap
- `PyYAML` — lecture/écriture inventaire
- `psutil` — auto-détection subnet local

**Externes :**
- `nmap` (binary) — requis pour le scan
- `plantuml.jar` / `graphviz` (`dot`) — facultatifs, l'utilisateur les utilise pour rendre les fichiers texte générés en images. IntraMap ne les invoque pas.

## 12. Hors-portée (futurs travaux possibles)

- IPv6
- Historique des changements (log apparu/disparu/IP changée)
- Alerte sur MAC inconnue (utile sécurité)
- Topologie L2 via SNMP sur switches managés
- Interface web pour éditer `inventory.yaml`
- Regroupement de plusieurs MAC sous un même appareil (interfaces multiples)
- Rendu image direct (invocation de plantuml/dot)
