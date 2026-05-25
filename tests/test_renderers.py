import pytest
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
    # Make sure the surrounding label quotes aren't broken; sprite prefix precedes the name
    assert '"<$question>\\nPC \\"test\\"' in out


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
    assert "dashed" in out


def test_graphviz_escapes_double_quotes():
    inv = Inventory(hosts={
        "aa:bb:cc:dd:ee:01": make_host(
            "aa:bb:cc:dd:ee:01", "192.168.1.1",
            custom_name='PC "test"',
            location=Location(floor="RDC", room="salon"),
        ),
    }, last_scan=datetime(2026, 5, 24))
    out = render_graphviz(inv)
    # HTML labels don't need backslash-escaped quotes; the name appears verbatim
    assert 'PC "test"' in out
    # The node label is HTML format (angle brackets), not text format (quotes)
    assert "label=<" in out


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


def test_copy_icons_to_validates_all_types_before_copying(tmp_path):
    """If any requested type is unknown, no files should be written."""
    from intramap.renderers.icons import copy_icons_to

    # router is valid, refrigerator is not — the call must fail and leave
    # no partial state.
    with pytest.raises(ValueError, match="refrigerator"):
        copy_icons_to(tmp_path, ["router", "refrigerator"])

    icons_dir = tmp_path / "icons"
    # No file from the valid type was copied either
    assert not (icons_dir / "router.svg").exists()


# ---------------------------------------------------------------------------
# PlantUML renderer — sprite emission
# ---------------------------------------------------------------------------

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
    assert "dashed" in out


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
    assert "<<offline>>" in out
    nas_color_lines = [l for l in out.splitlines() if "#9467bd" in l]
    assert nas_color_lines == []


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
    assert "Wi-Fi" in out
    assert "sw:5" in out


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
    assert "aa:bb:cc:dd:ee:01" in out
    assert "Switch principal\\nNone" not in out
    assert "Switch principal\\n?" not in out


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
    assert "2026-05-24" in out
