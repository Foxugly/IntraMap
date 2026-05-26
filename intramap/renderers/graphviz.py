from collections import defaultdict
from pathlib import Path

from intramap.models import Host, Inventory, _resolve_device_type
from intramap.renderers.icons import copy_icons_to, DEVICE_COLORS
from intramap.renderers._common import (
    UNLOCALISED as _UNLOCALISED,
    bucket as _bucket,
    edge_label as _edge_label,
    escape_quotes as _escape,
)


def _escape_html(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _html_label(host: Host) -> str:
    name = _escape_html(host.custom_name or host.mac)
    parts = [f"<B>{name}</B>"]
    if host.ip:
        parts.append(f'<FONT POINT-SIZE="10">{_escape_html(host.ip)}</FONT>')
    parts.append(
        f'<FONT POINT-SIZE="9" COLOR="#666666">{_escape_html(host.mac)}</FONT>'
    )
    return "<" + "<BR/>".join(parts) + ">"


def _tooltip(host: Host) -> str:
    vendor = host.vendor or "unknown"
    last = host.last_seen.date().isoformat()
    return _escape(f"{vendor} | last seen {last}")


def render(inv: Inventory, copy_assets_to: str | Path | None = None) -> str:
    """Render `inv` as Graphviz DOT text."""
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
            f'label={_html_label(host)}',
            f'tooltip="{_tooltip(host)}"',
            f'image="icons/{device_type}.png"',
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

    # Edges from declared links (symmetric — one edge per cable).
    for link in inv.links:
        if link.mac_a not in node_ids or link.mac_b not in node_ids:
            continue
        attrs: list[str] = []
        label = _edge_label(link)
        if label:
            attrs.append(f'label="{_escape(label)}"')
        if link.poe:
            attrs.append('color="orange"')
            attrs.append("penwidth=2")
        attrs_str = f' [{", ".join(attrs)}]' if attrs else ""
        lines.append(
            f"  {node_ids[link.mac_a]} -- {node_ids[link.mac_b]}{attrs_str};")

    # Edges from Wi-Fi associations
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        if host.wifi_ap_mac is None or host.wifi_ap_mac not in node_ids:
            continue
        src = node_ids[host.mac]
        dst = node_ids[host.wifi_ap_mac]
        lines.append(
            f'  {src} -- {dst} [style=dashed, color="#1f77b4", '
            f'label="Wi-Fi", fontsize=10];'
        )

    used_types = sorted({_resolve_device_type(h) for h in inv.hosts.values()})
    if used_types:
        lines.append('  subgraph cluster_legend {')
        lines.append('    label="Légende";')
        lines.append('    style=dashed;')
        for t in used_types:
            color = DEVICE_COLORS[t]
            lines.append(
                f'    legend_{t} [label="{t}", image="icons/{t}.png", '
                f'labelloc=b, imagescale=true, fillcolor="{color}", style=filled];'
            )
        lines.append('    legend_wired [label="─── wired", shape=plaintext];')
        lines.append('    legend_poe [label="━━━ PoE", shape=plaintext, fontcolor="#ff7f0e"];')
        lines.append('    legend_wifi [label="┄┄┄ Wi-Fi", shape=plaintext, fontcolor="#1f77b4"];')
        lines.append("  }")

    lines.append("}")

    if copy_assets_to is not None:
        used_types = {_resolve_device_type(h) for h in inv.hosts.values()}
        copy_icons_to(copy_assets_to, used_types)

    return "\n".join(lines) + "\n"
