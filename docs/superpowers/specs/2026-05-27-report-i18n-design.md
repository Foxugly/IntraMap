# Spec — Traduction du contenu des rapports (FR + EN)

Date : 2026-05-27
Statut : validé (GO)

## Objectif

Rendre bilingue le **contenu** des rapports (câblage, chemins, diagnostics,
diff de scan), affiché dans le GUI **et** le CLI, sans faire dépendre le CLI
de Qt.

## Refactor — cœur i18n sans Qt

- Créer `intramap/i18n.py` (sans Qt) : déplace `_CATALOG`, `tr`,
  `set_language`, `current_language`, `resolve_system_language`
  (stdlib `locale`).
- `intramap/gui/i18n.py` : ré-exporte `tr`, `set_language`,
  `current_language`, `resolve_system_language`, `_CATALOG` depuis
  `intramap.i18n` (les imports `from intramap.gui.i18n import tr` du GUI
  restent valides) ; conserve la couche Qt : `available_languages`,
  `load_saved_language`, `save_language`, `apply_saved_language` (QSettings).
- Les builders et le CLI importent `from intramap.i18n import tr`.

## Chaînes à traduire (builders, sans Qt)

- `wiring_report.py` : titre, libellés d'infra (Routeur/Switch/Patch panel/
  Outlet), « (aucun branchement) », « port », « (port ?) », « PoE », messages
  « aucun appareil… ». **CSV non traduit** (format machine).
- `path_report.py` : « Aucun appareil sur la carte. », « alimenté en PoE »,
  « ⇒ Passerelle Internet (accès box). », messages « aucun chemin… »,
  « Accès Internet ✓ », « chemin partiel… », et `_hop_detail`
  (« Wi-Fi », « port {p} », « → port {p} », « PoE »).
- `diagnostics.py` : tous les messages de `Finding` (interpolés via
  `tr("…{x}…").format(...)`).
- `scan_diff.py` : « Aucun changement… » et les en-têtes de sections
  (Nouveaux / Passés hors ligne / Revenus en ligne / IP modifiée).

Catalogue EN étendu dans `intramap/i18n.py`.

## CLI — choix de langue

- Option globale `--lang {fr,en}` sur le parseur racine.
- Dans `main()`, avant le dispatch :
  `i18n.set_language(args.lang or i18n.resolve_system_language())`.
- Sans `--lang`, la locale système décide (fr → français, sinon anglais).

## Tests

- `tests/test_i18n.py` : pointer les tests « cœur » sur `intramap.i18n` ;
  étendre le test de complétude AST pour scanner **aussi** les 4 builders
  (`wiring_report`, `path_report`, `diagnostics`, `scan_diff`).
- Traduction des builders : `set_language("en")` puis vérifier des marqueurs
  anglais (`build_wiring_report`, `build_report`, `diagnose`/message,
  `format_scan_diff`) ; `set_language("fr")` redonne le français. (Remettre
  `fr` en teardown.)
- `tests/test_cli.py` : `report`/`diagnose` avec `--lang en` produisent de
  l'anglais ; sans `--lang`, comportement par défaut (selon locale).

## Fichiers

- Créer : `intramap/i18n.py`.
- Modifier : `intramap/gui/i18n.py`, `intramap/wiring_report.py`,
  `intramap/path_report.py`, `intramap/diagnostics.py`,
  `intramap/scan_diff.py`, `intramap/cli.py`, tests.
