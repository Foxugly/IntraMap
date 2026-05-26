import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml

from intramap.models import DiscoveredHost, Host, Inventory, Location


def load(path: str | Path) -> Inventory:
    """Load an Inventory from a YAML file. Returns an empty Inventory if the
    file does not exist. Raises on parse errors (caller must handle).

    The optional top-level ``layout`` key (GUI presentation state) is ignored
    here: it is not part of the network data model. Use
    :func:`load_layout_dict` to read it.
    """
    p = Path(path)
    if not p.exists():
        return Inventory()
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Inventory.from_dict(data)


def load_layout_dict(path: str | Path) -> dict:
    """Return the raw ``layout`` mapping from the inventory file (or ``{}``).

    The ``layout`` section holds GUI presentation state (node positions, edge
    bends, routing style). It is optional and ignored by the data model and
    the CLI. A missing/invalid section yields ``{}``.
    """
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    layout = data.get("layout")
    return layout if isinstance(layout, dict) else {}


def save(inv: Inventory, path: str | Path, layout: dict | None = None) -> None:
    """Write an Inventory to YAML atomically.

    Writes to a temp file in the same directory, then renames over the
    destination. If anything fails the original file (if any) is preserved.

    ``layout`` is the optional GUI presentation section. When given, it is
    written under the top-level ``layout`` key. When omitted (e.g. the CLI
    ``scan`` command), any ``layout`` section already present in the file is
    preserved, so re-scanning never discards the user's map arrangement.
    """
    p = Path(path)
    if layout is None:
        layout = load_layout_dict(p) or None

    data = inv.to_dict()  # {"last_scan": ..., "links": [...], "hosts": {...}}
    document: dict = {"last_scan": data.get("last_scan")}
    if layout:
        document["layout"] = layout
    # CRUCIAL : on persiste les liaisons (câbles), maintenant centralisées
    # dans Inventory.links (et plus disséminées par hôte).
    document["links"] = data.get("links", [])
    document["hosts"] = data.get("hosts", {})

    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=p.name + ".",
        suffix=".tmp",
        dir=str(p.parent),
    )
    try:
        try:
            f = os.fdopen(fd, "w", encoding="utf-8")
        except Exception:
            os.close(fd)
            raise
        with f:
            yaml.safe_dump(document, f, sort_keys=False, allow_unicode=True)
        os.replace(tmp_name, p)
    except Exception:
        # On any failure, remove temp file if it still exists
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise


def merge(inv: Inventory, discovered: Iterable[DiscoveredHost],
          now: datetime) -> None:
    """Merge a list of newly discovered hosts into the inventory in place.

    - New MAC: added with empty custom_name/location/liaisons,
      first_seen=last_seen=now, manual=False
    - Existing MAC, manual=False: ip/hostname/vendor/last_seen updated,
      online=True; custom_name/location/liaisons/wifi_ap_mac/first_seen preserved
    - Existing MAC, manual=True: ignored entirely (no update, no offline marking)
    - Existing MAC absent from discovered, manual=False: online=False, other fields preserved
    """
    discovered_by_mac = {d.mac: d for d in discovered}

    for mac, d in discovered_by_mac.items():
        if mac in inv.hosts:
            h = inv.hosts[mac]
            if h.manual:
                continue  # manual entries are user-managed; do not overwrite
            h.ip = d.ip
            h.hostname = d.hostname
            h.vendor = d.vendor
            h.last_seen = now
            h.online = True
        else:
            inv.hosts[mac] = Host(
                mac=mac,
                ip=d.ip,
                hostname=d.hostname,
                vendor=d.vendor,
                first_seen=now,
                last_seen=now,
                custom_name=None,
                location=Location(),
                online=True,
            )

    for mac, h in inv.hosts.items():
        if h.manual:
            continue  # manual entries keep their declared online state
        if mac not in discovered_by_mac:
            h.online = False

    inv.last_scan = now
