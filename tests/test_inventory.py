from datetime import datetime
from pathlib import Path

from intramap.inventory import load, save
from intramap.models import Host, Inventory, Location


def make_host(mac: str, ip: str, **kwargs) -> Host:
    now = datetime(2026, 5, 24, 14, 0, 0)
    defaults = dict(hostname=None, vendor=None, first_seen=now, last_seen=now)
    defaults.update(kwargs)
    return Host(mac=mac, ip=ip, **defaults)


def test_load_missing_file_returns_empty_inventory(tmp_path: Path):
    inv = load(tmp_path / "does_not_exist.yaml")
    assert inv.hosts == {}
    assert inv.last_scan is None


def test_save_then_load_round_trip(tmp_path: Path):
    now = datetime(2026, 5, 24, 14, 30, 0)
    inv = Inventory(
        hosts={
            "aa:bb:cc:dd:ee:01": make_host(
                "aa:bb:cc:dd:ee:01", "192.168.1.1",
                custom_name="Box", location=Location(floor="RDC", room="salon"),
            ),
        },
        last_scan=now,
    )
    path = tmp_path / "inv.yaml"
    save(inv, path)
    loaded = load(path)
    assert loaded == inv


def test_save_sorts_hosts_by_mac(tmp_path: Path):
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:03": make_host("aa:bb:cc:dd:ee:03", "192.168.1.3"),
        "aa:bb:cc:dd:ee:01": make_host("aa:bb:cc:dd:ee:01", "192.168.1.1"),
        "aa:bb:cc:dd:ee:02": make_host("aa:bb:cc:dd:ee:02", "192.168.1.2"),
    }, last_scan=datetime(2026, 5, 24))
    path = tmp_path / "inv.yaml"
    save(inv, path)
    text = path.read_text(encoding="utf-8")
    pos1 = text.index("aa:bb:cc:dd:ee:01")
    pos2 = text.index("aa:bb:cc:dd:ee:02")
    pos3 = text.index("aa:bb:cc:dd:ee:03")
    assert pos1 < pos2 < pos3


def test_load_normalizes_mac_keys(tmp_path: Path):
    path = tmp_path / "inv.yaml"
    path.write_text(
        "last_scan: 2026-05-24T14:30:00\n"
        "hosts:\n"
        "  AA-BB-CC-DD-EE-01:\n"
        "    ip: 192.168.1.1\n"
        "    hostname: null\n"
        "    vendor: null\n"
        "    custom_name: null\n"
        "    location: {floor: null, room: null, rack: null, rack_unit: null}\n"
        "    first_seen: '2026-05-01T10:00:00'\n"
        "    last_seen: '2026-05-24T14:30:00'\n"
        "    online: true\n",
        encoding="utf-8",
    )
    inv = load(path)
    assert "aa:bb:cc:dd:ee:01" in inv.hosts
