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
    """Write an Inventory to YAML."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(inv.to_dict(), f, sort_keys=False, allow_unicode=True)
