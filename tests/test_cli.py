from datetime import datetime
from pathlib import Path

import pytest

from intramap.cli import main
from intramap.inventory import save
from intramap.models import Host, Inventory, Location


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


def test_list_missing_inventory_returns_clear_error(tmp_path: Path, capsys):
    exit_code = main(["--inventory", str(tmp_path / "absent.yaml"), "list"])
    captured = capsys.readouterr()
    assert exit_code != 0
    assert "inventory" in (captured.out + captured.err).lower()


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
