import re


_HEX12 = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(raw: str) -> str:
    """Return MAC in canonical form: lowercase, ':' separator.

    Accepts common variants (colons, dashes, no separator, mixed case).
    Raises ValueError on anything that is not a 48-bit MAC.
    """
    if not isinstance(raw, str):
        raise ValueError(f"MAC must be a string, got {type(raw).__name__}")
    compact = raw.strip().lower().replace(":", "").replace("-", "")
    if not _HEX12.match(compact):
        raise ValueError(f"Not a valid MAC address: {raw!r}")
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))


from dataclasses import asdict, dataclass, field
from datetime import date, datetime


def _parse_dt(value: str | datetime | date) -> datetime:
    """Accept either an ISO string or an already-parsed datetime/date (PyYAML).

    PyYAML auto-parses bare date strings (e.g. ``2026-05-24``) as
    ``datetime.date`` objects rather than ``datetime.datetime``.  We convert
    those to midnight datetimes.  The ``datetime`` branch must come first
    because ``datetime`` is a subclass of ``date``.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(value)


@dataclass
class Location:
    floor: str | None = None
    room: str | None = None
    rack: str | None = None
    rack_unit: int | None = None


@dataclass
class Uplink:
    """User-declared wired uplink from a host through a patch panel to a switch.

    All fields are optional. `switch_mac` references another host in the
    inventory (by MAC). `patch_port` is the port number on the patch panel of
    the host's rack. `poe` indicates whether the host is powered via PoE
    through this link.
    """
    switch_mac: str | None = None
    switch_port: int | None = None
    patch_port: int | None = None
    poe: bool = False

    def __post_init__(self) -> None:
        if self.switch_mac is not None:
            self.switch_mac = normalize_mac(self.switch_mac)


@dataclass
class DiscoveredHost:
    """A host as seen by the scanner — raw, before inventory integration."""
    mac: str
    ip: str
    hostname: str | None
    vendor: str | None

    def __post_init__(self) -> None:
        self.mac = normalize_mac(self.mac)


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

    def __post_init__(self) -> None:
        self.mac = normalize_mac(self.mac)

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


@dataclass
class Inventory:
    hosts: dict[str, Host] = field(default_factory=dict)
    last_scan: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "hosts": {mac: h.to_dict() for mac, h in sorted(self.hosts.items())},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Inventory":
        last_scan_raw = data.get("last_scan")
        last_scan = _parse_dt(last_scan_raw) if last_scan_raw else None
        hosts_data = data.get("hosts") or {}
        hosts = {
            normalize_mac(mac): Host.from_dict(normalize_mac(mac), h)
            for mac, h in hosts_data.items()
        }
        return cls(hosts=hosts, last_scan=last_scan)
