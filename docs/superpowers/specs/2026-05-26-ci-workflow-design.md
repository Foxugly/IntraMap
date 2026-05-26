# Spec — Intégration continue (GitHub Actions) + badge README

Date : 2026-05-26
Statut : validé (en attente de relecture)

## Objectif

Exécuter automatiquement la suite de tests (`pytest`, 218 tests dont les
tests GUI Qt en headless) à chaque `push` sur `main` et à chaque pull request,
sur plusieurs OS et versions de Python, et afficher l'état dans le README via
un badge. Aucun changement du code applicatif : ajout purement additif.

## Périmètre

- **Inclus** : un workflow GitHub Actions et un badge dans `README.md`.
- **Exclu** : lint/format (ruff), type-checking (mypy), publication de
  paquet, couverture de code. Pourront faire l'objet d'itérations ultérieures.

## Workflow

Fichier : `.github/workflows/ci.yml`, nom `CI`.

### Déclencheurs

```yaml
on:
  push:
    branches: [main]
  pull_request:
```

Couvre le flux trunk-based (push sur `main`) sans double exécution inutile, et
toute PR.

### Matrice (4 jobs)

```yaml
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, windows-latest]
    python-version: ["3.11", "3.13"]
```

- `fail-fast: false` : voir tous les échecs, pas seulement le premier.
- `3.11` = minimum supporté (`requires-python = ">=3.11"`), `3.13` = récent
  stable. (3.14 non retenu : trop récent côté `setup-python`.)
- Linux **et** Windows : Windows est l'environnement de dev/cible ; Linux
  attrape les hypothèses de plateforme (le scan évoque `sudo`/chemins POSIX).

### Étapes (par job)

1. `actions/checkout@v4`
2. `actions/setup-python@v5` avec `python-version` de la matrice et
   `cache: pip`.
3. **Linux uniquement** (`if: runner.os == 'Linux'`) : installer les
   bibliothèques système réclamées par PySide6 en headless :
   ```bash
   sudo apt-get update
   sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3
   ```
   (Inutile sur Windows : la plateforme Qt `offscreen` n'a pas ces
   dépendances là-bas.)
4. `python -m pip install --upgrade pip` puis
   `pip install -e .[dev,gui]` — récupère les déps runtime
   (`python-nmap`, `PyYAML`, `psutil`), `pytest` (extra `dev`) et
   `PySide6` (extra `gui`).
5. `python -m pytest -q` avec la variable d'environnement
   `QT_QPA_PLATFORM=offscreen`.

### Notes de conception / risques

- **nmap** : `tests/test_scanner.py` mocke `nmap.PortScanner` → aucun binaire
  nmap requis sur les runners.
- **Qt headless** : `tests/conftest.py` force déjà `QT_QPA_PLATFORM=offscreen`
  via `setdefault` ; on positionne quand même la variable au niveau du job CI
  (ceinture + bretelles).
- **Libs Qt Linux manquantes** : si l'import PySide6 échoue, le message est
  explicite → on complète la liste `apt`. Le set proposé est le minimum
  habituel pour PySide6 offscreen.
- **Aucun secret requis** ; le workflow ne touche pas au code.

## Badge README

Inséré immédiatement sous le titre `# IntraMap`, avant le paragraphe de
description :

```markdown
[![CI](https://github.com/Foxugly/IntraMap/actions/workflows/ci.yml/badge.svg)](https://github.com/Foxugly/IntraMap/actions/workflows/ci.yml)
```

## Critères de réussite

- Le workflow apparaît dans l'onglet *Actions* du dépôt et passe au vert sur
  les 4 jobs après le push.
- Le badge s'affiche dans le README et pointe vers la page Actions du workflow.
- Aucune régression : les 218 tests passent sur chaque combinaison.

## Tests / vérification

La CI n'est pas testable par `pytest` (c'est de la config). Vérification :
- Validation YAML locale du workflow (lecture + parse).
- Après push : observer les 4 jobs verts dans l'onglet Actions.
- Confirmer le rendu du badge.
