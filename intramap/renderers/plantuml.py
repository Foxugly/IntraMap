from collections import defaultdict

from intramap.models import Host, Inventory, Uplink, _resolve_device_type
from intramap.renderers.icons import PLANTUML_SPRITES, DEVICE_COLORS


_UNLOCALISED = "Non localisé"
_NO_ROOM = "(sans pièce)"


def _escape(text: str) -> str:
    return text.replace('"', '\\"')


def _label(host: Host) -> str:
    name = host.custom_name or host.mac
    ip = host.ip or "?"
    lines = [name, ip, host.mac]
    return _escape("\\n".join(lines))


def _bucket(host: Host) -> tuple[str, str, str | None]:
    """Return (floor, room, rack-or-None) for a host."""
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


def render(inv: Inventory) -> str:
    """Render an Inventory as PlantUML text."""
    # Assign stable node IDs by sorted MAC so edges can reference them.
    node_ids: dict[str, str] = {
        mac: f"h{i + 1}" for i, mac in enumerate(sorted(inv.hosts.keys()))
    }

    # floor -> room -> rack-or-None -> list[Host]
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
            continue  # render at the end
        lines.append(f'package "{_escape(floor)}" {{')
        for room in sorted(tree[floor].keys()):
            lines.append(f'  package "{_escape(room)}" {{')
            racks = tree[floor][room]
            # Hosts directly in the room (no rack) first
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

    # Edges from declared uplinks
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        u = host.uplink
        if u is None or u.switch_mac is None:
            continue
        if u.switch_mac not in node_ids:
            continue  # silently skip uplinks pointing to unknown hosts
        src = node_ids[host.mac]
        dst = node_ids[u.switch_mac]
        style = "-[#orange,thickness=2]-" if u.poe else "--"
        label = _edge_label(u)
        label_part = f' : "{_escape(label)}"' if label else ""
        lines.append(f"{src} {style} {dst}{label_part}")

    # Edges from Wi-Fi associations
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        if host.wifi_ap_mac is None:
            continue
        if host.wifi_ap_mac not in node_ids:
            continue
        src = node_ids[host.mac]
        dst = node_ids[host.wifi_ap_mac]
        lines.append(f'{src} ..> {dst} : "Wi-Fi"')

    lines.append("@enduml")
    return "\n".join(lines) + "\n"
