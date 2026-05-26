# Spec — Détection d'anomalies de câblage

Date : 2026-05-26
Statut : validé (GO)

## Objectif

Détecter automatiquement les incohérences de câblage d'un inventaire et les
présenter en CLI et dans le GUI. Logique sans Qt, réutilisable.

## Module `intramap/diagnostics.py` (sans Qt)

```python
@dataclass(frozen=True)
class Finding:
    severity: str            # "error" | "warning" | "info"
    category: str            # broken-link | unreachable | port-conflict | gateway | wifi
    message: str             # texte FR
    macs: tuple[str, ...] = ()

def diagnose(inv: Inventory) -> list[Finding]:
    ...
```

Résultat trié : `error` -> `warning` -> `info`, puis par `category` (tri stable,
ordre d'insertion préservé ensuite). Inventaire sain -> `[]`.

Nom d'appareil affiché : `custom_name or hostname or mac`.

### Règles

1. **Liens cassés** *(error, `broken-link`)*
   - `mac_a == mac_b` -> « Câble en boucle sur un même appareil ». `macs=(mac_a,)`.
   - `mac_a` ou `mac_b` absent de `inv.hosts` -> « Câble vers une MAC absente :
     <macs absentes> ». `macs` = extrémités présentes.

2. **Sans chemin** *(warning, `unreachable`)* — uniquement **si au moins une
   passerelle existe** : via `trace_all_paths(inv)`, tout hôte non-passerelle
   dont le chemin est vide. `macs=(mac,)`.

3. **Port sur-souscrit** *(warning, `port-conflict`)* — comptage des câbles par
   `(mac, port)` (ports `None` ignorés). Limite = 1 câble par port, **sauf
   patch panel** (limite 2, pass-through). Au-delà -> un finding par
   `(appareil, port)`. `macs=(mac,)`.

4. **Passerelle / Wi-Fi**
   - Aucune passerelle déclarée -> *(warning, `gateway`)*, un seul finding,
     `macs=()`.
   - `wifi_ap_mac` absent de l'inventaire -> *(error, `wifi`)*, `macs=(mac,)`.
   - `wifi_ap_mac` présent mais type du pair hors {`ap`, `router`,
     `controller`} -> *(warning, `wifi`)* « n'est pas un point d'accès »,
     `macs=(mac, ap)`.

## CLI : `intramap diagnose [--strict]`

- Sans anomalie : affiche « Aucune anomalie détectée. », exit 0.
- Avec anomalies : une ligne par finding, préfixée `[ERREUR]` / `[ATTENTION]`
  / `[INFO]`, puis un récapitulatif `N anomalie(s) détectée(s).`.
- `--strict` : exit **1** s'il y a au moins un finding ; sinon exit 0 toujours.
- Inventaire absent/illisible : via `_load_or_report` (exit 2 / 4).

## GUI : dialogue « Diagnostics réseau… »

- Fichier `intramap/gui/diagnose_dialog.py`, classe `DiagnoseDialog(QDialog)`
  (modal).
- Entrée de menu sous **Affichage**, à côté de « Rapport des chemins réseau ».
- `QListWidget` : une ligne par finding (préfixe + couleur selon sévérité ;
  rouge erreur, orange avertissement). Les MAC concernées sont stockées dans
  `Qt.UserRole`. Sans finding : une ligne « Aucune anomalie détectée. ».
- **Double-clic** sur une ligne ayant des MAC -> `self.selected_mac = macs[0]`
  puis fermeture acceptée du dialogue. Une fois le dialogue fermé,
  `main_window` lit `selected_mac` et sélectionne cet appareil sur la carte
  (et l'affiche dans l'inspecteur).

## Fichiers

- Créer : `intramap/diagnostics.py`, `intramap/gui/diagnose_dialog.py`,
  `tests/test_diagnostics.py`.
- Modifier : `intramap/cli.py` (commande `diagnose`),
  `intramap/gui/main_window.py` (action + menu + sélection post-dialogue).

## Tests

**`tests/test_diagnostics.py`** : lien orphelin, self-loop, sans-chemin,
conflit de port sur switch, patch-panel à 2 câbles **non** signalé, patch-panel
à 3 -> signalé, passerelle absente, Wi-Fi MAC inconnue, Wi-Fi vers non-AP,
inventaire sain -> `[]`.

**`tests/test_cli.py`** : `diagnose` sain (« Aucune anomalie », exit 0), avec
anomalie (texte + exit 0), `--strict` avec anomalie (exit 1).

**`tests/test_gui.py`** : `DiagnoseDialog` crée une ligne par finding ;
double-clic sur une ligne avec MAC positionne `selected_mac` ;
`intramap.diagnostics` reste sans Qt.

## Critères de réussite

- Les 4 vérifications produisent les bons findings ; inventaire sain -> aucun.
- `intramap diagnose` et le dialogue affichent les mêmes anomalies.
- `intramap.diagnostics` et `intramap.cli` n'importent pas PySide6.
- Suite complète verte.
