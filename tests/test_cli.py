from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from intramap.cli import main
from intramap.inventory import save
from intramap.models import DiscoveredHost, Host, Inventory, Location


def _seed_inventory(path: Path) -> None:
    now = datetime(2026, 5, 24, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname="livebox", vendor="Sagemcom",
            custom_name="Box internet",
            location=Location(floor="RDC", room="salon"),
            first_seen=now, last_seen=now, online=True,
        ),
        "aa:bb:cc:dd:ee:02": Host(
            mac="aa:bb:cc:dd:ee:02", ip="192.168.1.10",
            hostname=None, vendor="Cisco",
            custom_name=None,
            location=Location(),
            first_seen=now, last_seen=now, online=False,
        ),
    }, last_scan=now)
    save(inv, path)


def test_list_prints_all_hosts(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_inventory(inv_path)

    exit_code = main(["--inventory", str(inv_path), "list"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "aa:bb:cc:dd:ee:01" in out
    assert "aa:bb:cc:dd:ee:02" in out
    assert "Box internet" in out
    assert "Sagemcom" in out
    assert "Cisco" in out


def test_list_offline_filters(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_inventory(inv_path)

    exit_code = main(["--inventory", str(inv_path), "list", "--offline"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "aa:bb:cc:dd:ee:02" in out
    assert "aa:bb:cc:dd:ee:01" not in out


def test_list_unnamed_filters(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_inventory(inv_path)

    exit_code = main(["--inventory", str(inv_path), "list", "--unnamed"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "aa:bb:cc:dd:ee:02" in out
    assert "aa:bb:cc:dd:ee:01" not in out


def test_list_vendor_filter_case_insensitive_substring(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_inventory(inv_path)

    # "sagem" matches "Sagemcom" (case-insensitive substring)
    exit_code = main(["--inventory", str(inv_path), "list", "--vendor", "sagem"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "aa:bb:cc:dd:ee:01" in out  # Sagemcom
    assert "aa:bb:cc:dd:ee:02" not in out  # Cisco


def test_list_vendor_filter_no_match_prints_only_headers(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    _seed_inventory(inv_path)

    exit_code = main(["--inventory", str(inv_path), "list", "--vendor", "nothing-matches"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "aa:bb:cc:dd:ee:01" not in out
    assert "aa:bb:cc:dd:ee:02" not in out


def test_list_vendor_filter_excludes_hosts_with_no_vendor(tmp_path: Path, capsys):
    """Hosts with vendor=None (e.g. randomized MACs) are filtered out by --vendor."""
    now = datetime(2026, 5, 24, 14, 0, 0)
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": Host(
            mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
            hostname=None, vendor="Sagemcom",
            custom_name=None, location=Location(),
            first_seen=now, last_seen=now, online=True,
        ),
        "52:5f:d3:c2:b4:6e": Host(
            mac="52:5f:d3:c2:b4:6e", ip="192.168.1.81",
            hostname=None, vendor=None,  # randomized MAC, no OUI match
            custom_name=None, location=Location(),
            first_seen=now, last_seen=now, online=True,
        ),
    }, last_scan=now)
    inv_path = tmp_path / "inv.yaml"
    save(inv, inv_path)

    exit_code = main(["--inventory", str(inv_path), "list", "--vendor", "sagem"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "aa:bb:cc:dd:ee:01" in out
    assert "52:5f:d3:c2:b4:6e" not in out


def test_list_missing_inventory_returns_clear_error(tmp_path: Path, capsys):
    exit_code = main(["--inventory", str(tmp_path / "absent.yaml"), "list"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "inventory" in (captured.out + captured.err).lower()


def test_list_invalid_uplink_shape_gives_clear_error(tmp_path: Path, capsys):
    """A user hand-editing inventory.yaml with `uplink: true` (instead of a
    mapping) should see a clear error pointing at the offending host and
    showing the expected format, not a Python traceback."""
    inv_path = tmp_path / "inv.yaml"
    inv_path.write_text(
        "last_scan: 2026-05-24T14:00:00\n"
        "hosts:\n"
        "  aa:bb:cc:dd:ee:01:\n"
        "    ip: 192.168.1.1\n"
        "    hostname: null\n"
        "    vendor: null\n"
        "    custom_name: null\n"
        "    location: {floor: null, room: null, rack: null, rack_unit: null}\n"
        "    uplink: true\n"
        "    first_seen: 2026-05-01T10:00:00\n"
        "    last_seen: 2026-05-24T14:00:00\n"
        "    online: true\n",
        encoding="utf-8",
    )

    exit_code = main(["--inventory", str(inv_path), "list"])
    captured = capsys.readouterr()
    assert exit_code != 0
    err = captured.err
    assert "uplink" in err.lower()
    assert "aa:bb:cc:dd:ee:01" in err
    assert "switch_mac" in err  # the example format is shown


def test_render_writes_both_files_by_default(tmp_path: Path):
    inv_path = tmp_path / "inv.yaml"
    out_dir = tmp_path / "output"
    _seed_inventory(inv_path)

    exit_code = main([
        "--inventory", str(inv_path),
        "render", "--output-dir", str(out_dir),
    ])
    assert exit_code == 0
    assert (out_dir / "network.puml").exists()
    assert (out_dir / "network.dot").exists()
    assert "@startuml" in (out_dir / "network.puml").read_text(encoding="utf-8")
    assert "graph network" in (out_dir / "network.dot").read_text(encoding="utf-8")


def test_render_format_plantuml_only(tmp_path: Path):
    inv_path = tmp_path / "inv.yaml"
    out_dir = tmp_path / "output"
    _seed_inventory(inv_path)

    exit_code = main([
        "--inventory", str(inv_path),
        "render", "--format", "plantuml",
        "--output-dir", str(out_dir),
    ])
    assert exit_code == 0
    assert (out_dir / "network.puml").exists()
    assert not (out_dir / "network.dot").exists()


def test_render_missing_inventory_returns_error(tmp_path: Path, capsys):
    out_dir = tmp_path / "output"
    exit_code = main([
        "--inventory", str(tmp_path / "absent.yaml"),
        "render", "--output-dir", str(out_dir),
    ])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "inventory" in (captured.out + captured.err).lower()


def test_scan_with_explicit_network_creates_inventory(tmp_path: Path):
    inv_path = tmp_path / "inv.yaml"

    fake_discovered = [
        DiscoveredHost(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
                       hostname="box", vendor="Sagemcom"),
    ]
    with patch("intramap.cli.scanner.scan", return_value=fake_discovered):
        exit_code = main([
            "--inventory", str(inv_path),
            "scan", "--network", "192.168.1.0/24",
        ])

    assert exit_code == 0
    assert inv_path.exists()
    text = inv_path.read_text(encoding="utf-8")
    assert "aa:bb:cc:dd:ee:01" in text


def test_scan_merges_into_existing_inventory(tmp_path: Path):
    inv_path = tmp_path / "inv.yaml"
    _seed_inventory(inv_path)

    fake_discovered = [
        DiscoveredHost(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1",
                       hostname="box", vendor="Sagemcom"),
        DiscoveredHost(mac="aa:bb:cc:dd:ee:03", ip="192.168.1.3",
                       hostname="new-device", vendor="Apple"),
    ]
    with patch("intramap.cli.scanner.scan", return_value=fake_discovered):
        exit_code = main([
            "--inventory", str(inv_path),
            "scan", "--network", "192.168.1.0/24",
        ])
    assert exit_code == 0

    # Reload and check
    from intramap import inventory as inventory_mod
    inv = inventory_mod.load(inv_path)
    # Existing annotated host preserved
    assert inv.hosts["aa:bb:cc:dd:ee:01"].custom_name == "Box internet"
    # New host added
    assert "aa:bb:cc:dd:ee:03" in inv.hosts
    # Pre-existing host that wasn't rediscovered is now offline
    assert inv.hosts["aa:bb:cc:dd:ee:02"].online is False


def test_scan_auto_detects_single_subnet(tmp_path: Path):
    inv_path = tmp_path / "inv.yaml"
    with patch("intramap.cli._detect_subnets", return_value=["192.168.1.0/24"]):
        with patch("intramap.cli.scanner.scan", return_value=[]) as mock_scan:
            exit_code = main(["--inventory", str(inv_path), "scan"])
    assert exit_code == 0
    mock_scan.assert_called_once_with("192.168.1.0/24")


def test_scan_multiple_subnets_requires_explicit_network(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    with patch("intramap.cli._detect_subnets",
               return_value=["192.168.1.0/24", "10.0.0.0/24"]):
        exit_code = main(["--inventory", str(inv_path), "scan"])
    captured = capsys.readouterr()
    assert exit_code != 0
    err = captured.out + captured.err
    assert "192.168.1.0/24" in err
    assert "10.0.0.0/24" in err
    assert "--network" in err


def test_scan_no_subnet_detected_returns_error(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    with patch("intramap.cli._detect_subnets", return_value=[]):
        exit_code = main(["--inventory", str(inv_path), "scan"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "--network" in (captured.out + captured.err)


def test_scan_propagates_nmap_missing_as_clear_error(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    with patch("intramap.cli.scanner.scan",
               side_effect=RuntimeError("nmap binary not found in PATH...")):
        exit_code = main([
            "--inventory", str(inv_path),
            "scan", "--network", "192.168.1.0/24",
        ])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "nmap" in (captured.out + captured.err).lower()


def test_scan_warns_on_zero_hosts(tmp_path: Path, capsys):
    inv_path = tmp_path / "inv.yaml"
    with patch("intramap.cli.scanner.scan", return_value=[]):
        exit_code = main([
            "--inventory", str(inv_path),
            "scan", "--network", "192.168.1.0/24",
        ])
    captured = capsys.readouterr()
    assert exit_code == 0  # not an error, just a warning
    err = captured.err
    assert "zero hosts" in err.lower() or "sudo" in err.lower() or "administrator" in err.lower()


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
