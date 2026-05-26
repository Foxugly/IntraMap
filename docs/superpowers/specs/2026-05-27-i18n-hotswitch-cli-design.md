# Spec — Bascule de langue à chaud + messages CLI traduits

Date : 2026-05-27
Statut : validé (GO)

## Partie A — Bascule de langue à chaud (GUI)

`MainWindow._set_language(code)` n'affiche plus « redémarrez » : il applique la
langue puis **retraduit l'UI en place**.

- `i18n.save_language(code)` ; `i18n.set_language(resolve si « system »)`.
- `_retranslate()` :
  1. Ré-applique le texte de toutes les actions `self.act_*`, des actions de
     routage, le tooltip du panneau latéral, et le placeholder de recherche.
  2. Reconstruit la barre de menus : `menuBar().clear()` puis `_build_menus()`
     (réutilise les mêmes objets actions ; recrée sous-menus routage / langue /
     récents).
  3. Recrée l'inspecteur (ses libellés sont figés à la construction) : nouvel
     `Inspector` inséré dans le `QSplitter` à la place de l'ancien, signaux
     reconnectés, sélection courante réappliquée. (Stocker `self.splitter`.)
  4. `_reload_canvas()` pour rafraîchir les tooltips des nœuds/groupes.

Les dialogues (device/link/switch/diagnose/report/export) lisent la langue à
leur ouverture : rien à faire.

## Partie B — Messages de statut du CLI

Les messages `print(...)` de `intramap/cli.py` sont aujourd'hui en anglais. On
les passe en **français source** (cohérent avec tout le projet) via `tr(...)`,
avec traductions anglaises au catalogue. `main()` ayant déjà fixé la langue
(`--lang` ou locale), les messages suivent la langue.

Périmètre : messages utilisateur de `_load_or_report`, `_cmd_list` (en-têtes de
colonnes), `_cmd_render` (« Wrote … », avertissements `dot`), `_cmd_scan`
(résumé, avertissements), `_cmd_report` (erreur `--format csv`),
`_cmd_diagnose` (« Aucune anomalie… », libellés `[ERREUR]/[ATTENTION]/[INFO]`,
récap). Les chaînes purement techniques / data (CIDR, chemins) restent brutes.

### Tests
- Les tests CLI qui vérifient le **texte** d'un message passent désormais
  `--lang` explicitement (la plupart `--lang en` pour conserver leurs
  assertions anglaises actuelles ; certaines `--lang fr`). Ajout de quelques
  contre-tests dans l'autre langue.
- Le fixture autouse de `conftest.py` (reset langue → fr) garantit
  l'isolation.

## Tests (Partie A)
`tests/test_gui.py` : après `MainWindow._set_language("en")`, une action
(ex. `act_undo`) passe en anglais **sans** recréer la fenêtre ; l'inspecteur
recréé affiche ses onglets en anglais ; pas de dialogue « redémarrer ».

## Fichiers
- Modifier : `intramap/gui/main_window.py`, `intramap/cli.py`,
  `intramap/i18n.py` (catalogue), `tests/test_gui.py`, `tests/test_cli.py`.
