"""Détection d'anomalies de câblage sur un :class:`Inventory`.

Renvoie une liste de :class:`Finding` (sévérité, catégorie, message, MAC
concernées). Sans dépendance Qt : réutilisable en CLI comme en GUI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from intramap.models import Inventory, _resolve_device_type, trace_all_paths

# Types d'appareils considérés comme des points d'accès Wi-Fi valides.
_AP_TYPES = frozenset({"ap", "router", "controller"})

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    """Une anomalie détectée. ``macs`` liste les appareils concernés (utilisé
    par le GUI pour sélectionner l'appareil fautif sur la carte)."""
    severity: str            # "error" | "warning" | "info"
    category: str            # broken-link | unreachable | port-conflict | gateway | wifi
    message: str
    macs: tuple[str, ...] = field(default=())


def _name(host) -> str:
    return host.custom_name or host.hostname or host.mac


def diagnose(inv: Inventory) -> list[Finding]:
    """Analyse l'inventaire et renvoie les anomalies, triées par sévérité."""
    findings: list[Finding] = []

    # 1. Liens cassés : self-loop, ou extrémité absente de l'inventaire.
    for lk in inv.links:
        if lk.mac_a == lk.mac_b:
            findings.append(Finding(
                "error", "broken-link",
                f"Câble en boucle sur un même appareil ({lk.mac_a}).",
                (lk.mac_a,)))
            continue
        missing = [m for m in (lk.mac_a, lk.mac_b) if m not in inv.hosts]
        if missing:
            present = tuple(m for m in (lk.mac_a, lk.mac_b) if m in inv.hosts)
            findings.append(Finding(
                "error", "broken-link",
                f"Câble vers une MAC absente de l'inventaire : "
                f"{', '.join(missing)}.", present))

    # 4a. Passerelle Internet absente.
    gateways = [h for h in inv.hosts.values() if h.is_gateway]
    if not gateways:
        findings.append(Finding(
            "warning", "gateway",
            "Aucune passerelle Internet déclarée (cochez « Passerelle "
            "Internet » sur la box).", ()))

    # 2. Appareils sans chemin (seulement si une passerelle existe, sinon le
    #    point 4a couvre déjà le problème et on éviterait le bruit).
    if gateways:
        paths = trace_all_paths(inv)
        for mac, host in inv.hosts.items():
            if host.is_gateway:
                continue
            if not paths.get(mac):
                findings.append(Finding(
                    "warning", "unreachable",
                    f"« {_name(host)} » n'atteint aucune passerelle Internet.",
                    (mac,)))

    # 3. Port physique sur-souscrit (hors patch panel en pass-through).
    for mac, host in inv.hosts.items():
        counts: dict[int, int] = {}
        for lk in inv.links:
            if lk.mac_a == mac:
                p = lk.port_a
            elif lk.mac_b == mac:
                p = lk.port_b
            else:
                continue
            if p is not None:
                counts[p] = counts.get(p, 0) + 1
        is_pp = _resolve_device_type(host) == "patchpanel"
        limit = 2 if is_pp else 1
        for p, c in sorted(counts.items()):
            if c <= limit:
                continue
            if is_pp:
                msg = (f"Port {p} de « {_name(host)} » (patch panel) : "
                       f"{c} câbles (2 max en pass-through).")
            else:
                msg = (f"Port {p} de « {_name(host)} » : {c} câbles "
                       f"branchés (un seul attendu).")
            findings.append(Finding("warning", "port-conflict", msg, (mac,)))

    # 4b. Associations Wi-Fi invalides.
    for mac, host in inv.hosts.items():
        ap = host.wifi_ap_mac
        if not ap:
            continue
        if ap not in inv.hosts:
            findings.append(Finding(
                "error", "wifi",
                f"« {_name(host)} » est associé en Wi-Fi à une MAC inconnue "
                f"({ap}).", (mac,)))
        elif _resolve_device_type(inv.hosts[ap]) not in _AP_TYPES:
            findings.append(Finding(
                "warning", "wifi",
                f"« {_name(host)} » est associé en Wi-Fi à "
                f"« {_name(inv.hosts[ap])} », qui n'est pas un point d'accès.",
                (mac, ap)))

    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9),
                                 f.category))
    return findings
