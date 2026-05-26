"""Construit le rapport des branchements des appareils d'infrastructure.

Pour chaque routeur / switch / patch panel / outlet present dans l'inventaire,
on liste les ports utilises et l'appareil branche en face (avec son port,
type, label eventuel sur les outlets, et le marquage PoE).

Pensee pour etre la base d'une page texte ajoutee a l'export PDF.
"""
from __future__ import annotations

from intramap.models import (
    Inventory, Link, links_touching, _resolve_device_type,
)

# Types d'equipements pour lesquels on detaille les branchements. L'ordre
# correspond a l'ordre d'affichage dans le rapport (du plus central au plus
# peripherique).
INFRA_TYPES_ORDER: tuple[str, ...] = (
    "router", "switch", "patchpanel", "outlet",
)

_INFRA_LABEL = {
    "router": "Routeur",
    "switch": "Switch",
    "patchpanel": "Patch panel",
    "outlet": "Outlet (prise murale)",
}


def _device_name(host) -> str:
    return host.custom_name or host.hostname or host.mac


def _peer_info(inv: Inventory, link: Link, this_mac: str) -> tuple[str, int | None, str, str]:
    """Renvoie (nom du voisin, port du voisin, type du voisin, label port voisin)."""
    other = link.mac_b if link.mac_a == this_mac else link.mac_a
    other_port = link.port_b if link.mac_a == this_mac else link.port_a
    peer = inv.hosts.get(other)
    if peer is None:
        return (other, other_port, "?", "")
    name = _device_name(peer)
    ptype = _resolve_device_type(peer)
    label = ""
    if (other_port is not None and peer.port_labels
            and other_port in peer.port_labels):
        label = peer.port_labels[other_port]
    return (name, other_port, ptype, label)


def _port_sort_key(port: int | None) -> tuple[int, int]:
    """Tri par numero de port croissant ; les liens sans port en fin."""
    return (1, 0) if port is None else (0, port)


def build_wiring_report(inv: Inventory) -> str:
    """Retourne un rapport texte multi-lignes des branchements infra.

    Le format est volontairement plat (pas de tableau) pour rester lisible
    dans un PDF mis en page automatiquement.
    """
    if not inv.hosts:
        return "Aucun appareil dans l'inventaire.\n"

    # Regroupement par type d'infra dans l'ordre voulu.
    by_type: dict[str, list] = {t: [] for t in INFRA_TYPES_ORDER}
    for host in inv.hosts.values():
        t = _resolve_device_type(host)
        if t in by_type:
            by_type[t].append(host)
    for t in INFRA_TYPES_ORDER:
        by_type[t].sort(key=lambda h: _device_name(h).lower())

    if not any(by_type.values()):
        return ("Aucun appareil d'infrastructure (routeur, switch, "
                "patch panel, outlet) dans l'inventaire.\n")

    lines: list[str] = []
    lines.append("Branchements des appareils d'infrastructure")
    lines.append("=" * 50)
    lines.append("")

    for t in INFRA_TYPES_ORDER:
        hosts = by_type[t]
        if not hosts:
            continue
        lines.append(f"## {_INFRA_LABEL[t]} ({len(hosts)})")
        lines.append("")
        for host in hosts:
            head = f"- {_device_name(host)}  [{host.mac}]"
            loc_bits = []
            if host.location.floor:
                loc_bits.append(host.location.floor)
            if host.location.room:
                loc_bits.append(host.location.room)
            if loc_bits:
                head += "  -  " + " / ".join(loc_bits)
            lines.append(head)

            links = links_touching(inv, host.mac)
            if not links:
                lines.append("    (aucun branchement)")
                lines.append("")
                continue

            # Tri par port local croissant.
            def own_port(lk: Link) -> int | None:
                return lk.port_a if lk.mac_a == host.mac else lk.port_b
            links_sorted = sorted(links, key=lambda lk: _port_sort_key(own_port(lk)))

            for lk in links_sorted:
                p_here = own_port(lk)
                p_label_here = ""
                if (p_here is not None and host.port_labels
                        and p_here in host.port_labels):
                    p_label_here = host.port_labels[p_here]
                peer_name, peer_port, peer_type, peer_label = _peer_info(
                    inv, lk, host.mac)

                here = (f"port {p_here}" if p_here is not None else "(port ?)")
                if p_label_here:
                    here += f" [{p_label_here}]"
                peer = (f"port {peer_port}" if peer_port is not None else "(port ?)")
                if peer_label:
                    peer += f" [{peer_label}]"

                line = (f"    {here}  ->  {peer_name} ({peer_type})  -  {peer}")
                if lk.poe:
                    line += "   PoE"
                lines.append(line)
            lines.append("")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
