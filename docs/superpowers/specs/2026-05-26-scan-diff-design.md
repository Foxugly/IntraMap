# Spec — Diff de scan (apparus / disparus / changés)

Date : 2026-05-26
Statut : validé (GO)

## Objectif

Après un scan, montrer ce qui a changé par rapport à l'état précédent :
appareils apparus, passés hors ligne, revenus en ligne, et IP modifiées.

## Module `intramap/scan_diff.py` (sans Qt)

```python
@dataclass(frozen=True)
class ScanDiff:
    appeared: list[str]                              # nouvelles MAC
    gone_offline: list[str]                          # online -> offline
    back_online: list[str]                           # offline -> online
    ip_changed: list[tuple[str, str | None, str | None]]  # (mac, old, new)

    @property
    def has_changes(self) -> bool: ...

def diff_inventories(before: Inventory, after: Inventory) -> ScanDiff: ...
def format_scan_diff(diff: ScanDiff, inv: Inventory) -> str: ...
```

- `merge()` n'enlève jamais d'hôte (il marque hors ligne) ; on ne traite donc
  pas de catégorie « supprimé ».
- `format_scan_diff` produit un texte multi-lignes (sections Nouveaux /
  Passés hors ligne / Revenus en ligne / IP modifiée), nom d'appareil =
  `custom_name or hostname or mac`. Aucun changement -> « Aucun changement
  depuis le dernier scan. ».

## CLI (`_cmd_scan`)

Avant `merge`, capturer `before = Inventory.from_dict(inv.to_dict())` (copie),
puis après save afficher `format_scan_diff(diff, inv)` en plus du résumé
compteur existant.

## GUI (`_on_scan_done`)

Capturer `before` avant `merge`, calculer le diff, recharger, marquer dirty,
**enregistrer dans l'historique undo** (un scan modifie le modèle), mettre à
jour la barre de statut, et si `diff.has_changes` afficher un
`QMessageBox.information` récapitulatif (texte de `format_scan_diff`). Pas de
dialogue s'il n'y a aucun changement.

## Tests

`tests/test_scan_diff.py` : appeared, gone_offline, back_online, ip_changed,
aucun changement -> `has_changes is False` ; `format_scan_diff` contient les
bons libellés.

`tests/test_cli.py` : un scan ajoutant un device affiche son MAC dans le
résumé de diff.

`tests/test_gui.py` : `_on_scan_done` avec un nouveau device appelle
`QMessageBox.information` (monkeypatché) ; un re-scan sans changement ne
l'appelle pas.

## Fichiers

- Créer : `intramap/scan_diff.py`, `tests/test_scan_diff.py`.
- Modifier : `intramap/cli.py`, `intramap/gui/main_window.py`,
  `tests/test_cli.py`, `tests/test_gui.py`.
