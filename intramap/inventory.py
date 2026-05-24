import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

import yaml

from intramap.models import DiscoveredHost, Host, Inventory, Location


def load(path: str | Path) -> Inventory:
    """Load an Inventory from a YAML file. Returns an empty Inventory if the
    file does not exist. Raises on parse errors (caller must handle)."""
    p = Path(path)
    if not p.exists():
        return Inventory()
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Inventory.from_dict(data)


def save(inv: Inventory, path: str | Path) -> None:
    """Write an Inventory to YAML atomically.

    Writes to a temp file in the same directory, then renames over the
    destination. If anything fails the original file (if any) is preserved.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=p.name + ".",
        suffix=".tmp",
        dir=str(p.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(inv.to_dict(), f, sort_keys=False, allow_unicode=True)
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

    - New MAC: added with empty custom_name/location/uplink,
      first_seen=last_seen=now
    - Existing MAC: ip/hostname/vendor/last_seen updated, online=True;
      custom_name/location/uplink/first_seen preserved
    - Existing MAC absent from discovered: online=False, all other fields preserved
    """
    discovered_by_mac = {d.mac: d for d in discovered}

    for mac, d in discovered_by_mac.items():
        if mac in inv.hosts:
            h = inv.hosts[mac]
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
                uplink=None,
                online=True,
            )

    for mac, h in inv.hosts.items():
        if mac not in discovered_by_mac:
            h.online = False

    inv.last_scan = now
