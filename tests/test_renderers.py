from datetime import datetime

from intramap.models import Host, Inventory, Location, Uplink
from intramap.renderers.plantuml import render as render_plantuml


def make_host(mac: str, ip: str, *, custom_name=None, location=None,
              uplink=None, online=True) -> Host:
    now = datetime(2026, 5, 24, 14, 0, 0)
    return Host(
        mac=mac, ip=ip, hostname=None, vendor=None,
        custom_name=custom_name, location=location or Location(),
        uplink=uplink,
        first_seen=now, last_seen=now, online=online,
    )


def test_plantuml_groups_by_floor_room_rack():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            custom_name="Box", location=Location(floor="RDC", room="salon"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert out.startswith("@startuml")
    assert out.rstrip().endswith("@enduml")
    assert 'package "RDC"' in out
    assert 'package "salon"' in out
    assert 'package "sous-sol"' in out
    assert 'package "local-tech"' in out
    assert 'package "baie-A"' in out
    assert "Box" in out
    assert "Switch" in out


def test_plantuml_hosts_without_floor_go_to_non_localised():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:99": make_host(
            "aa:bb:cc:dd:ee:99", "192.168.1.99",
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert 'package "Non localisé"' in out
    assert "aa:bb:cc:dd:ee:99" in out


def test_plantuml_floor_set_without_room_gets_placeholder_room():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            location=Location(floor="RDC"),  # no room
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert 'package "RDC"' in out
    assert 'package "(sans pièce)"' in out


def test_plantuml_offline_host_has_offline_stereotype():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            location=Location(floor="RDC", room="salon"),
            online=False,
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert "<<offline>>" in out


def test_plantuml_escapes_double_quotes_in_names():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            custom_name='PC "test"',
            location=Location(floor="RDC", room="salon"),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert 'PC \\"test\\"' in out
    # Make sure the surrounding label quotes aren't broken
    assert '"PC \\"test\\"' in out


def test_plantuml_uses_mac_when_no_custom_name():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:99": make_host(
            "aa:bb:cc:dd:ee:99", "192.168.1.99",
            location=Location(floor="RDC", room="salon"),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert "aa:bb:cc:dd:ee:99" in out


def test_plantuml_draws_edge_for_valid_uplink():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(
                switch_mac="aa:bb:cc:dd:ee:01",
                switch_port=4,
                patch_port=7,
                poe=False,
            ),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    # An edge between the two nodes appears (PlantUML '--' between IDs)
    assert " -- " in out
    # Label contains both port indicators
    assert "sw:4" in out
    assert "pp:7" in out


def test_plantuml_poe_uplink_uses_distinct_style():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(
                switch_mac="aa:bb:cc:dd:ee:01",
                switch_port=4,
                poe=True,
            ),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert "[#orange,thickness=2]" in out
    assert "PoE" in out


def test_plantuml_uplink_with_only_patch_port():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(switch_mac="aa:bb:cc:dd:ee:01", patch_port=7),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    assert "pp:7" in out
    assert "sw:" not in out  # no switch_port label part


def test_plantuml_uplink_to_unknown_mac_is_silently_skipped():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(switch_mac="ff:ff:ff:ff:ff:ff", switch_port=4),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_plantuml(inv)
    # No edge drawn since the target MAC isn't in the inventory
    assert " -- " not in out
    assert "sw:4" not in out


# ---------------------------------------------------------------------------
# Graphviz (DOT) renderer tests
# ---------------------------------------------------------------------------

from intramap.renderers.graphviz import render as render_graphviz


def test_graphviz_outputs_a_graph():
    inv = Inventory(hosts={}, last_scan=datetime(2026, 5, 24))
    out = render_graphviz(inv)
    assert out.lstrip().startswith("graph ")
    assert out.rstrip().endswith("}")


def test_graphviz_groups_with_clusters():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            custom_name="Box", location=Location(floor="RDC", room="salon"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_graphviz(inv)
    assert "subgraph cluster_" in out
    assert 'label="RDC"' in out
    assert 'label="salon"' in out
    assert 'label="sous-sol"' in out
    assert 'label="local-tech"' in out
    assert 'label="baie-A"' in out
    assert "Box" in out
    assert "Switch" in out


def test_graphviz_non_localised_group():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:99": make_host("aa:bb:cc:dd:ee:99", "192.168.1.99"),
    }, last_scan=datetime(2026, 5, 24))
    out = render_graphviz(inv)
    assert 'label="Non localisé"' in out


def test_graphviz_offline_host_dashed():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            location=Location(floor="RDC", room="salon"),
            online=False,
        ),
    }, last_scan=datetime(2026, 5, 24))
    out = render_graphviz(inv)
    assert "style=dashed" in out


def test_graphviz_escapes_double_quotes():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            custom_name='PC "test"',
            location=Location(floor="RDC", room="salon"),
        ),
    }, last_scan=datetime(2026, 5, 24))
    out = render_graphviz(inv)
    assert 'PC \\"test\\"' in out


def test_graphviz_draws_edge_for_valid_uplink():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(
                switch_mac="aa:bb:cc:dd:ee:01",
                switch_port=4,
                patch_port=7,
                poe=False,
            ),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_graphviz(inv)
    assert " -- " in out
    assert "sw:4" in out
    assert "pp:7" in out


def test_graphviz_poe_uplink_styled_orange():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.10",
            custom_name="Switch",
            location=Location(floor="sous-sol", room="local-tech", rack="baie-A"),
        ),
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(switch_mac="aa:bb:cc:dd:ee:01",
                          switch_port=4, poe=True),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_graphviz(inv)
    assert "PoE" in out
    assert 'color="orange"' in out
    assert "penwidth=2" in out


def test_graphviz_uplink_to_unknown_mac_is_silently_skipped():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:02": make_host(
            "aa:bb:cc:dd:ee:02", "192.168.1.50",
            custom_name="Cam",
            location=Location(floor="RDC", room="hall"),
            uplink=Uplink(switch_mac="ff:ff:ff:ff:ff:ff", switch_port=4),
        ),
    }, last_scan=datetime(2026, 5, 24))

    out = render_graphviz(inv)
    assert " -- " not in out
    assert "sw:4" not in out


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


# ---------------------------------------------------------------------------
# icons.py — PLANTUML_SPRITES map and copy_icons_to helper
# ---------------------------------------------------------------------------

import pytest


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
