"""Rapport texte du traceroute physique (chemin de chaque appareil jusqu'à la
passerelle Internet). Sans dépendance Qt : réutilisable en CLI comme en GUI.

Le traceroute est non-directionnel : un câble entre A et B est suivi dans les
deux sens. Le calcul part de la passerelle et ne transite que par des appareils
d'infrastructure (outlet/switch/router/patchpanel/ap/controller). Le PoE est
respecté : un appareil PoE reste en PoE jusqu'à son switch PoE, puis hors PoE.
"""
from __future__ import annotations

from intramap.models import Inventory, trace_all_paths


def _device_name(host) -> str:
    return host.custom_name or host.hostname or host.mac


def _hop_detail(hop) -> str:
    """Décrit le saut : ports d'un câble, ou « Wi-Fi » pour une association."""
    if hop.wifi:
        return "Wi-Fi"
    lk = hop.link
    src_p = lk.port_at(hop.src.mac) if hop.src is not None else None
    dst_p = lk.port_at(hop.dst.mac) if hop.dst is not None else None
    parts: list[str] = []
    if src_p is not None:
        parts.append(f"port {src_p}")
    if dst_p is not None:
        parts.append(f"→ port {dst_p}")
    if lk.poe:
        parts.append("PoE")
    return "  ·  ".join(parts)


def build_report(inv: Inventory) -> str:
    """Construit le rapport texte du chemin de chaque appareil vers Internet."""
    if not inv.hosts:
        return "Aucun appareil sur la carte.\n"

    hosts = sorted(inv.hosts.values(), key=lambda h: _device_name(h).lower())
    paths = trace_all_paths(inv)
    lines: list[str] = []
    for h in hosts:
        head = f"■ {_device_name(h)}   [{h.mac}]"
        if h.ip:
            head += f"   {h.ip}"
        if h.poe_gateway:
            head += "   · alimenté en PoE"
        lines.append(head)

        if h.is_gateway:
            lines.append("    ⇒ Passerelle Internet (accès box).")
            lines.append("")
            continue

        path = paths.get(h.mac) or []
        if not path:
            if h.poe_gateway:
                lines.append(
                    "    ⚠ aucun chemin PoE trouvé jusqu'à la passerelle "
                    "Internet (PoE rompu, ou pas de chemin par les "
                    "appareils d'infrastructure)")
            else:
                lines.append(
                    "    ⚠ aucun chemin trouvé jusqu'à la passerelle "
                    "Internet (pas de liaison vers un switch / patch panel "
                    "qui y mène)")
            lines.append("")
            continue

        prev = _device_name(h)
        for hop in path:
            nxt = _device_name(hop.dst)
            detail = _hop_detail(hop)
            suffix = f"   ({detail})" if detail else ""
            lines.append(f"    «{prev}»  →  «{nxt}»{suffix}")
            prev = nxt
        if path[-1].dst.is_gateway:
            lines.append("    ↳ Accès Internet ✓")
        else:
            lines.append(
                f"    ↳ ⚠ chemin partiel — «{prev}» n'atteint pas la "
                f"passerelle Internet")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
