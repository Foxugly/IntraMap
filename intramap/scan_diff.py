"""Diff entre deux états d'inventaire (avant / après un scan).

Sans dépendance Qt : réutilisé par le CLI (`scan`) et le GUI (dialogue
post-scan). ``merge()`` n'enlève jamais d'hôte (il marque hors ligne), donc on
ne traite pas de catégorie « supprimé ».
"""
from __future__ import annotations

from dataclasses import dataclass

from intramap.i18n import tr
from intramap.models import Inventory


@dataclass(frozen=True)
class ScanDiff:
    appeared: list[str]
    gone_offline: list[str]
    back_online: list[str]
    ip_changed: list[tuple[str, str | None, str | None]]

    @property
    def has_changes(self) -> bool:
        return bool(self.appeared or self.gone_offline
                    or self.back_online or self.ip_changed)


def diff_inventories(before: Inventory, after: Inventory) -> ScanDiff:
    """Compare deux inventaires (apparus / hors ligne / revenus / IP changée)."""
    before_macs = set(before.hosts)
    after_macs = set(after.hosts)

    appeared = sorted(after_macs - before_macs)
    gone_offline: list[str] = []
    back_online: list[str] = []
    ip_changed: list[tuple[str, str | None, str | None]] = []

    for mac in sorted(before_macs & after_macs):
        b, a = before.hosts[mac], after.hosts[mac]
        if b.online and not a.online:
            gone_offline.append(mac)
        elif not b.online and a.online:
            back_online.append(mac)
        if b.ip != a.ip:
            ip_changed.append((mac, b.ip, a.ip))

    return ScanDiff(appeared, gone_offline, back_online, ip_changed)


def _name(host) -> str:
    return host.custom_name or host.hostname or host.mac


def format_scan_diff(diff: ScanDiff, inv: Inventory) -> str:
    """Texte multi-lignes résumant le diff (noms d'appareils résolus)."""
    def label(mac: str) -> str:
        host = inv.hosts.get(mac)
        return f"{_name(host)} [{mac}]" if host is not None else mac

    lines: list[str] = []
    if diff.appeared:
        lines.append(tr("Nouveaux ({n}) :").format(n=len(diff.appeared)))
        lines += [f"  + {label(m)}" for m in diff.appeared]
    if diff.gone_offline:
        lines.append(
            tr("Passés hors ligne ({n}) :").format(n=len(diff.gone_offline)))
        lines += [f"  - {label(m)}" for m in diff.gone_offline]
    if diff.back_online:
        lines.append(
            tr("Revenus en ligne ({n}) :").format(n=len(diff.back_online)))
        lines += [f"  ↑ {label(m)}" for m in diff.back_online]
    if diff.ip_changed:
        lines.append(tr("IP modifiée ({n}) :").format(n=len(diff.ip_changed)))
        lines += [f"  ~ {label(m)} : {old or '—'} → {new or '—'}"
                  for m, old, new in diff.ip_changed]
    if not lines:
        return tr("Aucun changement depuis le dernier scan.") + "\n"
    return "\n".join(lines) + "\n"
