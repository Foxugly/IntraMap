# Render Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply 5 cumulative visual improvements to the renderers: hierarchical layout, category colors, Wi-Fi edges (new `Host.wifi_ap_mac` field), auto-legend cluster, cleaner labels with HTML formatting and SVG tooltips in Graphviz.

**Architecture:** Most changes are renderer-only and additive. One model field (`Host.wifi_ap_mac`) introduces a new annotation. A new constant `DEVICE_COLORS` in `intramap/renderers/icons.py` is the single source of color truth, shared by both renderers.

**Tech Stack:** Python 3.11+, existing pytest / PyYAML / Graphviz / PlantUML stack.

**Spec:** `docs/superpowers/specs/2026-05-25-render-improvements-design.md`

## File Structure

- Modify: `intramap/renderers/icons.py` — add `DEVICE_COLORS: dict[str, str]`
- Modify: `intramap/models.py` — add `Host.wifi_ap_mac`, validate in `from_dict`, normalize in `__post_init__`
- Modify: `intramap/renderers/plantuml.py` — layout directive, per-node color, Wi-Fi edges, cleaner labels, legend cluster
- Modify: `intramap/renderers/graphviz.py` — layout, per-node fillcolor, Wi-Fi edges, HTML labels, tooltips, legend cluster
- Modify: `tests/test_models.py`, `tests/test_renderers.py` — coverage for all new behavior

---

### Task 1: Hierarchical layout (both renderers)

**Files:**
- Modify: `intramap/renderers/plantuml.py`
- Modify: `intramap/renderers/graphviz.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_has_top_to_bottom_direction():
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory()
    out = render(inv)
    assert "top to bottom direction" in out


def test_graphviz_has_top_bottom_rankdir():
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory()
    out = render(inv)
    assert "rankdir=TB" in out
    assert "splines=ortho" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k "top_to_bottom or rankdir"`
Expected: 2 failures.

- [ ] **Step 3: Add layout directive to PlantUML**

In `intramap/renderers/plantuml.py`, find where the header `lines` list is built. Insert `"top to bottom direction"` as the second line, right after `"@startuml"`:

Find:
```python
    lines: list[str] = [
        "@startuml",
        "skinparam node<<offline>> {",
```

Replace with:
```python
    lines: list[str] = [
        "@startuml",
        "top to bottom direction",
        "skinparam node<<offline>> {",
```

- [ ] **Step 4: Add layout attributes to Graphviz**

In `intramap/renderers/graphviz.py`, find where the header is built (looking for `lines = ["graph network {", ...]` or similar). Insert the layout attributes right after the graph opening:

Find (similar to):
```python
    lines: list[str] = [
        "graph network {",
        "  node [shape=box];",
```

Replace with:
```python
    lines: list[str] = [
        "graph network {",
        "  rankdir=TB;",
        "  splines=ortho;",
        "  nodesep=0.5;",
        "  ranksep=0.8;",
        "  node [shape=box];",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 135 tests pass (133 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add intramap/renderers/plantuml.py intramap/renderers/graphviz.py tests/test_renderers.py
git commit -m "feat: hierarchical top-to-bottom layout for both renderers"
```

---

### Task 2: DEVICE_COLORS table

**Files:**
- Modify: `intramap/renderers/icons.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_device_colors_cover_all_device_types():
    from intramap.models import DEVICE_TYPES
    from intramap.renderers.icons import DEVICE_COLORS

    assert set(DEVICE_COLORS.keys()) == set(DEVICE_TYPES)


def test_device_colors_use_expected_palette():
    from intramap.renderers.icons import DEVICE_COLORS

    expected = {
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
    assert DEVICE_COLORS == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k device_colors`
Expected: ImportError.

- [ ] **Step 3: Add DEVICE_COLORS to icons.py**

Append to `intramap/renderers/icons.py` (after `PLANTUML_SPRITES`):
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 137 tests pass (135 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/icons.py tests/test_renderers.py
git commit -m "feat: DEVICE_COLORS palette per device_type category"
```

---

### Task 3: PlantUML applies color per node

**Files:**
- Modify: `intramap/renderers/plantuml.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_online_host_has_color_suffix(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(vendor="Synology"),
    })
    out = render(inv)
    # device_type=nas → color #9467bd appears after node ID
    assert "#9467bd" in out


def test_plantuml_offline_host_has_no_color_suffix(make_host_factory):
    """Offline hosts keep their <<offline>> stereotype unmodified — no color
    suffix is appended (stereotype dominates the look)."""
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            vendor="Synology", online=False,
        ),
    })
    out = render(inv)
    # node line for offline host: contains <<offline>> but no color hex
    # offline stereotype takes precedence
    assert "<<offline>>" in out
    # the offline host's node line should not contain the nas color
    nas_color_lines = [l for l in out.splitlines() if "#9467bd" in l]
    assert nas_color_lines == []  # no color applied to this offline host
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k "color_suffix"`
Expected: 2 failures.

- [ ] **Step 3: Update PlantUML node emission to append color**

In `intramap/renderers/plantuml.py`, add to imports:
```python
from intramap.renderers.icons import PLANTUML_SPRITES, DEVICE_COLORS
```

Find the node emission code (a line like `lines.append(f'    node "{label}" as {node_id}...')` or similar). Identify the line that emits each node. Currently it looks like (or similar):
```python
        node_line = f'{indent}node "{label}" as {node_id}{stereotype}'
        lines.append(node_line)
```

Where `stereotype` is either ` <<offline>>` or `""`.

Update to append color suffix when the host is online:
```python
        if host.online:
            color = DEVICE_COLORS[_resolve_device_type(host)]
            color_suffix = f" {color}"
        else:
            color_suffix = ""
        node_line = f'{indent}node "{label}" as {node_id}{stereotype}{color_suffix}'
        lines.append(node_line)
```

(Adjust to match the actual variable names in the existing code.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 139 tests pass (137 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/plantuml.py tests/test_renderers.py
git commit -m "feat: PlantUML colors online nodes by device_type"
```

---

### Task 4: Graphviz applies fillcolor per node

**Files:**
- Modify: `intramap/renderers/graphviz.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_graphviz_online_host_has_fillcolor(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(vendor="Synology"),
    })
    out = render(inv)
    assert 'fillcolor="#9467bd"' in out
    assert "style=filled" in out


def test_graphviz_offline_host_keeps_color_but_dashed(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            vendor="Synology", online=False,
        ),
    })
    out = render(inv)
    assert 'fillcolor="#9467bd"' in out
    # offline combines filled and dashed
    assert 'style="filled,dashed"' in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k "fillcolor or keeps_color"`
Expected: 2 failures.

- [ ] **Step 3: Update Graphviz node emission**

In `intramap/renderers/graphviz.py`, add to imports:
```python
from intramap.renderers.icons import copy_icons_to, DEVICE_COLORS
```

Find the node attribute building code. Currently looks like:
```python
        device_type = _resolve_device_type(host)
        attrs = [
            f'label="{label_text}"',
            f'image="icons/{device_type}.svg"',
            'labelloc="b"',
            'imagescale=true',
        ]
        if not host.online:
            attrs.append("style=dashed")
            attrs.append('color="#888888"')
```

Update to add fillcolor and adjust style for online/offline:
```python
        device_type = _resolve_device_type(host)
        fillcolor = DEVICE_COLORS[device_type]
        attrs = [
            f'label="{label_text}"',
            f'image="icons/{device_type}.svg"',
            'labelloc="b"',
            'imagescale=true',
            f'fillcolor="{fillcolor}"',
        ]
        if host.online:
            attrs.append("style=filled")
        else:
            attrs.append('style="filled,dashed"')
            attrs.append('color="#888888"')
```

Important: the existing `style=dashed` line becomes `style="filled,dashed"` (combined), and `color="#888888"` (border color for offline) stays.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 141 tests pass (139 + 2 new). Pre-existing test `test_graphviz_offline_host_dashed` should still pass because the dashed style is still present in the combined `"filled,dashed"`.

If `test_graphviz_offline_host_dashed` previously asserted `"style=dashed"` exactly, update it to check for `"dashed"` substring or `"filled,dashed"`. Minimal change.

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/graphviz.py tests/test_renderers.py
git commit -m "feat: Graphviz colors nodes by device_type, preserves offline dashed style"
```

---

### Task 5: Host.wifi_ap_mac field

**Files:**
- Modify: `intramap/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_models.py`:
```python
def test_host_wifi_ap_mac_defaults_to_none(make_host_factory):
    h = make_host_factory()
    assert h.wifi_ap_mac is None


def test_host_wifi_ap_mac_normalized(make_host_factory):
    h = make_host_factory(wifi_ap_mac="AA-BB-CC-DD-EE-02")
    assert h.wifi_ap_mac == "aa:bb:cc:dd:ee:02"


def test_host_to_dict_includes_wifi_ap_mac(make_host_factory):
    h = make_host_factory(wifi_ap_mac="aa:bb:cc:dd:ee:02")
    d = h.to_dict()
    assert d["wifi_ap_mac"] == "aa:bb:cc:dd:ee:02"


def test_host_from_dict_reads_wifi_ap_mac():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10", "hostname": None, "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None, "device_type": None, "manual": False,
        "wifi_ap_mac": "aa:bb:cc:dd:ee:02",
        "first_seen": now, "last_seen": now, "online": True,
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.wifi_ap_mac == "aa:bb:cc:dd:ee:02"


def test_host_from_dict_missing_wifi_ap_mac_defaults_to_none():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10", "hostname": None, "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None, "device_type": None, "manual": False,
        "first_seen": now, "last_seen": now, "online": True,
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.wifi_ap_mac is None


def test_host_from_dict_wifi_ap_mac_bad_type_raises():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10", "hostname": None, "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None, "device_type": None, "manual": False,
        "wifi_ap_mac": 42,  # not a string
        "first_seen": now, "last_seen": now, "online": True,
    }
    with pytest.raises(ValueError, match="wifi_ap_mac"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_round_trip_with_wifi_ap_mac(make_host_factory):
    from intramap.models import Host
    h = make_host_factory(wifi_ap_mac="aa:bb:cc:dd:ee:02")
    restored = Host.from_dict(h.mac, h.to_dict())
    assert restored == h
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -v -k wifi`
Expected: failures because `Host` doesn't have `wifi_ap_mac` yet.

- [ ] **Step 3: Add wifi_ap_mac field**

In `intramap/models.py`, find the `Host` dataclass. Add `wifi_ap_mac` before `online`:

Old:
```python
@dataclass
class Host:
    # ... existing fields ...
    uplink: Uplink | None = None
    device_type: str | None = None
    manual: bool = False
    online: bool = True
```

New:
```python
@dataclass
class Host:
    # ... existing fields ...
    uplink: Uplink | None = None
    device_type: str | None = None
    manual: bool = False
    wifi_ap_mac: str | None = None
    online: bool = True
```

Update `__post_init__` to normalize `wifi_ap_mac`. Find:
```python
    def __post_init__(self) -> None:
        self.mac = normalize_mac(self.mac)
```

Replace with:
```python
    def __post_init__(self) -> None:
        self.mac = normalize_mac(self.mac)
        if self.wifi_ap_mac is not None:
            self.wifi_ap_mac = normalize_mac(self.wifi_ap_mac)
```

Update `to_dict` to include the field. Find the existing return dict and add the entry just after `"manual": self.manual,`:
```python
            "manual": self.manual,
            "wifi_ap_mac": self.wifi_ap_mac,
```

Update `from_dict`. Locate the existing `manual` validation block and add wifi_ap_mac validation right after, before the `return cls(...)`:
```python
        wifi_ap_mac = data.get("wifi_ap_mac")
        if wifi_ap_mac is not None and not isinstance(wifi_ap_mac, str):
            raise ValueError(
                f"Host {mac}: 'wifi_ap_mac' must be a string or null, got "
                f"{type(wifi_ap_mac).__name__} ({wifi_ap_mac!r})"
            )
```

Pass it through to the constructor in the `return cls(...)`:
```python
        return cls(
            # ... existing kwargs ...
            manual=manual,
            wifi_ap_mac=wifi_ap_mac,
            # ... rest ...
        )
```

Update the merge docstring (optional, doesn't need code change since merge already preserves user annotations).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 148 tests pass (141 + 7 new).

- [ ] **Step 5: Commit**

```bash
git add intramap/models.py tests/test_models.py
git commit -m "feat: Host.wifi_ap_mac for declaring Wi-Fi associations"
```

---

### Task 6: Wi-Fi edges in both renderers

**Files:**
- Modify: `intramap/renderers/plantuml.py`
- Modify: `intramap/renderers/graphviz.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_draws_wifi_edge_when_valid(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="TP-Link Systems",
            custom_name="AP RDC",
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Apple",
            custom_name="iPhone",
            wifi_ap_mac="aa:bb:cc:dd:ee:01",
        ),
    })
    out = render(inv)
    assert "..>" in out  # PlantUML dashed arrow
    assert "Wi-Fi" in out


def test_plantuml_wifi_edge_to_unknown_mac_skipped(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Apple",
            wifi_ap_mac="ff:ff:ff:ff:ff:ff",
        ),
    })
    out = render(inv)
    assert "Wi-Fi" not in out
    assert "..>" not in out


def test_graphviz_draws_wifi_edge_when_valid(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="TP-Link",
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Apple",
            wifi_ap_mac="aa:bb:cc:dd:ee:01",
        ),
    })
    out = render(inv)
    assert "style=dashed" in out
    assert "Wi-Fi" in out


def test_graphviz_wifi_edge_to_unknown_mac_skipped(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Apple",
            wifi_ap_mac="ff:ff:ff:ff:ff:ff",
        ),
    })
    out = render(inv)
    assert "Wi-Fi" not in out


def test_host_with_both_uplink_and_wifi_gets_two_edges(make_host_factory):
    """A laptop docked via Ethernet + associated to Wi-Fi backup should
    show BOTH edges in the diagram."""
    from intramap.models import Inventory, Uplink
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="TP-Link",  # AP
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Cisco",  # switch
            device_type="switch",
        ),
        "aa:bb:cc:dd:ee:03": make_host_factory(
            mac="aa:bb:cc:dd:ee:03", vendor="Intel Corporate",  # laptop
            uplink=Uplink(switch_mac="aa:bb:cc:dd:ee:02", switch_port=5),
            wifi_ap_mac="aa:bb:cc:dd:ee:01",
        ),
    })
    out = render(inv)
    # one wired edge (to switch) and one Wi-Fi edge (to AP)
    assert out.count("--") >= 2  # naive but adequate count
    assert "Wi-Fi" in out
    assert "sw:5" in out  # wired uplink label
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k "wifi"`
Expected: failures.

- [ ] **Step 3: PlantUML — emit Wi-Fi edges**

In `intramap/renderers/plantuml.py`, find the section where uplink edges are emitted (after all packages, before `@enduml`). Likely a loop like:

```python
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        u = host.uplink
        if u is None or u.switch_mac is None:
            continue
        if u.switch_mac not in node_ids:
            continue
        # ... emit uplink edge
```

Right after that loop (still before `@enduml`), add a second loop for Wi-Fi edges:
```python
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        if host.wifi_ap_mac is None:
            continue
        if host.wifi_ap_mac not in node_ids:
            continue
        src = node_ids[host.mac]
        dst = node_ids[host.wifi_ap_mac]
        lines.append(f'{src} ..> {dst} : "Wi-Fi"')
```

- [ ] **Step 4: Graphviz — emit Wi-Fi edges**

In `intramap/renderers/graphviz.py`, find the analogous uplink edge emission section. Add a sibling loop for Wi-Fi:

```python
    for mac in sorted(inv.hosts.keys()):
        host = inv.hosts[mac]
        if host.wifi_ap_mac is None:
            continue
        if host.wifi_ap_mac not in node_ids:
            continue
        src = node_ids[host.mac]
        dst = node_ids[host.wifi_ap_mac]
        lines.append(
            f'  {src} -- {dst} [style=dashed, color="#1f77b4", '
            f'label="Wi-Fi", fontsize=10];'
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 153 tests pass (148 + 5 new).

- [ ] **Step 6: Commit**

```bash
git add intramap/renderers/plantuml.py intramap/renderers/graphviz.py tests/test_renderers.py
git commit -m "feat: Wi-Fi edges in both renderers (dashed, labeled)"
```

---

### Task 7: Cleaner labels — PlantUML omits null IP

**Files:**
- Modify: `intramap/renderers/plantuml.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_label_omits_ip_when_null(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", ip=None,
            custom_name="Switch principal", vendor=None,
        ),
    })
    out = render(inv)
    # MAC present
    assert "aa:bb:cc:dd:ee:01" in out
    # No "None" or "?" appearing as IP placeholder in the label
    # We expect the label to be "Switch principal\nMAC" (2 lines, not 3)
    assert "Switch principal\\nNone" not in out
    assert "Switch principal\\n?" not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_renderers.py -v -k label_omits_ip`
Expected: failure (current code outputs "?" or "None" for ip).

- [ ] **Step 3: Update PlantUML label construction**

In `intramap/renderers/plantuml.py`, find the helper that builds a label (often `_label(host)` returning a string with `\n` separators). It currently looks something like:

```python
def _label(host: Host) -> str:
    name = host.custom_name or host.mac
    ip = host.ip or "?"
    return _escape(f"{name}\\n{ip}\\n{host.mac}")
```

Replace with a version that filters out empty lines:
```python
def _label(host: Host) -> str:
    name = host.custom_name or host.mac
    lines = [name]
    if host.ip:
        lines.append(host.ip)
    lines.append(host.mac)
    return _escape("\\n".join(lines))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 154 tests pass (153 + 1 new). Existing tests that check for label content (`"NAS\\n192.168.1.10\\n00:11:32:..."`) should still pass.

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/plantuml.py tests/test_renderers.py
git commit -m "feat: PlantUML omits null IP from node labels"
```

---

### Task 8: HTML labels + tooltips in Graphviz

**Files:**
- Modify: `intramap/renderers/graphviz.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_graphviz_uses_html_labels(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", custom_name="NAS",
            vendor="Synology",
        ),
    })
    out = render(inv)
    # HTML labels start with < not " (Graphviz convention)
    assert "label=<" in out
    # Bold tag for the name
    assert "<B>NAS</B>" in out
    # Smaller font for IP / MAC
    assert "<BR/>" in out


def test_graphviz_html_label_omits_ip_when_null(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", ip=None,
            custom_name="Switch", vendor=None,
        ),
    })
    out = render(inv)
    # MAC line still present
    assert "aa:bb:cc:dd:ee:01" in out
    # No literal "None" leaking into the label
    assert ">None<" not in out


def test_graphviz_has_tooltip(make_host_factory):
    from datetime import datetime
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    last = datetime(2026, 5, 24, 10, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
            last_seen=last,
        ),
    })
    out = render(inv)
    assert "tooltip=" in out
    assert "Synology" in out
    # last seen date present in tooltip
    assert "2026-05-24" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k "html_label or tooltip"`
Expected: failures.

- [ ] **Step 3: Replace text label with HTML label + add tooltip**

In `intramap/renderers/graphviz.py`, add (or extend) the label helper. Add an HTML-escape helper and an HTML label builder near the existing label code:

```python
def _escape_html(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _html_label(host: Host) -> str:
    """Build a Graphviz HTML label with differentiated text sizes."""
    name = _escape_html(host.custom_name or host.mac)
    parts = [f"<B>{name}</B>"]
    if host.ip:
        parts.append(f'<FONT POINT-SIZE="10">{_escape_html(host.ip)}</FONT>')
    parts.append(
        f'<FONT POINT-SIZE="9" COLOR="#666666">{_escape_html(host.mac)}</FONT>'
    )
    return "<" + "<BR/>".join(parts) + ">"


def _tooltip(host: Host) -> str:
    vendor = host.vendor or "unknown"
    last = host.last_seen.date().isoformat()
    return f"{vendor} | last seen {last}"
```

Update the node attribute construction. Find the existing `attrs` list build. The label entry currently looks like `f'label="{label_text}"'` — change to use HTML label (no quotes around it, since Graphviz HTML labels use `<...>` directly):

Replace the existing `f'label="{label_text}"'` with `f'label={_html_label(host)}'`.

Add the tooltip attribute right after:
```python
        attrs = [
            f'label={_html_label(host)}',
            f'tooltip="{_tooltip(host)}"',
            f'image="icons/{device_type}.svg"',
            # ... rest unchanged ...
        ]
```

- [ ] **Step 4: Update existing tests that asserted the old text-label format**

Pre-existing tests that asserted on a literal `label="..."` format may now fail because the format is `label=<...>`. Check `tests/test_renderers.py` for assertions like `'label="..."'` in Graphviz tests. Update each minimal assertion to the new HTML format OR check for a substring like `<B>name</B>`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 157 tests pass (154 + 3 new).

- [ ] **Step 6: Commit**

```bash
git add intramap/renderers/graphviz.py tests/test_renderers.py
git commit -m "feat: Graphviz HTML labels with sized text + SVG tooltips"
```

---

### Task 9: Legend cluster in PlantUML

**Files:**
- Modify: `intramap/renderers/plantuml.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_emits_legend_cluster(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(vendor="Synology"),
    })
    out = render(inv)
    assert 'package "Légende"' in out
    # the used device_type appears in the legend
    assert "legend_nas" in out or "nas" in out.split('package "Légende"', 1)[1]


def test_plantuml_legend_only_lists_used_types(make_host_factory):
    """Legend only mentions device_types actually present in the inventory."""
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(vendor="Synology"),  # nas only
    })
    out = render(inv)
    legend = out.split('package "Légende"', 1)[1]
    # 'nas' is in the legend, but 'router' is not (no router in inventory)
    assert "nas" in legend
    assert "router" not in legend
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k legend`
Expected: failures.

- [ ] **Step 3: Emit the legend cluster in PlantUML**

In `intramap/renderers/plantuml.py`, after all packages and all edges (Wi-Fi + uplinks), and BEFORE `@enduml`, emit a legend cluster.

Compute the used device_types (same as before for the sprite includes). Then:
```python
    # ... after all edges are appended ...

    used_types = sorted({_resolve_device_type(h) for h in inv.hosts.values()})
    if used_types:
        lines.append('package "Légende" {')
        for t in used_types:
            sprite = PLANTUML_SPRITES[t]
            color = DEVICE_COLORS[t]
            lines.append(
                f'  node "<${sprite}>\\n{t}" as legend_{t} {color}'
            )
        lines.append("}")

    lines.append("@enduml")
```

(Don't append `@enduml` twice — find the existing one and ensure the legend is inserted before it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 159 tests pass (157 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/plantuml.py tests/test_renderers.py
git commit -m "feat: PlantUML emits an auto Légende cluster"
```

---

### Task 10: Legend cluster in Graphviz

**Files:**
- Modify: `intramap/renderers/graphviz.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_graphviz_emits_legend_cluster(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(vendor="Synology"),
    })
    out = render(inv)
    assert 'subgraph cluster_legend' in out
    assert 'label="Légende"' in out
    # used type appears
    assert "legend_nas" in out


def test_graphviz_legend_only_lists_used_types(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(vendor="Synology"),
    })
    out = render(inv)
    legend = out.split('subgraph cluster_legend', 1)[1]
    assert "legend_nas" in legend
    assert "legend_router" not in legend
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_renderers.py -v -k "graphviz.*legend"`
Expected: failures.

- [ ] **Step 3: Emit the legend cluster in Graphviz**

In `intramap/renderers/graphviz.py`, right after all edges are appended and before the closing `lines.append("}")` of the outer graph, add:

```python
    used_types = sorted({_resolve_device_type(h) for h in inv.hosts.values()})
    if used_types:
        lines.append('  subgraph cluster_legend {')
        lines.append('    label="Légende";')
        lines.append('    style=dashed;')
        for t in used_types:
            color = DEVICE_COLORS[t]
            lines.append(
                f'    legend_{t} [label="{t}", image="icons/{t}.svg", '
                f'labelloc=b, imagescale=true, fillcolor="{color}", style=filled];'
            )
        lines.append("  }")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: 161 tests pass (159 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/graphviz.py tests/test_renderers.py
git commit -m "feat: Graphviz emits an auto Légende cluster"
```

---

### Task 11: README update + end-to-end verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the new field and improvements**

Add a section to `README.md` (insert before "Acknowledgements") :
```markdown
## Wi-Fi associations and visual hints

Declare a Wi-Fi association on any host by setting `wifi_ap_mac` to the MAC
of the upstream access point (must be a host in the inventory):

```yaml
aa:bb:cc:dd:ee:03:
  ip: 192.168.1.50
  custom_name: iPhone
  wifi_ap_mac: aa:bb:cc:dd:ee:01   # MAC of the AP
  # ... other fields ...
```

The renderer draws a dashed edge labeled "Wi-Fi" from the host to the AP.
A host can have both a wired `uplink` and a `wifi_ap_mac` — both edges are
drawn.

### Diagram features

- Hierarchical top-to-bottom layout
- Node color by device category (router, switch, NAS, IoT, etc.)
- PoE edges drawn in orange, Wi-Fi edges drawn dashed blue
- Auto-generated legend cluster at the bottom of each diagram
- Cleaner labels with smaller IP/MAC text
- Graphviz SVG output includes `<title>` tooltips with vendor and last-seen info
```

- [ ] **Step 2: Re-render the real inventory to verify**

Run (with PATH set up for nmap and Graphviz):
```powershell
PATH="/c/Program Files (x86)/Nmap:/c/Program Files/Graphviz/bin:$PATH" python -m intramap render
PATH="/c/Program Files/Graphviz/bin:$PATH" dot -Tsvg output/network.dot -o output/network.svg
```

Open `output/network.svg` in a browser. Visually verify:
- Hierarchical top-down layout
- Nodes are colored by category
- Legend cluster at the bottom listing each used device_type
- (If wifi_ap_mac is set on any host in the real inventory) dashed Wi-Fi edges appear

- [ ] **Step 3: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: ~161 tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README documents wifi_ap_mac and new diagram features"
```

---

## Self-Review Notes

**Spec coverage:**
- §3 Layout → Task 1
- §4 Couleur (DEVICE_COLORS + PlantUML + Graphviz) → Tasks 2, 3, 4
- §5 Wi-Fi (champ + edges) → Tasks 5, 6
- §6 Légende → Tasks 9, 10
- §7 Labels propres + tooltips → Tasks 7, 8
- §11 Hors-portée respecté

**Placeholders:** none.

**Type consistency:**
- `DEVICE_COLORS: dict[str, str]` (Task 2, used in 3, 4, 9, 10)
- `Host.wifi_ap_mac: str | None = None` (Task 5, used in 6)
- `_resolve_device_type(host) -> str` continues to be the single resolution function (Tasks 3, 4, 6, 9, 10)
- Wi-Fi edge label literal `"Wi-Fi"` consistent across PlantUML and Graphviz (Task 6)
