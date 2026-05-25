"""Per-device-type icon mapping for the PlantUML and Graphviz renderers.

`PLANTUML_SPRITES` maps each `device_type` to the FontAwesome 6 sprite name
that PlantUML's stdlib exposes via `!include <font-awesome-6/<sprite>>`.

`copy_icons_to(out_dir, types)` copies the SVG files of the requested types
from the package's bundled icons into `<out_dir>/icons/` for Graphviz to
reference at render time.
"""
import shutil
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from intramap.models import DEVICE_TYPES


PLANTUML_SPRITES: dict[str, str] = {
    "router": "network_wired",
    "switch": "share_nodes",
    "ap": "wifi",
    "controller": "sliders",
    "nas": "hard_drive",
    "tv": "tv",
    "stb": "clapperboard",
    "phone": "mobile_screen_button",
    "tablet": "tablet_screen_button",
    "laptop": "laptop",
    "iot": "house_signal",
    "camera": "video",
    "printer": "print",
    "voip": "phone_volume",
    "other": "question",
}

DEVICE_COLORS: dict[str, str] = {
    "router": "#1f77b4",
    "switch": "#2ca02c",
    "ap": "#2ca02c",
    "controller": "#2ca02c",
    "nas": "#9467bd",
    "tv": "#ff7f0e",
    "stb": "#ff7f0e",
    "phone": "#7f7f7f",
    "tablet": "#7f7f7f",
    "laptop": "#7f7f7f",
    "iot": "#e377c2",
    "camera": "#e377c2",
    "voip": "#bcbd22",
    "printer": "#bcbd22",
    "other": "#cccccc",
}


def copy_icons_to(out_dir: str | Path, types: Iterable[str]) -> None:
    """Copy the SVG icons for the given device_types into <out_dir>/icons/.

    Raises ValueError (BEFORE creating any files) if a requested type is
    not in DEVICE_TYPES, so the output directory is never left in a
    partial state.
    """
    types_list = list(types)
    unknown = [t for t in types_list if t not in DEVICE_TYPES]
    if unknown:
        raise ValueError(
            f"Unknown device_type(s): {sorted(set(unknown))!r}"
        )

    out_dir = Path(out_dir)
    icons_out = out_dir / "icons"
    icons_out.mkdir(parents=True, exist_ok=True)

    src_root = files("intramap.renderers") / "icons"
    for t in types_list:
        src = src_root / f"{t}.svg"
        dst = icons_out / f"{t}.svg"
        with src.open("rb") as fsrc, open(dst, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)
