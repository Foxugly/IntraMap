# Spec — Undo/redo par instantanés (GUI)

Date : 2026-05-26
Statut : validé (GO)

## Objectif

Permettre d'annuler/rétablir les éditions du modèle dans l'interface, via une
pile d'historique d'instantanés du document. Approche choisie : **snapshots**
(pas de `QUndoCommand`), car l'inspecteur édite en place au fil de l'eau.

## Capture / restauration (`MainWindow`)

- `_capture_state() -> dict` :
  ```python
  {"doc": self.inv.to_dict(),
   "layout": layout_mod.layout_to_dict(LayoutData(
       positions=self.canvas.current_positions(),
       edge_bends=self.canvas.current_edge_bends(),
       routing_style=self.canvas.routing_style,
       switch_ports=self._switch_ports))}
  ```
- `_restore_state(state)` : reconstruit `self.inv = Inventory.from_dict(state["doc"])`,
  relit le layout (`layout_from_dict`), recharge le canvas
  (`canvas.load(inv, positions_for(...), edge_bends, routing_style)`),
  resynchronise le menu de routage, réinitialise l'inspecteur, marque dirty.
  Encadré par `self._restoring = True/False` pour n'enregistrer aucun nouvel
  état pendant la restauration.

## Pile d'historique

- `self._history: list[dict]`, `self._hist_pos: int`, `self._restoring: bool`.
- Cap : **50** états (les plus anciens sont supprimés au-delà).
- `_reset_history()` : `history = [capture]`, `pos = 0`, met à jour les actions.
  Appelé après **ouverture**, **Nouveau**, **Fermer**, et à la construction.
  **Pas** après Enregistrer (on doit pouvoir annuler après sauvegarde).
- `_record_history()` : si `_restoring`, ne fait rien ; sinon tronque
  `history[pos+1:]`, ajoute l'état courant (état **après** l'action), applique
  le cap, `pos = len-1`, met à jour les actions.
- `_undo()` : si `pos > 0`, `pos -= 1`, restaure `history[pos]`.
- `_redo()` : si `pos < len-1`, `pos += 1`, restaure `history[pos]`.
- `_update_undo_actions()` : `act_undo.setEnabled(pos > 0)` ;
  `act_redo.setEnabled(pos < len-1)`.

## Points d'enregistrement

`_record_history()` est appelé à la fin de : `_add_device`,
`_connect_devices`, `_on_host_changed`, `_on_host_deleted`,
`_on_node_double_clicked` (déclaration de ports, sur acceptation),
`_relayout`, `_reset_bends`, `_set_routing`.

**Exclu** : `_on_node_moved` (un simple déplacement de nœud n'est pas un pas
d'undo séparé — sinon un drag inonderait l'historique).

## UI

- `act_undo` : « Annuler », raccourci `QKeySequence.Undo` (Ctrl+Z).
- `act_redo` : « Rétablir », raccourci `QKeySequence.Redo` (Ctrl+Y / Ctrl+Maj+Z).
- Toutes deux désactivées quand indisponibles ; ajoutées en tête du menu
  **Édition** (séparateur), et à la barre d'outils.

## Tests (headless, sans dialogue modal)

`tests/test_gui.py` :
- round-trip : `_capture_state` → mutation → `_restore_state` redonne l'état.
- annuler/refaire un ajout (mutation directe + `_record_history`).
- annuler une suppression (`_on_host_deleted`) restaure l'appareil **et** sa
  liaison.
- annuler une édition inspecteur (`_on_host_changed`) restaure l'ancien
  `custom_name`.
- positions de nœuds préservées après undo.
- `act_undo`/`act_redo` : désactivées au baseline, activées après changement,
  bascule correcte après undo ; une nouvelle action après undo purge le redo.

## Fichiers

- Modifier : `intramap/gui/main_window.py`, `tests/test_gui.py`.

## Critères de réussite

- Annuler/rétablir restaure fidèlement modèle **et** mise en page.
- Les actions reflètent la disponibilité ; redo purgé après une nouvelle action.
- Aucune régression ; suite complète verte.
