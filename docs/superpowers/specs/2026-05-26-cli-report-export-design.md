# Spec — Export des rapports en CLI

Date : 2026-05-26
Statut : validé (en attente de relecture)

## Objectif

Rendre les deux rapports déjà existants accessibles en ligne de commande, sans
dépendance à Qt :
- le **rapport de câblage** des appareils d'infrastructure
  (`wiring_report.build_wiring_report`), en texte et en CSV tabulaire ;
- le **rapport des chemins réseau** (traceroute physique), en texte.

## Périmètre

- **Inclus** : une sous-commande `report`, l'extraction du builder de chemins
  hors du module GUI, et un export CSV pour le câblage.
- **Exclu** : Markdown, CSV pour les chemins, toute sortie graphique. (YAGNI.)

## Contexte / contrainte d'architecture

`wiring_report.build_wiring_report(inv)` est déjà sans Qt → réutilisable tel
quel. En revanche `build_report` (chemins) vit dans
`intramap/gui/path_report_dialog.py`, qui importe **PySide6 en tête de
module** : la CLI ne doit pas tirer Qt (extra optionnel `gui`). Il faut donc
**extraire** la logique de rapport de chemins dans un module sans Qt.

## Architecture / fichiers

- **`intramap/path_report.py`** *(nouveau, sans Qt)* — contient
  `build_report(inv) -> str`, `_hop_detail(hop) -> str`,
  `_device_name(host) -> str`, déplacés à l'identique depuis
  `gui/path_report_dialog.py`.
- **`intramap/gui/path_report_dialog.py`** *(modifié)* — supprime les copies
  locales et importe `build_report` (et au besoin `_device_name`,
  `_hop_detail`) depuis `intramap.path_report`. Le dialogue Qt est inchangé.
  Le symbole `build_report` reste importable depuis ce module (ré-export) pour
  ne pas casser les appels existants.
- **`intramap/wiring_report.py`** *(modifié)* — ajout de
  `build_wiring_csv(inv) -> str`.
- **`intramap/cli.py`** *(modifié)* — `_cmd_report(args)` + sous-parseur
  `report` dans `build_parser`.

## Commande

```
intramap [--inventory PATH] report {wiring|paths|all} [--format {text,csv}] [--output FILE]
```

- `type` : positionnel **requis**, `choices=["wiring", "paths", "all"]`.
- `--format` : `text` (défaut) ou `csv`. `csv` n'est **valide qu'avec
  `wiring`** ; combiné à `paths` ou `all`, la commande écrit un message clair
  sur `stderr` et retourne le **code 2** (sans rien produire).
- `--output` : si absent, écrit sur **stdout** ; sinon écrit le fichier en
  UTF-8 et affiche `Wrote <chemin>` sur stdout.
- Inventaire absent / illisible : passe par `_load_or_report` (codes 2 / 4,
  cohérent avec `list` et `render`).

### Contenu par type (format texte)
- `wiring` → `build_wiring_report(inv)`.
- `paths`  → `build_report(inv)`.
- `all`    → `build_wiring_report(inv)`, une ligne de séparation
  (`"=" * 60`), puis `build_report(inv)`.

## Format CSV (câblage)

Une ligne par couple (appareil d'infrastructure, câble qui le touche), dans le
même ordre que le rapport texte : types `router`, `switch`, `patchpanel`,
`outlet`, et au sein de chaque type tri par nom (`custom_name or hostname or
mac`, insensible à la casse). Un câble reliant deux appareils d'infra apparaît
donc une fois par extrémité (c'est voulu : la vue est « par appareil »).

Colonnes (en-tête exact) :

```
device,mac,floor,room,local_port,local_label,peer,peer_type,peer_port,peer_label,poe
```

- `device` = `custom_name or hostname or mac` de l'appareil d'infra.
- `local_port` / `peer_port` : entier, ou **cellule vide** si `None`.
- `local_label` / `peer_label` : label du port (`port_labels`), sinon vide.
- `peer` / `peer_type` : nom et `_resolve_device_type` du voisin ; si le voisin
  n'est pas dans l'inventaire, `peer` = MAC brut et `peer_type` = `?`.
- `poe` : `true` / `false`.
- Génération via le module `csv` de la stdlib avec `lineterminator="\n"`.
- Inventaire sans appareil d'infra → **ligne d'en-tête seule** (CSV valide).

## Codes de sortie

| Cas | Code |
|-----|------|
| Succès | 0 |
| `--format csv` avec `paths`/`all` | 2 |
| Inventaire absent | 2 |
| Inventaire illisible | 4 |

## Tests

**`tests/test_path_report.py`** *(nouveau, sans Qt)* :
- `build_report` trace un appareil jusqu'à la passerelle (contient les noms,
  « Accès Internet »).
- appareil isolé → mention « aucun chemin ».
- inventaire vide → message « Aucun appareil… ».

**`tests/test_wiring_report.py`** *(ajouts)* :
- `build_wiring_csv` émet l'en-tête exact.
- une ligne par câble d'un switch, avec `peer`, `peer_type`, ports.
- colonne `poe` = `true` quand le câble est PoE.
- labels de port repris dans `local_label`/`peer_label`.
- inventaire vide → en-tête seul (1 ligne).

**`tests/test_cli.py`** *(ajouts, via `main([...])` + `capsys`)* :
- `report wiring` → stdout contient le titre du rapport, exit 0.
- `report paths` → stdout contient le traceroute, exit 0.
- `report all` → contient les deux + séparateur.
- `report wiring --format csv` → stdout contient la ligne d'en-tête CSV.
- `report paths --format csv` → exit 2, message sur stderr.
- `report wiring --output FICHIER` → fichier créé, `Wrote` sur stdout, exit 0.
- inventaire absent → exit ≠ 0, message mentionnant « inventory ».

**Non-régression** : le test GUI existant qui importe
`intramap.gui.path_report_dialog.build_report` reste vert (ré-export).

## Critères de réussite

- Les trois variantes (`wiring`/`paths`/`all`) et les deux formats produisent
  la bonne sortie, sur stdout ou fichier.
- La CLI ne tire jamais PySide6 (vérifiable : `import intramap.cli` sans Qt).
- Suite complète verte (existants + nouveaux tests).
