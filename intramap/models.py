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
from datetime import datetime


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
        uplink = Uplink(**uplink_data) if uplink_data is not None else None
        return cls(
            mac=mac,
            ip=data.get("ip"),
            hostname=data.get("hostname"),
            vendor=data.get("vendor"),
            custom_name=data.get("custom_name"),
            location=Location(**loc_data),
            uplink=uplink,
            first_seen=datetime.fromisoformat(data["first_seen"]),
            last_seen=datetime.fromisoformat(data["last_seen"]),
            online=data.get("online", True),
        )


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
        last_scan = datetime.fromisoformat(last_scan_raw) if last_scan_raw else None
        hosts_data = data.get("hosts") or {}
        hosts = {
            normalize_mac(mac): Host.from_dict(normalize_mac(mac), h)
            for mac, h in hosts_data.items()
        }
        return cls(hosts=hosts, last_scan=last_scan)
