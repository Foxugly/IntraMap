from collections import defaultdict

from intramap.models import Host, Inventory, _resolve_device_type
from intramap.renderers.icons import PLANTUML_SPRITES, DEVICE_COLORS
from intramap.renderers._common import (
    UNLOCALISED as _UNLOCALISED,
    bucket as _bucket,
    edge_label as _edge_label,
    escape_quotes as _escape,
)


def _label(host: Host) -> str:
    name = host.custom_name or host.mac
    lines = [name]
    if host.ip:
        lines.append(host.ip)
    lines.append(host.mac)
    # Chaque ligne est échappée séparément, PUIS jointe par le séparateur
    # PlantUML ``\n`` (un backslash). Échapper après la jointure doublerait
    # ce backslash et casserait le saut de ligne.
    return "\\n".join(_escape(line) for line in lines)


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

    used_types = {_resolve_device_type(h) for h in inv.hosts.values()}
    used_sprites = sorted({PLANTUML_SPRITES[t] for t in used_types})
    include_lines = [f"!include <font-awesome-6/{s}>" for s in used_sprites]

    lines: list[str] = [
        "@startuml",
        "top to bottom direction",
        "skinparam node<<offline>> {",
        "  BackgroundColor #DDDDDD",
        "  BorderColor #888888",
        "}",
        *include_lines,
        "",
    ]

    def render_host(host: Host, indent: str) -> None:
        stereotype = " <<offline>>" if not host.online else ""
        node_id = node_ids[host.mac]
        sprite = PLANTUML_SPRITES[_resolve_device_type(host)]
        label = f"<${sprite}>\\n{_label(host)}"
        if host.online:
            color = DEVICE_COLORS[_resolve_device_type(host)]
            color_suffix = f" {color}"
        else:
            color_suffix = ""
        lines.append(
            f'{indent}node "{label}" as {node_id}{stereotype}{color_suffix}'
        )

    for floor in sorted(tree.keys()):
        if floor == _UNLOCALISED:
            continue
        lines.append(f'package "{_escape(floor)}" {{')
        for room in sorted(tree[floor].keys()):
            lines.append(f'  package "{_escape(room)}" {{')
            racks = tree[floor][room]
            for host in racks.get(None, []):
                render_host(host, "    ")
            for rack in sorted(r for r in racks.keys() if r is not None):
                lines.append(f'    package "{_escape(rack)}" {{')
                for host in racks[rack]:
                    render_host(host, "      ")
                lines.append("    }")
            lines.append("  }")
        lines.append("}")

    if _UNLOCALISED in tree:
        lines.append(f'package "{_UNLOCALISED}" {{')
        for host in tree[_UNLOCALISED][""][None]:
            render_host(host, "  ")
        lines.append("}")

    # Symmetric edges from inv.links.
    for link in inv.links:
        if link.mac_a not in node_ids or link.mac_b not in node_ids:
            continue
        src = node_ids[link.mac_a]
        dst = node_ids[link.mac_b]
        style = "-[#orange,thickness=2]-" if link.poe else "--"
        label = _edge_label(link)
        label_part = f' : "{_escape(label)}"' if label else ""
        lines.append(f"{src} {style} {dst}{label_part}")

    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        if host.wifi_ap_mac is None or host.wifi_ap_mac not in node_ids:
            continue
        src = node_ids[host.mac]
        dst = node_ids[host.wifi_ap_mac]
        lines.append(f'{src} ..> {dst} : "Wi-Fi"')

    used_types = sorted({_resolve_device_type(h) for h in inv.hosts.values()})
    if used_types:
        lines.append('package "Légende" {')
        for t in used_types:
            sprite = PLANTUML_SPRITES[t]
            color = DEVICE_COLORS[t]
            lines.append(
                f'  node "<${sprite}>\\n{t}" as legend_{t} {color}'
            )
        lines.append('  note "**Edges:**\\n─── wired\\n━━━ PoE (orange)\\n┄┄┄ Wi-Fi (blue)" as legend_edges')
        lines.append("}")

    lines.append("@enduml")
    return "\n".join(lines) + "\n"
