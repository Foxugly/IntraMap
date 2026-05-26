"""Helpers partagés par les renderers Graphviz et PlantUML.

Ces deux renderers émettent des chaînes entre guillemets (étiquettes, noms de
groupes, libellés d'arêtes) et regroupent les hôtes selon le même découpage
étage / pièce / baie. Ce module factorise ce qui était dupliqué à l'identique.
"""
from __future__ import annotations

from intramap.models import Host, Link

UNLOCALISED = "Non localisé"
NO_ROOM = "(sans pièce)"


def escape_quotes(text: str) -> str:
    """Échappe une chaîne destinée à un littéral entre guillemets (DOT/PlantUML).

    Le backslash est échappé **en premier** (sinon on doublerait les backslash
    introduits en échappant les guillemets), puis le guillemet double.
    """
    return text.replace("\\", "\\\\").replace('"', '\\"')


def bucket(host: Host) -> tuple[str, str, str | None]:
    """Classe un hôte en (étage, pièce, baie) pour le regroupement visuel."""
    loc = host.location
    if loc.floor is None:
        return UNLOCALISED, "", None
    room = loc.room or NO_ROOM
    return loc.floor, room, loc.rack


def edge_label(link: Link) -> str:
    """Libellé court d'un câble : ``port_a↔port_b`` et/ou ``PoE``."""
    parts: list[str] = []
    if link.port_a is not None or link.port_b is not None:
        a = str(link.port_a) if link.port_a is not None else "?"
        b = str(link.port_b) if link.port_b is not None else "?"
        parts.append(f"{a}↔{b}")
    if link.poe:
        parts.append("PoE")
    return " ".join(parts)
