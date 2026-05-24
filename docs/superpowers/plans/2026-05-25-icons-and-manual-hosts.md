# Icons & Manual Hosts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add device-type icons to PlantUML and Graphviz diagrams (auto-detected from vendor, overridable per host) and a `manual: true` flag that exempts hand-added inventory entries (e.g. unmanaged switches) from the scan/merge cycle.

**Architecture:** Extend the existing model with `Host.device_type` and `Host.manual` fields. Add a `DEVICE_TYPES` catalogue + `infer_device_type` / `_resolve_device_type` helpers in `models.py`. Update the merge to bypass manual hosts. Add a new `intramap/renderers/icons.py` module that maps each `device_type` to a FontAwesome 6 sprite name (PlantUML) and bundles SVG files (Graphviz). Update both renderers to emit icons. Update CLI `list` with a `Type` column and `--type` filter.

**Tech Stack:** Python 3.11+, FontAwesome Free 6 SVG icons (CC BY 4.0), `importlib.resources` for asset lookup, setuptools `package-data` for bundling, existing `pytest` / `PyYAML` / `python-nmap` stack.

**Spec:** `docs/superpowers/specs/2026-05-25-icons-and-manual-hosts-design.md`

**Refinement vs spec**: spec says PNG icons; this plan uses SVG instead. Reason: FA Free distributes SVG natively (no conversion needed); Graphviz accepts SVG as `image=` for both PNG and SVG outputs; ~10 KB total.

## File Structure

- Modify: `intramap/models.py` — add `DEVICE_TYPES`, `infer_device_type`, `_resolve_device_type`, `Host.device_type`, `Host.manual`, validation in `Host.from_dict`
- Modify: `intramap/inventory.py` — `merge` skips `manual=True` hosts
- Create: `intramap/renderers/icons.py` — `PLANTUML_SPRITES`, `copy_icons_to`
- Create: `intramap/renderers/icons/<type>.svg` × 15 — bundled FA icons
- Create: `intramap/renderers/icons/LICENSE` — CC BY 4.0 text
- Modify: `intramap/renderers/plantuml.py` — emit `!include` directives + sprite-prefixed node labels
- Modify: `intramap/renderers/graphviz.py` — emit `image=` per node + invoke icon copy
- Modify: `intramap/cli.py` — `Type` column in `list`, `--type` filter
- Modify: `pyproject.toml` — `[tool.setuptools.package-data]` for the SVGs and LICENSE
- Modify: `README.md` — FA attribution line
- Modify: `tests/test_models.py`, `tests/test_inventory.py`, `tests/test_renderers.py`, `tests/test_cli.py`

---

### Task 1: DEVICE_TYPES catalogue + infer + resolve helpers

Adds the static catalogue, the vendor → type inference function, and the resolution helper that the renderers and the CLI will use. No new Host fields yet — that's Task 2.

**Files:**
- Modify: `intramap/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_models.py`:
```python
import pytest

from intramap.models import (
    DEVICE_TYPES,
    infer_device_type,
    _resolve_device_type,
)


def test_device_types_catalogue_is_15_known_values():
    expected = {
        "router", "switch", "ap", "controller", "nas",
        "tv", "stb", "phone", "tablet", "laptop",
        "iot", "camera", "printer", "voip", "other",
    }
    assert DEVICE_TYPES == expected


@pytest.mark.parametrize("vendor, expected", [
    ("Sagemcom Broadband SAS", "router"),
    ("Vantiva USA", "router"),
    ("Synology Incorporated", "nas"),
    ("QNAP Systems", "nas"),
    ("Cisco Systems", "switch"),
    ("TP-Link Systems", "ap"),
    ("LG Electronics", "tv"),
    ("Samsung Electronics", "tv"),
    ("Apple Inc", "phone"),
    ("Hikvision", "camera"),
    ("Bticino SPA", "camera"),
    ("Intel Corporate", "laptop"),
    ("Universal Global Scientific Industrial.", "laptop"),
    ("Tuya Smart", "iot"),
    ("tado GmbH", "iot"),
    ("Davicom Semiconductor", "iot"),
    ("Grandstream Networks", "voip"),
    ("Canon Inc", "printer"),
])
def test_infer_device_type_known_vendors(vendor, expected):
    assert infer_device_type(vendor) == expected


def test_infer_device_type_case_insensitive():
    assert infer_device_type("SYNOLOGY INC") == "nas"
    assert infer_device_type("synology inc") == "nas"


def test_infer_device_type_unknown_returns_none():
    assert infer_device_type("Totally Unknown Vendor Ltd") is None


def test_infer_device_type_none_input_returns_none():
    assert infer_device_type(None) is None


def test_resolve_device_type_explicit_wins(make_host_factory):
    h = make_host_factory(vendor="Synology", device_type="laptop")
    assert _resolve_device_type(h) == "laptop"


def test_resolve_device_type_falls_back_to_inferred(make_host_factory):
    h = make_host_factory(vendor="Synology Incorporated", device_type=None)
    assert _resolve_device_type(h) == "nas"


def test_resolve_device_type_invalid_explicit_falls_back_to_other(make_host_factory):
    h = make_host_factory(vendor="Synology Incorporated", device_type="refrigerator")
    assert _resolve_device_type(h) == "other"


def test_resolve_device_type_no_match_no_explicit_returns_other(make_host_factory):
    h = make_host_factory(vendor="Totally Unknown", device_type=None)
    assert _resolve_device_type(h) == "other"
```

Also add this fixture at the top of `tests/test_models.py` (just below existing imports):
```python
from datetime import datetime

import pytest


@pytest.fixture
def make_host_factory():
    """Return a function that builds a Host with sensible defaults."""
    from intramap.models import Host, Location  # local import to avoid early failure

    def _make(**kwargs):
        now = datetime(2026, 5, 25, 0, 0, 0)
        defaults = dict(
            mac="aa:bb:cc:dd:ee:01",
            ip="192.168.1.1",
            hostname=None,
            vendor=None,
            first_seen=now,
            last_seen=now,
        )
        defaults.update(kwargs)
        return Host(**defaults)
    return _make
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py::test_device_types_catalogue_is_15_known_values -v`
Expected: `ImportError: cannot import name 'DEVICE_TYPES'` (or similar).

- [ ] **Step 3: Implement DEVICE_TYPES + infer + resolve**

Append to `intramap/models.py` (after the existing dataclasses):
```python
DEVICE_TYPES: frozenset[str] = frozenset({
    "router", "switch", "ap", "controller", "nas",
    "tv", "stb", "phone", "tablet", "laptop",
    "iot", "camera", "printer", "voip", "other",
})


# Order matters: first matching pattern wins. Patterns are substring,
# case-insensitive.
_VENDOR_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("sagemcom", "vantiva", "technicolor", "arris"), "router"),
    (("synology", "qnap", "western digital", "seagate"), "nas"),
    (("cisco", "juniper", "aruba", "mikrotik", "netgear"), "switch"),
    (("tp-link", "ubiquiti", "unifi"), "ap"),
    (("lg electronics", "samsung electronics", "sony", "philips"), "tv"),
    (("apple", "google", "xiaomi", "huawei", "oneplus"), "phone"),
    (("hikvision", "dahua", "axis", "bticino"), "camera"),
    (("intel corporate", "dell", "lenovo", "asus", "hp inc",
      "universal global scientific"), "laptop"),
    (("tuya", "tado", "nest", "ring", "philips hue",
      "eedomus", "davicom"), "iot"),
    (("grandstream", "yealink", "polycom", "snom"), "voip"),
    (("canon", "epson", "brother industries"), "printer"),
]


def infer_device_type(vendor: str | None) -> str | None:
    """Map a raw vendor string to a device_type using substring patterns.

    Returns None if no pattern matches or vendor is None.
    """
    if not vendor:
        return None
    v = vendor.lower()
    for patterns, device_type in _VENDOR_PATTERNS:
        for p in patterns:
            if p in v:
                return device_type
    return None


def _resolve_device_type(host) -> str:
    """Return the device_type to use when rendering this host.

    Priority: explicit host.device_type (if in catalogue) > inferred from
    vendor > 'other'. An explicit value not in the catalogue silently
    falls back to 'other'.
    """
    explicit = getattr(host, "device_type", None)
    if explicit is not None:
        return explicit if explicit in DEVICE_TYPES else "other"
    inferred = infer_device_type(getattr(host, "vendor", None))
    return inferred or "other"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: all tests including the new ones pass.

- [ ] **Step 5: Commit**

```bash
git add intramap/models.py tests/test_models.py
git commit -m "feat: DEVICE_TYPES catalogue + infer_device_type + _resolve_device_type"
```

---

### Task 2: Host.device_type + Host.manual fields with round-trip and validation

Adds the two new fields, makes them serialise/deserialise cleanly through `to_dict`/`from_dict`, validates their types, and ensures backward compatibility with existing YAML files (which lack these keys).

**Files:**
- Modify: `intramap/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_models.py`:
```python
def test_host_device_type_defaults_to_none(make_host_factory):
    h = make_host_factory()
    assert h.device_type is None


def test_host_manual_defaults_to_false(make_host_factory):
    h = make_host_factory()
    assert h.manual is False


def test_host_to_dict_includes_new_fields(make_host_factory):
    h = make_host_factory(device_type="nas", manual=True)
    d = h.to_dict()
    assert d["device_type"] == "nas"
    assert d["manual"] is True


def test_host_from_dict_reads_new_fields():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        "device_type": "nas",
        "manual": True,
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.device_type == "nas"
    assert h.manual is True


def test_host_from_dict_missing_new_fields_uses_defaults():
    """Backward compatibility: existing YAMLs without device_type/manual load
    with the new defaults (None and False)."""
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        # no device_type, no manual
    }
    h = Host.from_dict("aa:bb:cc:dd:ee:01", data)
    assert h.device_type is None
    assert h.manual is False


def test_host_from_dict_device_type_bad_type_raises():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        "device_type": 42,  # not a string
    }
    with pytest.raises(ValueError, match="device_type"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_from_dict_manual_bad_type_raises():
    from intramap.models import Host
    now = "2026-05-25T00:00:00"
    data = {
        "ip": "192.168.1.10",
        "hostname": None,
        "vendor": None,
        "custom_name": None,
        "location": {"floor": None, "room": None, "rack": None, "rack_unit": None},
        "uplink": None,
        "first_seen": now,
        "last_seen": now,
        "online": True,
        "manual": "yes",  # not a bool
    }
    with pytest.raises(ValueError, match="manual"):
        Host.from_dict("aa:bb:cc:dd:ee:01", data)


def test_host_round_trip_with_new_fields():
    from intramap.models import Host
    from datetime import datetime
    now = datetime(2026, 5, 25, 0, 0, 0)
    h = Host(
        mac="aa:bb:cc:dd:ee:01",
        ip="192.168.1.10",
        hostname=None,
        vendor="Synology",
        first_seen=now,
        last_seen=now,
        device_type="nas",
        manual=True,
    )
    restored = Host.from_dict(h.mac, h.to_dict())
    assert restored == h
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v -k "device_type or manual"`
Expected: failures complaining `device_type` / `manual` are not fields of `Host`, or that the dict roundtrip drops them.

- [ ] **Step 3: Modify the `Host` dataclass and `from_dict`/`to_dict`**

In `intramap/models.py`, find the `Host` dataclass. Add the two new fields **before** `online` (keep `online` last so it stays the last keyword arg in tests/examples):

Old:
```python
@dataclass
class Host:
    mac: str
    ip: str | None
    hostname: str | None
    vendor: str | None
    first_seen: datetime
    last_seen: datetime
    custom_name: str | None = None
    location: Location = field(default_factory=Location)
    uplink: Uplink | None = None
    online: bool = True
```

New:
```python
@dataclass
class Host:
    mac: str
    ip: str | None
    hostname: str | None
    vendor: str | None
    first_seen: datetime
    last_seen: datetime
    custom_name: str | None = None
    location: Location = field(default_factory=Location)
    uplink: Uplink | None = None
    device_type: str | None = None
    manual: bool = False
    online: bool = True
```

Find `Host.to_dict()` and update the returned mapping to include the new fields:

Old:
```python
    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "custom_name": self.custom_name,
            "location": asdict(self.location),
            "uplink": asdict(self.uplink) if self.uplink is not None else None,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "online": self.online,
        }
```

New:
```python
    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "custom_name": self.custom_name,
            "location": asdict(self.location),
            "uplink": asdict(self.uplink) if self.uplink is not None else None,
            "device_type": self.device_type,
            "manual": self.manual,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "online": self.online,
        }
```

Find `Host.from_dict()` and update it to read the new fields with validation:

Old:
```python
    @classmethod
    def from_dict(cls, mac: str, data: dict) -> "Host":
        loc_data = data.get("location") or {}
        uplink_data = data.get("uplink")
        if uplink_data is None:
            uplink = None
        elif isinstance(uplink_data, dict):
            uplink = Uplink(**uplink_data)
        else:
            raise ValueError(
                f"Host {mac}: 'uplink' must be null or a mapping with fields "
                f"switch_mac/switch_port/patch_port/poe, got "
                f"{type(uplink_data).__name__} ({uplink_data!r}). Example:\n"
                f"  uplink:\n"
                f"    switch_mac: aa:bb:cc:dd:ee:ff\n"
                f"    switch_port: 4\n"
                f"    patch_port: 7\n"
                f"    poe: true"
            )
        return cls(
            mac=mac,
            ip=data.get("ip"),
            hostname=data.get("hostname"),
            vendor=data.get("vendor"),
            custom_name=data.get("custom_name"),
            location=Location(**loc_data),
            uplink=uplink,
            first_seen=_parse_dt(data["first_seen"]),
            last_seen=_parse_dt(data["last_seen"]),
            online=data.get("online", True),
        )
```

New (note the two added validations and the two new kwargs):
```python
    @classmethod
    def from_dict(cls, mac: str, data: dict) -> "Host":
        loc_data = data.get("location") or {}
        uplink_data = data.get("uplink")
        if uplink_data is None:
            uplink = None
        elif isinstance(uplink_data, dict):
            uplink = Uplink(**uplink_data)
        else:
            raise ValueError(
                f"Host {mac}: 'uplink' must be null or a mapping with fields "
                f"switch_mac/switch_port/patch_port/poe, got "
                f"{type(uplink_data).__name__} ({uplink_data!r}). Example:\n"
                f"  uplink:\n"
                f"    switch_mac: aa:bb:cc:dd:ee:ff\n"
                f"    switch_port: 4\n"
                f"    patch_port: 7\n"
                f"    poe: true"
            )

        device_type = data.get("device_type")
        if device_type is not None and not isinstance(device_type, str):
            raise ValueError(
                f"Host {mac}: 'device_type' must be a string or null, got "
                f"{type(device_type).__name__} ({device_type!r})"
            )

        manual = data.get("manual", False)
        if not isinstance(manual, bool):
            raise ValueError(
                f"Host {mac}: 'manual' must be a boolean (true/false), got "
                f"{type(manual).__name__} ({manual!r})"
            )

        return cls(
            mac=mac,
            ip=data.get("ip"),
            hostname=data.get("hostname"),
            vendor=data.get("vendor"),
            custom_name=data.get("custom_name"),
            location=Location(**loc_data),
            uplink=uplink,
            device_type=device_type,
            manual=manual,
            first_seen=_parse_dt(data["first_seen"]),
            last_seen=_parse_dt(data["last_seen"]),
            online=data.get("online", True),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: all model tests pass. Existing tests must continue to pass (backward compat).

Also run the full suite to confirm nothing breaks elsewhere:

Run: `pytest -v`
Expected: all existing tests still pass. Some inventory/CLI tests that build a `Host` with positional args could break — if so, they need updating to keyword args (likely already keyword-style).

- [ ] **Step 5: Commit**

```bash
git add intramap/models.py tests/test_models.py
git commit -m "feat: add Host.device_type and Host.manual with round-trip + validation"
```

---

### Task 3: Merge skips manual hosts

Updates `inventory.merge` so any host with `manual=True` is left untouched: not updated from a discovered MAC, not marked offline when absent.

**Files:**
- Modify: `intramap/inventory.py`
- Modify: `tests/test_inventory.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_inventory.py`:
```python
def test_merge_skips_manual_hosts_in_scan():
    """A discovered MAC that matches a manual=True host must NOT be updated."""
    from datetime import datetime
    from intramap.inventory import merge
    from intramap.models import DiscoveredHost, Host, Inventory, Location

    earlier = datetime(2026, 5, 1, 10, 0, 0)
    now = datetime(2026, 5, 25, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01",
            ip=None,
            hostname=None,
            vendor=None,
            custom_name="Switch principal",
            location=Location(floor="cave", room="local"),
            first_seen=earlier,
            last_seen=earlier,
            manual=True,
            online=True,
        ),
    }, last_scan=earlier)

    discovered = [DiscoveredHost(mac="aa:bb:cc:dd:ee:01",
                                 ip="192.168.1.5",
                                 hostname="something",
                                 vendor="SomeVendor")]
    merge(inv, discovered, now=now)

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    # NOT updated
    assert h.ip is None
    assert h.hostname is None
    assert h.vendor is None
    assert h.last_seen == earlier
    assert h.online is True
    # preserved
    assert h.custom_name == "Switch principal"
    assert h.manual is True


def test_merge_does_not_mark_manual_hosts_offline_when_absent():
    """A manual=True host absent from the scan must remain online=True."""
    from datetime import datetime
    from intramap.inventory import merge
    from intramap.models import Host, Inventory

    earlier = datetime(2026, 5, 1, 10, 0, 0)
    now = datetime(2026, 5, 25, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01",
            ip=None,
            hostname=None,
            vendor=None,
            custom_name="Switch principal",
            first_seen=earlier,
            last_seen=earlier,
            manual=True,
            online=True,
        ),
    }, last_scan=earlier)

    merge(inv, [], now=now)

    h = inv.hosts["aa:bb:cc:dd:ee:01"]
    assert h.online is True  # NOT marked offline
    assert h.last_seen == earlier  # untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_inventory.py -v -k manual`
Expected: both new tests fail — current merge updates everything.

- [ ] **Step 3: Update `merge` to skip manual hosts**

Find `merge` in `intramap/inventory.py`. Add early-skip logic in both loops:

Old:
```python
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
```

New (two `if h.manual: continue` guards added):
```python
def merge(inv: Inventory, discovered: Iterable[DiscoveredHost],
          now: datetime) -> None:
    """Merge a list of newly discovered hosts into the inventory in place.

    - New MAC: added with empty custom_name/location/uplink,
      first_seen=last_seen=now, manual=False
    - Existing MAC, manual=False: ip/hostname/vendor/last_seen updated,
      online=True; custom_name/location/uplink/first_seen preserved
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
                uplink=None,
                online=True,
            )

    for mac, h in inv.hosts.items():
        if h.manual:
            continue  # manual entries keep their declared online state
        if mac not in discovered_by_mac:
            h.online = False

    inv.last_scan = now
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_inventory.py -v`
Expected: all inventory tests pass including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add intramap/inventory.py tests/test_inventory.py
git commit -m "feat: merge skips manual=True hosts (no update, no offline marking)"
```

---

### Task 4: Bundle 15 FontAwesome SVG icons + LICENSE + package-data

Downloads the 15 FA Free 6 SVGs from the FortAwesome repo, renames each to our `device_type` and commits them. Also adds the LICENSE file and configures setuptools to include them in the installed package.

**Files:**
- Create: `intramap/renderers/icons/<type>.svg` × 15
- Create: `intramap/renderers/icons/LICENSE`
- Modify: `pyproject.toml`
- Modify: `tests/test_renderers.py` (small bundling sanity test)

The 15 mappings (our name → upstream FA name):

| File created | Source FA solid SVG |
|---|---|
| `router.svg` | `network-wired.svg` |
| `switch.svg` | `share-nodes.svg` |
| `ap.svg` | `wifi.svg` |
| `controller.svg` | `sliders.svg` |
| `nas.svg` | `hard-drive.svg` |
| `tv.svg` | `tv.svg` |
| `stb.svg` | `clapperboard.svg` |
| `phone.svg` | `mobile-screen-button.svg` |
| `tablet.svg` | `tablet-screen-button.svg` |
| `laptop.svg` | `laptop.svg` |
| `iot.svg` | `house-signal.svg` |
| `camera.svg` | `video.svg` |
| `printer.svg` | `print.svg` |
| `voip.svg` | `phone-volume.svg` |
| `other.svg` | `question.svg` |

Source base URL: `https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/<name>.svg`

- [ ] **Step 1: Write failing bundling test**

Append to `tests/test_renderers.py`:
```python
def test_all_15_device_type_icons_are_bundled():
    """Every value in DEVICE_TYPES must have a corresponding SVG file in
    the package, accessible via importlib.resources."""
    from importlib.resources import files

    from intramap.models import DEVICE_TYPES

    icons_root = files("intramap.renderers") / "icons"
    for device_type in DEVICE_TYPES:
        path = icons_root / f"{device_type}.svg"
        assert path.is_file(), f"missing icon: {path}"


def test_icons_license_is_bundled():
    from importlib.resources import files

    license_path = files("intramap.renderers") / "icons" / "LICENSE"
    assert license_path.is_file()
    content = license_path.read_text(encoding="utf-8")
    assert "Creative Commons" in content or "CC BY" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderers.py -v -k "bundled or license"`
Expected: failures because `intramap/renderers/icons/` directory does not exist yet.

- [ ] **Step 3: Create the icons directory and fetch the SVGs**

Create directory: `intramap/renderers/icons/`

Fetch the 15 SVGs and rename. Run this Python one-liner (or do it with curl/wget if available):

```bash
python -c "
import urllib.request
import pathlib

mapping = {
    'router.svg': 'network-wired.svg',
    'switch.svg': 'share-nodes.svg',
    'ap.svg': 'wifi.svg',
    'controller.svg': 'sliders.svg',
    'nas.svg': 'hard-drive.svg',
    'tv.svg': 'tv.svg',
    'stb.svg': 'clapperboard.svg',
    'phone.svg': 'mobile-screen-button.svg',
    'tablet.svg': 'tablet-screen-button.svg',
    'laptop.svg': 'laptop.svg',
    'iot.svg': 'house-signal.svg',
    'camera.svg': 'video.svg',
    'printer.svg': 'print.svg',
    'voip.svg': 'phone-volume.svg',
    'other.svg': 'question.svg',
}
out = pathlib.Path('intramap/renderers/icons')
out.mkdir(parents=True, exist_ok=True)
base = 'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/'
for local, remote in mapping.items():
    url = base + remote
    data = urllib.request.urlopen(url, timeout=10).read()
    (out / local).write_bytes(data)
    print(f'wrote {local} ({len(data)} bytes)')
"
```

Verify the directory now contains 15 SVG files.

- [ ] **Step 4: Add the LICENSE file**

Create `intramap/renderers/icons/LICENSE`:

```
Icons in this directory are from Font Awesome Free 6
(https://fontawesome.com/), licensed under the Creative Commons Attribution
4.0 International license (CC BY 4.0).

Full license text: https://creativecommons.org/licenses/by/4.0/

When redistributing these icons, retain attribution to Font Awesome.
```

- [ ] **Step 5: Update pyproject.toml to include the SVGs in the wheel**

Edit `pyproject.toml`. Find the existing `[tool.setuptools.packages.find]` section and append a `[tool.setuptools.package-data]` section right after it:

Old (only `packages.find` likely exists):
```toml
[tool.setuptools.packages.find]
include = ["intramap*"]
```

New (add the package-data section below):
```toml
[tool.setuptools.packages.find]
include = ["intramap*"]

[tool.setuptools.package-data]
"intramap.renderers" = ["icons/*.svg", "icons/LICENSE"]
```

- [ ] **Step 6: Reinstall to pick up the package-data**

Run: `pip install -e ".[dev]"`
Expected: successful reinstall (the package now knows about the SVGs).

- [ ] **Step 7: Run bundling tests**

Run: `pytest tests/test_renderers.py -v -k "bundled or license"`
Expected: both tests pass — all 15 SVGs are discoverable via `importlib.resources`.

- [ ] **Step 8: Commit**

```bash
git add intramap/renderers/icons/ pyproject.toml tests/test_renderers.py
git commit -m "feat: bundle 15 FontAwesome SVG device icons (CC BY 4.0)"
```

---

### Task 5: Renderers/icons.py module — sprite map and copy_icons_to

The single source of truth for the PlantUML sprite name and Graphviz icon file per `device_type`. Used by both renderers.

**Files:**
- Create: `intramap/renderers/icons.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_sprites_cover_all_device_types():
    from intramap.models import DEVICE_TYPES
    from intramap.renderers.icons import PLANTUML_SPRITES

    assert set(PLANTUML_SPRITES.keys()) == set(DEVICE_TYPES)


def test_plantuml_sprites_use_known_fa6_names():
    from intramap.renderers.icons import PLANTUML_SPRITES

    expected = {
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
    assert PLANTUML_SPRITES == expected


def test_copy_icons_to_creates_subdir_and_copies_requested_types(tmp_path):
    from intramap.renderers.icons import copy_icons_to

    used = {"router", "nas"}
    copy_icons_to(tmp_path, used)

    icons_dir = tmp_path / "icons"
    assert icons_dir.is_dir()
    assert (icons_dir / "router.svg").is_file()
    assert (icons_dir / "nas.svg").is_file()
    # Did not copy unused icons
    assert not (icons_dir / "tv.svg").exists()


def test_copy_icons_to_idempotent(tmp_path):
    from intramap.renderers.icons import copy_icons_to

    copy_icons_to(tmp_path, {"router"})
    # Second call must not raise (idempotent)
    copy_icons_to(tmp_path, {"router"})
    assert (tmp_path / "icons" / "router.svg").is_file()


def test_copy_icons_to_unknown_type_raises(tmp_path):
    from intramap.renderers.icons import copy_icons_to

    with pytest.raises(ValueError, match="refrigerator"):
        copy_icons_to(tmp_path, {"refrigerator"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderers.py -v -k "sprite or copy_icons"`
Expected: ImportError on `intramap.renderers.icons`.

- [ ] **Step 3: Implement icons.py**

Create `intramap/renderers/icons.py`:
```python
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


def copy_icons_to(out_dir: str | Path, types: Iterable[str]) -> None:
    """Copy the SVG icons for the given device_types into <out_dir>/icons/.

    Raises ValueError if a requested type is not in DEVICE_TYPES.
    """
    out_dir = Path(out_dir)
    icons_out = out_dir / "icons"
    icons_out.mkdir(parents=True, exist_ok=True)

    src_root = files("intramap.renderers") / "icons"
    for t in types:
        if t not in DEVICE_TYPES:
            raise ValueError(f"Unknown device_type: {t!r}")
        src = src_root / f"{t}.svg"
        dst = icons_out / f"{t}.svg"
        with src.open("rb") as fsrc, open(dst, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -v -k "sprite or copy_icons"`
Expected: 5 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/icons.py tests/test_renderers.py
git commit -m "feat: renderers/icons.py with PlantUML sprite map and copy_icons_to"
```

---

### Task 6: PlantUML renderer emits sprites

The renderer now:
1. Computes the set of `device_type`s in use (via `_resolve_device_type`)
2. Emits a `!include <font-awesome-6/<sprite>>` for each, in lexicographic order, right after the `skinparam` block
3. Prefixes each node's label with `<$<sprite>>\n`

**Files:**
- Modify: `intramap/renderers/plantuml.py`
- Modify: `tests/test_renderers.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_plantuml_emits_include_per_used_sprite(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Sagemcom",
        ),
    })
    out = render(inv)

    assert "!include <font-awesome-6/hard_drive>" in out
    assert "!include <font-awesome-6/network_wired>" in out


def test_plantuml_includes_are_lexicographically_sorted(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",  # nas -> hard_drive
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Sagemcom",  # router -> network_wired
        ),
    })
    out = render(inv)

    pos_hard = out.index("hard_drive")
    pos_net = out.index("network_wired")
    assert pos_hard < pos_net


def test_plantuml_dedupes_includes(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="QNAP",
        ),
    })
    out = render(inv)

    assert out.count("!include <font-awesome-6/hard_drive>") == 1


def test_plantuml_node_label_starts_with_sprite(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
            custom_name="NAS",
        ),
    })
    out = render(inv)

    assert '"<$hard_drive>\\nNAS' in out


def test_plantuml_unknown_vendor_uses_question_sprite(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor=None,
        ),
    })
    out = render(inv)

    assert "!include <font-awesome-6/question>" in out
    assert "<$question>" in out


def test_plantuml_explicit_device_type_overrides_inference(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01",
            vendor="TP-Link Systems",  # would infer 'ap' -> 'wifi'
            device_type="controller",  # override -> 'sliders'
        ),
    })
    out = render(inv)

    assert "<$sliders>" in out
    assert "<$wifi>" not in out


def test_plantuml_invalid_device_type_falls_back_to_question(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.plantuml import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01",
            vendor="Synology",
            device_type="refrigerator",  # not in catalogue
        ),
    })
    out = render(inv)

    assert "<$question>" in out
    assert "<$hard_drive>" not in out
```

Also add `make_host_factory` fixture to `tests/test_renderers.py` if not already present (same as the one in test_models.py):
```python
@pytest.fixture
def make_host_factory():
    """Return a function that builds a Host with sensible defaults."""
    from intramap.models import Host

    def _make(**kwargs):
        from datetime import datetime
        now = datetime(2026, 5, 25, 0, 0, 0)
        defaults = dict(
            mac="aa:bb:cc:dd:ee:01",
            ip="192.168.1.1",
            hostname=None,
            vendor=None,
            first_seen=now,
            last_seen=now,
        )
        defaults.update(kwargs)
        return Host(**defaults)
    return _make
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderers.py -v -k "plantuml" -x`
Expected: the new tests fail (no sprite emission yet).

- [ ] **Step 3: Update the PlantUML renderer**

Open `intramap/renderers/plantuml.py`. Find the `render` function. Update it to compute and emit the sprite includes and prefix node labels with sprites.

Look for the header block (where `lines = ["@startuml", ...]` is built) and the node-emission code. Replace the function body so it:

1. Computes `used_types = {_resolve_device_type(h) for h in inv.hosts.values()}`
2. Computes `used_sprites = sorted({PLANTUML_SPRITES[t] for t in used_types})`
3. Inserts the `!include` lines right after the `skinparam node<<offline>> { ... }` block (i.e. inside the existing header `lines` list)
4. For each node, prepends `<$<sprite>>\n` to the label

Concretely, at the top of `plantuml.py`, add:
```python
from intramap.models import _resolve_device_type
from intramap.renderers.icons import PLANTUML_SPRITES
```

Find the `render(inv)` function. Locate the part where the header `lines` list is constructed (it currently looks like):
```python
    lines: list[str] = [
        "@startuml",
        "skinparam node<<offline>> {",
        "  BackgroundColor #DDDDDD",
        "  BorderColor #888888",
        "}",
        "",
    ]
```

Replace it with the version below, which computes `used_sprites` from the inventory and inserts the `!include` lines:
```python
    used_types = {_resolve_device_type(h) for h in inv.hosts.values()}
    used_sprites = sorted({PLANTUML_SPRITES[t] for t in used_types})
    include_lines = [f"!include <font-awesome-6/{s}>" for s in used_sprites]

    lines: list[str] = [
        "@startuml",
        "skinparam node<<offline>> {",
        "  BackgroundColor #DDDDDD",
        "  BorderColor #888888",
        "}",
        *include_lines,
        "",
    ]
```

Find the part of the function that emits each node. Locate the f-string used for the label. It currently looks similar to:
```python
        label = f"{host.custom_name or host.mac}\\n{host.ip or ''}\\n{host.mac}"
```

Update to prepend the sprite. After the existing `label = ...` line, insert:
```python
        sprite = PLANTUML_SPRITES[_resolve_device_type(host)]
        label = f"<${sprite}>\\n{label}"
```

(Adjust to fit the existing code style. If the renderer composes labels differently, the principle is the same: prepend `<$<sprite>>\\n` to the multi-line label.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -v -k plantuml`
Expected: all PlantUML tests pass, including the new sprite tests.

Run the full suite:

Run: `pytest -v`
Expected: all tests still pass.

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/plantuml.py tests/test_renderers.py
git commit -m "feat: PlantUML renderer prefixes nodes with FontAwesome sprites"
```

---

### Task 7: Graphviz renderer emits image attributes and copies icons

The renderer now:
1. Computes the set of `device_type`s in use
2. Provides them to `copy_icons_to(out_dir, used_types)` — but only when `out_dir` is known
3. Emits `image="icons/<type>.svg"`, `labelloc="b"`, `imagescale=true` for each node

Since `render(inv)` returns a string and doesn't know an output directory, the renderer needs a small API change: a second optional argument or a separate copy step from the CLI. We pick the simpler path: `render(inv, copy_assets_to=None)` — when `copy_assets_to` is passed, the renderer triggers the icon copy.

**Files:**
- Modify: `intramap/renderers/graphviz.py`
- Modify: `tests/test_renderers.py`
- Note: `cli.py` will pass `copy_assets_to=out_dir` in Task 9.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_renderers.py`:
```python
def test_graphviz_emits_image_attribute(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
            custom_name="NAS",
        ),
    })
    out = render(inv)

    assert 'image="icons/nas.svg"' in out
    assert 'labelloc="b"' in out
    assert "imagescale=true" in out


def test_graphviz_explicit_device_type_overrides_inference(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01",
            vendor="TP-Link Systems",  # would infer 'ap'
            device_type="controller",
        ),
    })
    out = render(inv)

    assert 'image="icons/controller.svg"' in out
    assert 'image="icons/ap.svg"' not in out


def test_graphviz_unknown_vendor_uses_other_icon(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor=None,
        ),
    })
    out = render(inv)

    assert 'image="icons/other.svg"' in out


def test_graphviz_offline_host_keeps_image_and_uses_dashed_style(make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
            online=False,
        ),
    })
    out = render(inv)

    assert 'image="icons/nas.svg"' in out
    assert "style=dashed" in out


def test_graphviz_copy_assets_to_writes_icons(tmp_path, make_host_factory):
    from intramap.models import Inventory
    from intramap.renderers.graphviz import render

    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host_factory(
            mac="aa:bb:cc:dd:ee:01", vendor="Synology",
        ),
        "aa:bb:cc:dd:ee:02": make_host_factory(
            mac="aa:bb:cc:dd:ee:02", vendor="Sagemcom",
        ),
    })
    out = render(inv, copy_assets_to=tmp_path)

    assert (tmp_path / "icons" / "nas.svg").is_file()
    assert (tmp_path / "icons" / "router.svg").is_file()
    # No copy when copy_assets_to is None: covered by other tests that
    # didn't pass the arg.
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_renderers.py -v -k graphviz -x`
Expected: most new tests fail — `image=` attribute is not emitted.

- [ ] **Step 3: Update the Graphviz renderer**

Open `intramap/renderers/graphviz.py`.

At the top, add imports:
```python
from pathlib import Path

from intramap.models import _resolve_device_type
from intramap.renderers.icons import copy_icons_to
```

Update the `render` function signature and behaviour. Locate it (currently looks like `def render(inv: Inventory) -> str:` or similar) and replace:

Old (signature only — keep the body, just change the head):
```python
def render(inv: Inventory) -> str:
```

New:
```python
def render(inv: Inventory, copy_assets_to: str | Path | None = None) -> str:
    """Render `inv` as Graphviz DOT text.

    If `copy_assets_to` is given, also copy the SVG icons of all used
    device_types into `<copy_assets_to>/icons/`.
    """
```

Inside `render`, after the inventory is processed and BEFORE the function returns the text, locate the node-emission block. For each node, the current code emits something like:
```python
        attrs = [f'label="{label_text}"']
        if not host.online:
            attrs.append("style=dashed")
            attrs.append('color="#888888"')
        lines.append(f'    {node_id} [{", ".join(attrs)}];')
```

Update the `attrs` list to include the image, labelloc and imagescale:
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
        lines.append(f'    {node_id} [{", ".join(attrs)}];')
```

After the function body has finished building the output text (and BEFORE the `return` statement), add the icon copy logic:
```python
    if copy_assets_to is not None:
        used_types = {_resolve_device_type(h) for h in inv.hosts.values()}
        copy_icons_to(copy_assets_to, used_types)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_renderers.py -v -k graphviz`
Expected: all Graphviz tests pass, new ones included.

- [ ] **Step 5: Commit**

```bash
git add intramap/renderers/graphviz.py tests/test_renderers.py
git commit -m "feat: Graphviz renderer emits image attributes and copies icons"
```

---

### Task 8: CLI list — Type column

Adds the `Type` column to the `intramap list` output, populated from `_resolve_device_type`. Insert between `Name` and `Vendor`.

**Files:**
- Modify: `intramap/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:
```python
def test_list_prints_type_column(tmp_path, capsys):
    from datetime import datetime
    from intramap.cli import main
    from intramap.inventory import save
    from intramap.models import Host, Inventory

    now = datetime(2026, 5, 25, 0, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="Synology Incorporated",
            first_seen=now, last_seen=now,
        ),
    })
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)

    rc = main(["--inventory", str(inv_path), "list"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "Type" in out
    assert "nas" in out


def test_list_type_for_unknown_vendor_is_other(tmp_path, capsys):
    from datetime import datetime
    from intramap.cli import main
    from intramap.inventory import save
    from intramap.models import Host, Inventory

    now = datetime(2026, 5, 25, 0, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="Totally Unknown",
            first_seen=now, last_seen=now,
        ),
    })
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)

    rc = main(["--inventory", str(inv_path), "list"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "other" in out


def test_list_explicit_device_type_shown_over_inferred(tmp_path, capsys):
    from datetime import datetime
    from intramap.cli import main
    from intramap.inventory import save
    from intramap.models import Host, Inventory

    now = datetime(2026, 5, 25, 0, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="TP-Link Systems",
            device_type="controller",
            first_seen=now, last_seen=now,
        ),
    })
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)

    rc = main(["--inventory", str(inv_path), "list"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "controller" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k "type_column or type_for_unknown or explicit_device"`
Expected: failures — the `Type` column doesn't exist yet.

- [ ] **Step 3: Update the CLI to include the Type column**

Open `intramap/cli.py`. At the top, add the import:
```python
from intramap.models import _resolve_device_type
```

Find the `_cmd_list` function. It currently builds rows like:
```python
        rows.append((
            mac, ip, name, vendor, hostname, location, status,
        ))
```
(or a similar tuple). It also has a `headers` tuple like:
```python
    headers = ["MAC", "IP", "Name", "Vendor", "Hostname", "Location", "Status"]
```

Update to insert the `Type` column between `Name` and `Vendor`:

```python
    headers = ["MAC", "IP", "Name", "Type", "Vendor", "Hostname", "Location", "Status"]
```

And, when building each row, compute `device_type` and insert it in the right position:

Old (find the row-building line and adapt the order):
```python
        rows.append((
            host.mac,
            host.ip or "-",
            host.custom_name or "-",
            host.vendor or "-",
            host.hostname or "-",
            _format_location(host.location),
            "online" if host.online else "OFFLINE",
        ))
```

New (with `Type` inserted between `Name` and `Vendor`):
```python
        rows.append((
            host.mac,
            host.ip or "-",
            host.custom_name or "-",
            _resolve_device_type(host),
            host.vendor or "-",
            host.hostname or "-",
            _format_location(host.location),
            "online" if host.online else "OFFLINE",
        ))
```

(Adjust to whatever the actual existing function looks like. If column widths are computed dynamically, no further change is needed — the inserted column will auto-size.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: all CLI tests pass, including the three new ones.

- [ ] **Step 5: Commit**

```bash
git add intramap/cli.py tests/test_cli.py
git commit -m "feat: intramap list shows Type column"
```

---

### Task 9: CLI list — --type filter + render copies icons

Adds a `--type <value>` filter (exact match against resolved device_type) and updates the `render` CLI handler to pass `copy_assets_to=out_dir` to the Graphviz renderer so icons end up next to `network.dot`.

**Files:**
- Modify: `intramap/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:
```python
def test_list_filter_by_type_exact_match(tmp_path, capsys):
    from datetime import datetime
    from intramap.cli import main
    from intramap.inventory import save
    from intramap.models import Host, Inventory

    now = datetime(2026, 5, 25, 0, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="Synology",
            first_seen=now, last_seen=now,
        ),
        "aa:bb:cc:dd:ee:02": Host(
            mac="aa:bb:cc:dd:ee:02", ip="192.168.1.2",
            hostname=None, vendor="Sagemcom",
            first_seen=now, last_seen=now,
        ),
    })
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)

    rc = main(["--inventory", str(inv_path), "list", "--type", "nas"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "aa:bb:cc:dd:ee:01" in out
    assert "aa:bb:cc:dd:ee:02" not in out


def test_list_filter_by_type_case_insensitive(tmp_path, capsys):
    from datetime import datetime
    from intramap.cli import main
    from intramap.inventory import save
    from intramap.models import Host, Inventory

    now = datetime(2026, 5, 25, 0, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="Synology",
            first_seen=now, last_seen=now,
        ),
    })
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)

    rc = main(["--inventory", str(inv_path), "list", "--type", "NAS"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "aa:bb:cc:dd:ee:01" in out


def test_render_graphviz_writes_icons_subdir(tmp_path):
    from datetime import datetime
    from intramap.cli import main
    from intramap.inventory import save
    from intramap.models import Host, Inventory

    now = datetime(2026, 5, 25, 0, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="Synology",
            first_seen=now, last_seen=now,
        ),
    })
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)
    out_dir = tmp_path / "out"

    rc = main([
        "--inventory", str(inv_path),
        "render", "--format", "graphviz", "--output-dir", str(out_dir),
    ])

    assert rc == 0
    assert (out_dir / "network.dot").is_file()
    assert (out_dir / "icons" / "nas.svg").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v -k "filter_by_type or icons_subdir"`
Expected: failures — `--type` arg isn't recognised, and icons aren't copied.

- [ ] **Step 3: Add `--type` argument and route it through filtering**

In `intramap/cli.py`, find where the `list` subparser is built (somewhere in `_build_parser` or equivalent). It currently has lines like:
```python
    list_p.add_argument("--vendor", default=None,
                        help="substring filter on vendor (case-insensitive)")
```

Add right after:
```python
    list_p.add_argument("--type", default=None, dest="type_filter",
                        help="filter by exact device_type (case-insensitive); "
                             "compares against resolved device_type")
```

(Use `dest="type_filter"` to avoid shadowing the Python builtin `type` when accessing `args.type`.)

In `_cmd_list`, find the loop that iterates hosts and applies the existing filters (`--vendor`, `--offline`, `--unnamed`). Add the new filter:
```python
        if args.type_filter is not None:
            if _resolve_device_type(host).lower() != args.type_filter.lower():
                continue
```

- [ ] **Step 4: Update `render` to pass `copy_assets_to`**

In the same file, find `_cmd_render`. It calls `graphviz.render(inv)` (or via the dispatch table). Update so the Graphviz renderer call passes `copy_assets_to=out_dir`:

Old:
```python
        if "graphviz" in formats:
            (out_dir / "network.dot").write_text(graphviz.render(inv),
                                                 encoding="utf-8")
```

New:
```python
        if "graphviz" in formats:
            (out_dir / "network.dot").write_text(
                graphviz.render(inv, copy_assets_to=out_dir),
                encoding="utf-8",
            )
```

(Adjust to the existing dispatch shape — the only change is adding `copy_assets_to=out_dir`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: all CLI tests pass.

Run the full suite:

Run: `pytest -v`
Expected: 71 + N new tests pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add intramap/cli.py tests/test_cli.py
git commit -m "feat: intramap list --type filter; render copies icons next to .dot"
```

---

### Task 10: README attribution + end-to-end verification

Adds the Font Awesome attribution to the README and runs the full pipeline against a small real-shaped inventory to confirm everything wires up.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Font Awesome attribution to the README**

Open `README.md`. Find the **Acknowledgements / Credits** section if one exists. If not, add one at the end of the file.

Append (or insert into the existing credits section):

```markdown
## Acknowledgements

Icons by [Font Awesome](https://fontawesome.com/), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
The bundled SVGs are unmodified copies of selected Font Awesome Free 6
solid icons (see `intramap/renderers/icons/LICENSE`).
```

- [ ] **Step 2: End-to-end verification — fresh render on a real-shaped inventory**

In a scratch directory:

```bash
mkdir -p /tmp/intramap_e2e
cd /tmp/intramap_e2e
```

Create a small `inventory.yaml`:
```yaml
last_scan: 2026-05-25T00:00:00
hosts:
  38:e1:f4:85:aa:42:
    ip: 192.168.1.1
    hostname: null
    vendor: Sagemcom Broadband SAS
    custom_name: BBox
    location: {floor: cave, room: local, rack: baie, rack_unit: null}
    uplink: null
    device_type: null
    manual: false
    first_seen: 2026-05-25T00:00:00
    last_seen: 2026-05-25T00:00:00
    online: true
  aa:aa:aa:11:11:11:
    ip: null
    hostname: null
    vendor: null
    custom_name: Switch principal
    location: {floor: cave, room: local, rack: baie, rack_unit: 5}
    uplink:
      switch_mac: 38:e1:f4:85:aa:42
      switch_port: null
      patch_port: null
      poe: false
    device_type: switch
    manual: true
    first_seen: 2026-05-25T00:00:00
    last_seen: 2026-05-25T00:00:00
    online: true
  00:11:32:41:bb:85:
    ip: 192.168.1.10
    hostname: null
    vendor: Synology
    custom_name: NAS
    location: {floor: cave, room: local, rack: baie, rack_unit: 1}
    uplink:
      switch_mac: aa:aa:aa:11:11:11
      switch_port: 3
      patch_port: null
      poe: false
    device_type: null
    manual: false
    first_seen: 2026-05-25T00:00:00
    last_seen: 2026-05-25T00:00:00
    online: true
```

Run:
```bash
intramap --inventory inventory.yaml list
intramap --inventory inventory.yaml list --type nas
intramap --inventory inventory.yaml render --format plantuml --output-dir out
intramap --inventory inventory.yaml render --format graphviz --output-dir out
```

Expected:
- `list` shows three rows with `Type` column populated: `router` (inferred from Sagemcom), `switch` (explicit), `nas` (inferred from Synology).
- `list --type nas` shows only the Synology entry.
- `out/network.puml` contains `!include <font-awesome-6/hard_drive>`, `!include <font-awesome-6/network_wired>`, `!include <font-awesome-6/share_nodes>` and node labels prefixed with the corresponding `<$sprite>`.
- `out/network.dot` references `image="icons/nas.svg"`, `image="icons/router.svg"`, `image="icons/switch.svg"`.
- `out/icons/` contains exactly those three SVG files.

- [ ] **Step 3: Run the full test suite one final time**

Run: `pytest -v`
Expected: all tests pass (~71 + ~24 new = ~95 total, give or take).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: README acknowledges Font Awesome icons (CC BY 4.0)"
```

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Implemented by |
|---|---|
| §3.1 New Host fields (`device_type`, `manual`) | Task 2 |
| §3.2 Semantics (defaults, override priority, manual exemption) | Tasks 1, 2, 3 |
| §3.3 Catalogue (15 values) | Task 1 (`DEVICE_TYPES`) + Task 5 (`PLANTUML_SPRITES`) + Task 4 (icons) |
| §3.4 Auto-detection table | Task 1 (`_VENDOR_PATTERNS` + `infer_device_type`) |
| §3.5 Resolution priority | Task 1 (`_resolve_device_type`) |
| §4.1, §4.2 Merge skips manual | Task 3 |
| §5 YAML round-trip + backward compat | Task 2 |
| §6.1 PlantUML sprites and emission | Task 6 |
| §6.2 Graphviz `image=` + icon copy | Tasks 5 + 7 + 9 |
| §6.3 Output tree (network.dot + icons/) | Tasks 7 + 9 |
| §7.1 CLI list Type column | Task 8 |
| §7.2 CLI list --type filter | Task 9 |
| §8 Errors at boundaries | Tasks 2 (validation), 5 (unknown type in copy_icons) |
| §9 Tests | Embedded in every task |
| §10 FA attribution | Task 10 |

**Placeholder scan:** none.

**Type consistency check:**
- `Host.device_type: str | None = None` and `Host.manual: bool = False` (Tasks 2, 3, 6, 7, 8, 9).
- `DEVICE_TYPES: frozenset[str]` (Task 1, used in Task 5).
- `PLANTUML_SPRITES: dict[str, str]` (Task 5, used in Task 6).
- `copy_icons_to(out_dir, types)` — `out_dir: str | Path`, `types: Iterable[str]` (Task 5, called from Task 7 renderer and Task 9 CLI flow).
- `render(inv, copy_assets_to=None)` Graphviz signature (Task 7, called from Task 9).
- `_resolve_device_type(host) -> str` returns a value in `DEVICE_TYPES` (Task 1, used in 6, 7, 8, 9).
- `infer_device_type(vendor) -> str | None` returns either a value in `DEVICE_TYPES \ {"other"}` or None (Task 1).

All names match across tasks.
