"""Renderer Mermaid : diagramme `flowchart` collable dans Markdown / GitHub.

Mêmes regroupements (étage / pièce / baie) et même identité de nœuds (``hN``)
que les renderers Graphviz/PlantUML.
"""
from collections import defaultdict

from intramap.models import Host, Inventory, _resolve_device_type
from intramap.renderers._common import (
    UNLOCALISED as _UNLOCALISED, bucket as _bucket, edge_label as _edge_label,
)
from intramap.renderers.icons import DEVICE_COLORS


def _esc(text: str) -> str:
    """Échappe un label Mermaid (rendu en HTML par défaut)."""
    return (text.replace("&", "&amp;")
                .replace('"', "&quot;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _label(host: Host) -> str:
    parts = [_esc(host.custom_name or host.mac)]
    if host.ip:
        parts.append(_esc(host.ip))
    parts.append(_esc(host.mac))
    return "<br/>".join(parts)


def render(inv: Inventory) -> str:
    node_ids: dict[str, str] = {
        mac: f"h{i + 1}" for i, mac in enumerate(sorted(inv.hosts.keys()))
    }

    tree: dict[str, dict[str, dict[str | None, list[Host]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for host in inv.hosts.values():
        floor, room, rack = _bucket(host)
        tree[floor][room][rack].append(host)

    lines: list[str] = ["flowchart TB"]
    sub = [0]

    def render_host(host: Host, indent: str) -> None:
        lines.append(f'{indent}{node_ids[host.mac]}["{_label(host)}"]')

    def open_sub(label: str, indent: str) -> str:
        sub[0] += 1
        lines.append(f'{indent}subgraph s{sub[0]}["{_esc(label)}"]')
        return indent + "  "

    def close_sub(indent: str) -> None:
        lines.append(f"{indent[:-2]}end")

    for floor in sorted(tree.keys()):
        if floor == _UNLOCALISED:
            continue
        fi = open_sub(floor, "  ")
        for room in sorted(tree[floor].keys()):
            ri = open_sub(room, fi)
            racks = tree[floor][room]
            for host in racks.get(None, []):
                render_host(host, ri)
            for rack in sorted(r for r in racks.keys() if r is not None):
                rki = open_sub(rack, ri)
                for host in racks[rack]:
                    render_host(host, rki)
                close_sub(rki)
            close_sub(ri)
        close_sub(fi)

    if _UNLOCALISED in tree:
        ui = open_sub(_UNLOCALISED, "  ")
        for host in tree[_UNLOCALISED][""][None]:
            render_host(host, ui)
        close_sub(ui)

    # Liens (câbles) : --- filaire, === PoE.
    for link in inv.links:
        if link.mac_a not in node_ids or link.mac_b not in node_ids:
            continue
        a, b = node_ids[link.mac_a], node_ids[link.mac_b]
        op = "===" if link.poe else "---"
        label = _edge_label(link)
        if label:
            lines.append(f'  {a} {op}|"{_esc(label)}"| {b}')
        else:
            lines.append(f"  {a} {op} {b}")

    # Associations Wi-Fi.
    for mac in sorted(inv.hosts.keys()):
        ap = inv.hosts[mac].wifi_ap_mac
        if ap and ap in node_ids:
            lines.append(f'  {node_ids[mac]} -.->|"Wi-Fi"| {node_ids[ap]}')

    # Couleurs par type d'appareil.
    by_type: dict[str, list[str]] = defaultdict(list)
    for mac, host in inv.hosts.items():
        by_type[_resolve_device_type(host)].append(node_ids[mac])
    for t in sorted(by_type.keys()):
        ids = ",".join(sorted(by_type[t]))
        lines.append(f"  classDef {t} fill:{DEVICE_COLORS[t]},stroke:#333;")
        lines.append(f"  class {ids} {t};")

    return "\n".join(lines) + "\n"
