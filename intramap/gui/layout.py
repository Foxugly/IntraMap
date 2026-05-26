"""Mise en page de la carte (couche *layout*).

La disposition — positions des nœuds, coudes des liaisons, style de routage —
est désormais stockée **dans l'inventaire lui-même**, sous une section
``layout`` de premier niveau. Un seul fichier (`inventory.yaml`) contient donc
à la fois les données réseau et leur mise en page::

    last_scan: ...
    layout:
      routing_style: ortho_h
      positions:
        aa:bb:cc:dd:ee:ff: {x: 120.0, y: 40.0}
      edges:
        "aa:bb:..|02:00:..|wired": {split: 310.5}
    hosts:
      ...

La section ``layout`` est ignorée par le modèle de données
(:mod:`intramap.models`) et par la CLI : ce module fait la conversion entre
ce dictionnaire et l'objet :class:`LayoutData` utilisé par l'interface.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from intramap.models import Inventory, normalize_mac

_VALID_STYLES = ("straight", "ortho_h", "ortho_v")
DEFAULT_ROUTING_STYLE = "ortho_h"

# Auto-layout : taille de cellule (nœud + marge) et écarts entre groupes.
_CELL_W = 200.0
_CELL_H = 165.0
_ROOM_GAP = 80.0
_FLOOR_GAP = 130.0
_ROOM_COLS = 4


@dataclass
class LayoutData:
    """Mise en page de la carte, telle que manipulée par l'interface."""
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    edge_bends: dict[str, float] = field(default_factory=dict)
    routing_style: str = DEFAULT_ROUTING_STYLE
    # Nombre de ports déclaré pour un switch, indexé par MAC.
    switch_ports: dict[str, int] = field(default_factory=dict)


def layout_from_dict(data: dict) -> LayoutData:
    """Convertit la section ``layout`` (dict YAML/JSON) en :class:`LayoutData`.

    Les entrées invalides sont ignorées silencieusement : une mise en page
    abîmée ne doit jamais empêcher l'ouverture de la carte.
    """
    data = data or {}

    positions: dict[str, tuple[float, float]] = {}
    for mac, coords in (data.get("positions") or {}).items():
        try:
            positions[normalize_mac(mac)] = (
                float(coords["x"]), float(coords["y"]))
        except (ValueError, TypeError, KeyError):
            continue

    edge_bends: dict[str, float] = {}
    for key, info in (data.get("edges") or {}).items():
        try:
            edge_bends[str(key)] = float(info["split"])
        except (ValueError, TypeError, KeyError):
            continue

    style = data.get("routing_style")
    if style not in _VALID_STYLES:
        style = DEFAULT_ROUTING_STYLE

    switch_ports: dict[str, int] = {}
    for mac, count in (data.get("switch_ports") or {}).items():
        try:
            n = int(count)
        except (ValueError, TypeError):
            continue
        if n > 0:
            try:
                switch_ports[normalize_mac(mac)] = n
            except ValueError:
                continue

    return LayoutData(positions=positions, edge_bends=edge_bends,
                      routing_style=style, switch_ports=switch_ports)


def layout_to_dict(layout: LayoutData) -> dict:
    """Sérialise un :class:`LayoutData` vers la section ``layout`` du YAML."""
    return {
        "routing_style": layout.routing_style,
        "positions": {
            mac: {"x": round(x, 2), "y": round(y, 2)}
            for mac, (x, y) in sorted(layout.positions.items())
        },
        "edges": {
            key: {"split": round(split, 2)}
            for key, split in sorted(layout.edge_bends.items())
        },
        "switch_ports": dict(sorted(layout.switch_ports.items())),
    }


def read_legacy_sidecar(inventory_path: str | Path) -> dict:
    """Migration : lit un ancien fichier compagnon ``*.layout.json``.

    Les premières versions de l'interface stockaient la mise en page dans un
    fichier JSON séparé. S'il existe encore et que l'inventaire n'a pas de
    section ``layout``, on le récupère une dernière fois ; au prochain
    enregistrement la mise en page passe dans l'inventaire. Retourne ``{}``
    si aucun fichier compagnon exploitable n'est trouvé.
    """
    sidecar = Path(inventory_path).with_suffix(".layout.json")
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def auto_layout(inv: Inventory) -> dict[str, tuple[float, float]]:
    """Dispose les nœuds en blocs : une bande par étage, un bloc par pièce.

    Les blocs sont assez espacés pour que les cadres de groupe (étage/pièce)
    ne se chevauchent pas au départ. L'utilisateur réorganise ensuite par
    glisser-déposer.
    """
    tree: dict[str, dict[object, list[str]]] = {}
    for mac, host in inv.hosts.items():
        floor = host.location.floor or "Non localisé"
        tree.setdefault(floor, {}).setdefault(host.location.room, []).append(mac)

    positions: dict[str, tuple[float, float]] = {}
    y = 0.0
    for floor in sorted(tree):
        rooms = tree[floor]
        # Pièces nommées triées, puis les hôtes sans pièce (clé None) en dernier.
        room_keys: list[object] = sorted(
            (r for r in rooms if r is not None), key=str)
        if None in rooms:
            room_keys.append(None)

        x = 0.0
        floor_height = 0.0
        for room in room_keys:
            macs = sorted(
                rooms[room],
                key=lambda m: (inv.hosts[m].custom_name or inv.hosts[m].mac))
            cols = min(_ROOM_COLS, len(macs)) or 1
            rows = (len(macs) + cols - 1) // cols
            for i, mac in enumerate(macs):
                positions[mac] = (x + (i % cols) * _CELL_W,
                                  y + (i // cols) * _CELL_H)
            x += cols * _CELL_W + _ROOM_GAP
            floor_height = max(floor_height, rows * _CELL_H)
        y += floor_height + _FLOOR_GAP
    return positions


def positions_for(
    inv: Inventory,
    saved: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Fusionne positions enregistrées et auto-layout.

    Tout hôte présent dans ``saved`` garde sa position ; les autres (nouveaux
    devices, premier lancement) reçoivent une position issue de l'auto-layout.
    """
    auto = auto_layout(inv)
    return {
        mac: saved.get(mac, auto.get(mac, (0.0, 0.0)))
        for mac in inv.hosts
    }
