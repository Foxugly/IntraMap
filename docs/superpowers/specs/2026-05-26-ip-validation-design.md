# Spec — Validation des adresses IP en saisie

Date : 2026-05-26
Statut : validé (GO global)

## Objectif

Empêcher la saisie d'IP invalides dans les dialogues (incohérent avec la
validation MAC déjà stricte). IPv4 **et** IPv6 acceptées ; champ vide autorisé
(IP optionnelle) ; seules les valeurs non vides invalides sont rejetées.

## Helper (sans Qt)

`intramap/models.py` : `is_valid_ip(text: str) -> bool` via `ipaddress`
(`ip_address`). Renvoie `False` pour une chaîne vide ou invalide.

## Intégration

- `device_dialog.AddDeviceDialog._accept` : si l'IP saisie est non vide et
  invalide → `QMessageBox.warning` et on n'accepte pas (reste ouvert).
- `inspector.Inspector._apply` : si l'IP est non vide et invalide → avertir,
  remettre le champ à l'IP précédente du host (`self._ip.setText`), et
  conserver l'ancienne valeur (les autres champs continuent d'être appliqués ;
  pas de blocage). Aucune validation au chargement (`set_host`) pour ne pas
  bloquer l'ouverture d'un fichier contenant une IP douteuse.

## Tests

- `tests/test_models.py` : `is_valid_ip` — IPv4 OK, IPv6 OK, invalide → False,
  vide → False.
- `tests/test_gui.py` : `AddDeviceDialog` avec IP invalide ne produit pas de
  host (OK bloqué) ; avec IP valide en produit un. `Inspector` édité avec une
  IP invalide conserve l'IP précédente du host.

## Fichiers

- Modifier : `intramap/models.py`, `intramap/gui/device_dialog.py`,
  `intramap/gui/inspector.py`, `tests/test_models.py`, `tests/test_gui.py`.
