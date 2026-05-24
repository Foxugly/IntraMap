import os
import tempfile
from pathlib import Path

import yaml

from intramap.models import Inventory


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
