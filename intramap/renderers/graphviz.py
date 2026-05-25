from collections import defaultdict
from pathlib import Path

from intramap.models import Host, Inventory, Uplink, _resolve_device_type
from intramap.renderers.icons import copy_icons_to, DEVICE_COLORS


_UNLOCALISED = "Non localisé"
_NO_ROOM = "(sans pièce)"


def _escape(text: str) -> str:
    return text.replace('"', '\\"')


def _label(host: Host) -> str:
    name = host.custom_name or host.mac
    ip = host.ip or "?"
    return _escape(f"{name}\\n{ip}\\n{host.mac}")


def _bucket(host: Host) -> tuple[str, str, str | None]:
    loc = host.location
    if loc.floor is None:
        return _UNLOCALISED, "", None
    room = loc.room or _NO_ROOM
    return loc.floor, room, loc.rack


def _edge_label(uplink: Uplink) -> str:
    parts: list[str] = []
    if uplink.switch_port is not None:
        parts.append(f"sw:{uplink.switch_port}")
    if uplink.patch_port is not None:
        parts.append(f"pp:{uplink.patch_port}")
    if uplink.poe:
        parts.append("PoE")
    return " ".join(parts)


def render(inv: Inventory, copy_assets_to: str | Path | None = None) -> str:
    """Render `inv` as Graphviz DOT text.

    If `copy_assets_to` is given, also copy the SVG icons of all used
    device_types into `<copy_assets_to>/icons/`.
    """
    # Stable node IDs per MAC so edges reference consistent identifiers
    node_ids: dict[str, str] = {
        mac: f"h{i + 1}" for i, mac in enumerate(sorted(inv.hosts.keys()))
    }

    tree: dict[str, dict[str, dict[str | None, list[Host]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for host in inv.hosts.values():
        floor, room, rack = _bucket(host)
        tree[floor][room][rack].append(host)

    lines: list[str] = [
        "graph network {",
        "  rankdir=TB;",
        "  splines=ortho;",
        "  nodesep=0.5;",
        "  ranksep=0.8;",
        "  node [shape=box];",
    ]
    cluster_id = 0

    def render_host(host: Host, indent: str) -> None:
        device_type = _resolve_device_type(host)
        fillcolor = DEVICE_COLORS[device_type]
        attrs = [
            f'label="{_label(host)}"',
            f'image="icons/{device_type}.svg"',
            'labelloc="b"',
            'imagescale=true',
            f'fillcolor="{fillcolor}"',
        ]
        if host.online:
            attrs.append("style=filled")
        else:
            attrs.append('style="filled,dashed"')
            attrs.append('color="#888888"')
        node_id = node_ids[host.mac]
        lines.append(f'{indent}{node_id} [{", ".join(attrs)}];')

    def open_cluster(label: str, indent: str) -> str:
        nonlocal cluster_id
        cluster_id += 1
        lines.append(f'{indent}subgraph cluster_{cluster_id} {{')
        lines.append(f'{indent}  label="{_escape(label)}";')
        return indent + "  "

    def close_cluster(indent: str) -> None:
        lines.append(f"{indent[:-2]}}}")

    for floor in sorted(tree.keys()):
        if floor == _UNLOCALISED:
            continue
        floor_indent = open_cluster(floor, "  ")
        for room in sorted(tree[floor].keys()):
            room_indent = open_cluster(room, floor_indent)
            racks = tree[floor][room]
            for host in racks.get(None, []):
                render_host(host, room_indent)
            for rack in sorted(r for r in racks.keys() if r is not None):
                rack_indent = open_cluster(rack, room_indent)
                for host in racks[rack]:
                    render_host(host, rack_indent)
                close_cluster(rack_indent)
            close_cluster(room_indent)
        close_cluster(floor_indent)

    if _UNLOCALISED in tree:
        u_indent = open_cluster(_UNLOCALISED, "  ")
        for host in tree[_UNLOCALISED][""][None]:
            render_host(host, u_indent)
        close_cluster(u_indent)

    # Edges from declared uplinks
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        u = host.uplink
        if u is None or u.switch_mac is None:
            continue
        if u.switch_mac not in node_ids:
            continue
        attrs: list[str] = []
        label = _edge_label(u)
        if label:
            attrs.append(f'label="{_escape(label)}"')
        if u.poe:
            attrs.append('color="orange"')
            attrs.append("penwidth=2")
        attrs_str = f' [{", ".join(attrs)}]' if attrs else ""
        lines.append(f"  {node_ids[host.mac]} -- {node_ids[u.switch_mac]}{attrs_str};")

    lines.append("}")

    if copy_assets_to is not None:
        used_types = {_resolve_device_type(h) for h in inv.hosts.values()}
        copy_icons_to(copy_assets_to, used_types)

    return "\n".join(lines) + "\n"
