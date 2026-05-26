import pytest
from datetime import datetime

from intramap.models import Host, Inventory, Link, Location
from intramap.renderers.graphviz import render as render_graphviz
from intramap.renderers.plantuml import render as render_plantuml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_host(mac, ip=None, *, custom_name=None, location=None,
              vendor=None, device_type=None, online=True, wifi_ap_mac=None):
    now = datetime(2026, 5, 24, 14, 0, 0)
    return Host(
        mac=mac, ip=ip, hostname=None, vendor=vendor,
        custom_name=custom_name, location=location or Location(),
        device_type=device_type,
        first_seen=now, last_seen=now, online=online,
        wifi_ap_mac=wifi_ap_mac,
    )


@pytest.fixture
def make_host_factory():
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


def _inv(*hosts, links=()):
    return Inventory(hosts={h.mac: h for h in hosts},
                     links=list(links),
                     last_scan=datetime(2026, 5, 24))


# ---------------------------------------------------------------------------
# PlantUML : structure et groupes
# ---------------------------------------------------------------------------

def test_plantuml_groups_by_floor_room_rack():
    inv = _inv(
        make_host("aa:bb:cc:dd:ee:01", "192.168.1.1", custom_name="Box",
                  location=Location(floor="RDC", room="salon")),
        make_host("aa:bb:cc:dd:ee:02", "192.168.1.10", custom_name="Switch",
                  location=Location(floor="sous-sol", room="local-tech",
                                    rack="baie-A")),
    )
    out = render_plantuml(inv)
    assert out.startswith("@startuml")
    assert out.rstrip().endswith("@enduml")
    for label in ('"RDC"', '"salon"', '"sous-sol"', '"local-tech"', '"baie-A"',
                  "Box", "Switch"):
        assert label in out


def test_plantuml_hosts_without_floor_go_to_non_localised():
    inv = _inv(make_host("aa:bb:cc:dd:ee:99", "192.168.1.99"))
    out = render_plantuml(inv)
    assert 'package "Non localisé"' in out
    assert "aa:bb:cc:dd:ee:99" in out


def test_plantuml_floor_set_without_room_gets_placeholder_room():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         location=Location(floor="RDC")))
    out = render_plantuml(inv)
    assert 'package "RDC"' in out
    assert 'package "(sans pièce)"' in out


def test_plantuml_offline_host_has_offline_stereotype():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         location=Location(floor="RDC", room="salon"),
                         online=False))
    out = render_plantuml(inv)
    assert "<<offline>>" in out


def test_plantuml_escapes_double_quotes_in_names():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         custom_name='PC "test"',
                         location=Location(floor="RDC", room="salon")))
    out = render_plantuml(inv)
    assert 'PC \\"test\\"' in out


def test_plantuml_has_top_to_bottom_direction():
    out = render_plantuml(Inventory())
    assert "top to bottom direction" in out


# ---------------------------------------------------------------------------
# PlantUML : arêtes
# ---------------------------------------------------------------------------

def test_plantuml_draws_one_edge_per_link():
    sw = make_host("aa:bb:cc:dd:ee:01", custom_name="Switch", device_type="switch",
                   location=Location(floor="sous-sol", room="local-tech"))
    cam = make_host("aa:bb:cc:dd:ee:02", custom_name="Cam",
                    location=Location(floor="RDC", room="hall"))
    inv = _inv(sw, cam, links=[
        Link(mac_a=cam.mac, port_a=None, mac_b=sw.mac, port_b=4, poe=False),
    ])
    out = render_plantuml(inv)
    assert " -- " in out


def test_plantuml_poe_link_uses_orange_style():
    sw = make_host("aa:bb:cc:dd:ee:01", custom_name="Switch", device_type="switch",
                   location=Location(floor="sous-sol", room="local-tech"))
    cam = make_host("aa:bb:cc:dd:ee:02", custom_name="Cam",
                    location=Location(floor="RDC", room="hall"))
    inv = _inv(sw, cam, links=[
        Link(mac_a=cam.mac, mac_b=sw.mac, port_b=4, poe=True),
    ])
    out = render_plantuml(inv)
    assert "[#orange,thickness=2]" in out
    assert "PoE" in out


def test_plantuml_link_to_unknown_mac_silently_skipped():
    cam = make_host("aa:bb:cc:dd:ee:02", custom_name="Cam",
                    location=Location(floor="RDC", room="hall"))
    inv = _inv(cam, links=[
        Link(mac_a=cam.mac, mac_b="ff:ff:ff:ff:ff:ff", port_b=4),
    ])
    out = render_plantuml(inv)
    assert " -- " not in out


# ---------------------------------------------------------------------------
# Graphviz : structure
# ---------------------------------------------------------------------------

def test_graphviz_outputs_a_graph():
    out = render_graphviz(Inventory())
    assert out.lstrip().startswith("graph ")
    assert out.rstrip().endswith("}")


def test_graphviz_groups_with_clusters():
    inv = _inv(
        make_host("aa:bb:cc:dd:ee:01", "192.168.1.1", custom_name="Box",
                  location=Location(floor="RDC", room="salon")),
        make_host("aa:bb:cc:dd:ee:02", "192.168.1.10", custom_name="Switch",
                  location=Location(floor="sous-sol", room="local-tech",
                                    rack="baie-A")),
    )
    out = render_graphviz(inv)
    assert "subgraph cluster_" in out
    for lbl in ('"RDC"', '"salon"', '"sous-sol"', '"local-tech"', '"baie-A"'):
        assert f'label={lbl}' in out


def test_graphviz_non_localised_group():
    inv = _inv(make_host("aa:bb:cc:dd:ee:99", "192.168.1.99"))
    assert 'label="Non localisé"' in render_graphviz(inv)


def test_graphviz_offline_host_dashed():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         location=Location(floor="RDC", room="salon"),
                         online=False))
    assert "dashed" in render_graphviz(inv)


def test_graphviz_escapes_double_quotes():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         custom_name='PC "test"',
                         location=Location(floor="RDC", room="salon")))
    out = render_graphviz(inv)
    assert 'PC "test"' in out
    assert "label=<" in out


def test_graphviz_has_top_bottom_rankdir():
    out = render_graphviz(Inventory())
    assert "rankdir=TB" in out
    assert "splines=ortho" in out


def test_graphviz_uses_html_labels(make_host_factory):
    inv = _inv(make_host_factory(custom_name="NAS", vendor="Synology"))
    out = render_graphviz(inv)
    assert "label=<" in out
    assert "<B>NAS</B>" in out
    assert "<BR/>" in out


def test_graphviz_has_tooltip(make_host_factory):
    last = datetime(2026, 5, 24, 10, 0, 0)
    inv = _inv(make_host_factory(vendor="Synology", last_seen=last))
    out = render_graphviz(inv)
    assert "tooltip=" in out
    assert "Synology" in out and "2026-05-24" in out


# ---------------------------------------------------------------------------
# Graphviz : arêtes
# ---------------------------------------------------------------------------

def test_graphviz_draws_edge_for_link():
    sw = make_host("aa:bb:cc:dd:ee:01", custom_name="Switch", device_type="switch",
                   location=Location(floor="sous-sol", room="local-tech"))
    cam = make_host("aa:bb:cc:dd:ee:02", custom_name="Cam",
                    location=Location(floor="RDC", room="hall"))
    inv = _inv(sw, cam, links=[Link(mac_a=cam.mac, mac_b=sw.mac, port_b=4)])
    out = render_graphviz(inv)
    assert " -- " in out


def test_graphviz_poe_link_styled_orange():
    sw = make_host("aa:bb:cc:dd:ee:01", custom_name="Switch", device_type="switch",
                   location=Location(floor="sous-sol", room="local-tech"))
    cam = make_host("aa:bb:cc:dd:ee:02", custom_name="Cam",
                    location=Location(floor="RDC", room="hall"))
    inv = _inv(sw, cam, links=[
        Link(mac_a=cam.mac, mac_b=sw.mac, port_b=4, poe=True),
    ])
    out = render_graphviz(inv)
    assert "PoE" in out
    assert 'color="orange"' in out
    assert "penwidth=2" in out


def test_graphviz_link_to_unknown_mac_silently_skipped():
    cam = make_host("aa:bb:cc:dd:ee:02", custom_name="Cam",
                    location=Location(floor="RDC", room="hall"))
    inv = _inv(cam, links=[Link(mac_a=cam.mac, mac_b="ff:ff:ff:ff:ff:ff",
                                port_b=4)])
    out = render_graphviz(inv)
    assert " -- " not in out


def test_graphviz_emits_image_attribute(make_host_factory):
    inv = _inv(make_host_factory(vendor="Synology", custom_name="NAS"))
    out = render_graphviz(inv)
    assert 'image="icons/nas.png"' in out
    assert 'labelloc="b"' in out


def test_graphviz_explicit_device_type_overrides_inference(make_host_factory):
    inv = _inv(make_host_factory(vendor="TP-Link Systems",
                                 device_type="controller"))
    out = render_graphviz(inv)
    assert 'image="icons/controller.png"' in out
    assert 'image="icons/ap.png"' not in out


def test_graphviz_unknown_vendor_uses_other_icon(make_host_factory):
    inv = _inv(make_host_factory(vendor=None))
    assert 'image="icons/other.png"' in render_graphviz(inv)


def test_graphviz_offline_host_keeps_image_and_dashed(make_host_factory):
    inv = _inv(make_host_factory(vendor="Synology", online=False))
    out = render_graphviz(inv)
    assert 'image="icons/nas.png"' in out
    assert "dashed" in out


def test_graphviz_copy_assets_to_writes_icons(tmp_path, make_host_factory):
    inv = _inv(
        make_host_factory(mac="aa:bb:cc:dd:ee:01", vendor="Synology"),
        make_host_factory(mac="aa:bb:cc:dd:ee:02", vendor="Sagemcom"),
    )
    render_graphviz(inv, copy_assets_to=tmp_path)
    assert (tmp_path / "icons" / "nas.png").is_file()
    assert (tmp_path / "icons" / "router.png").is_file()


# ---------------------------------------------------------------------------
# Wi-Fi
# ---------------------------------------------------------------------------

def test_plantuml_draws_wifi_edge_when_valid(make_host_factory):
    inv = _inv(
        make_host_factory(mac="aa:bb:cc:dd:ee:01", vendor="TP-Link Systems",
                          custom_name="AP RDC"),
        make_host_factory(mac="aa:bb:cc:dd:ee:02", vendor="Apple",
                          custom_name="iPhone",
                          wifi_ap_mac="aa:bb:cc:dd:ee:01"),
    )
    out = render_plantuml(inv)
    assert "..>" in out and "Wi-Fi" in out


def test_plantuml_wifi_to_unknown_mac_skipped(make_host_factory):
    inv = _inv(make_host_factory(mac="aa:bb:cc:dd:ee:02", vendor="Apple",
                                 wifi_ap_mac="ff:ff:ff:ff:ff:ff"))
    out = render_plantuml(inv)
    assert "..>" not in out


def test_graphviz_draws_wifi_edge_when_valid(make_host_factory):
    inv = _inv(
        make_host_factory(mac="aa:bb:cc:dd:ee:01", vendor="TP-Link"),
        make_host_factory(mac="aa:bb:cc:dd:ee:02", vendor="Apple",
                          wifi_ap_mac="aa:bb:cc:dd:ee:01"),
    )
    out = render_graphviz(inv)
    assert "style=dashed" in out and "Wi-Fi" in out


def test_graphviz_wifi_to_unknown_mac_skipped(make_host_factory):
    inv = _inv(make_host_factory(mac="aa:bb:cc:dd:ee:02", vendor="Apple",
                                 wifi_ap_mac="ff:ff:ff:ff:ff:ff"))
    out = render_graphviz(inv)
    assert 'style=dashed, color="#1f77b4"' not in out


# ---------------------------------------------------------------------------
# Icônes + sprites + couleurs
# ---------------------------------------------------------------------------

def test_all_device_type_icons_are_bundled():
    from importlib.resources import files
    from intramap.models import DEVICE_TYPES
    icons_root = files("intramap.renderers") / "icons"
    for t in DEVICE_TYPES:
        assert (icons_root / f"{t}.svg").is_file()
        assert (icons_root / f"{t}.png").is_file()


def test_icons_license_is_bundled():
    from importlib.resources import files
    p = files("intramap.renderers") / "icons" / "LICENSE"
    assert p.is_file()
    content = p.read_text(encoding="utf-8")
    assert "Creative Commons" in content or "CC BY" in content


def test_plantuml_sprites_cover_all_device_types():
    from intramap.models import DEVICE_TYPES
    from intramap.renderers.icons import PLANTUML_SPRITES
    assert set(PLANTUML_SPRITES.keys()) == set(DEVICE_TYPES)


def test_device_colors_cover_all_device_types():
    from intramap.models import DEVICE_TYPES
    from intramap.renderers.icons import DEVICE_COLORS
    assert set(DEVICE_COLORS.keys()) == set(DEVICE_TYPES)


def test_copy_icons_to_creates_subdir_and_copies_requested(tmp_path):
    from intramap.renderers.icons import copy_icons_to
    copy_icons_to(tmp_path, {"router", "nas"})
    icons = tmp_path / "icons"
    assert (icons / "router.png").is_file()
    assert (icons / "nas.png").is_file()
    assert not (icons / "tv.png").exists()


def test_copy_icons_to_unknown_type_raises(tmp_path):
    from intramap.renderers.icons import copy_icons_to
    with pytest.raises(ValueError, match="refrigerator"):
        copy_icons_to(tmp_path, {"refrigerator"})


def test_copy_icons_to_validates_all_types_before_writing(tmp_path):
    # Un type inconnu dans le lot doit faire échouer AVANT d'écrire le moindre
    # fichier (sortie atomique).
    from intramap.renderers.icons import copy_icons_to
    with pytest.raises(ValueError, match="refrigerator"):
        copy_icons_to(tmp_path, ["router", "refrigerator"])
    assert not (tmp_path / "icons" / "router.png").exists()


def test_copy_icons_to_is_idempotent(tmp_path):
    from intramap.renderers.icons import copy_icons_to
    copy_icons_to(tmp_path, {"router"})
    copy_icons_to(tmp_path, {"router"})  # 2e passage : ne doit pas lever
    assert (tmp_path / "icons" / "router.png").is_file()


def test_device_colors_are_valid_hex():
    import re as _re
    from intramap.renderers.icons import DEVICE_COLORS
    for dtype, color in DEVICE_COLORS.items():
        assert _re.fullmatch(r"#[0-9a-fA-F]{6}", color), (dtype, color)


def test_plantuml_sprites_are_nonempty_identifiers():
    from intramap.renderers.icons import PLANTUML_SPRITES
    for dtype, sprite in PLANTUML_SPRITES.items():
        assert sprite and _re_ok(sprite), (dtype, sprite)


def _re_ok(sprite: str) -> bool:
    import re as _re
    # Noms FontAwesome : minuscules, chiffres et underscores (ex. network_wired).
    return bool(_re.fullmatch(r"[a-z0-9_]+", sprite))


def test_plantuml_pins_key_sprites():
    # Quelques sprites critiques épinglés (le branche a changé ces valeurs).
    from intramap.renderers.icons import PLANTUML_SPRITES
    assert PLANTUML_SPRITES["router"] == "tower_broadcast"
    assert PLANTUML_SPRITES["switch"] == "network_wired"
    assert PLANTUML_SPRITES["other"] == "question"


# ---------------------------------------------------------------------------
# PlantUML : émission des sprites FontAwesome (!include)
# ---------------------------------------------------------------------------

def test_plantuml_emits_one_include_per_used_sprite_sorted_and_deduped():
    sw = make_host("aa:bb:cc:dd:ee:01", device_type="switch")
    sw2 = make_host("aa:bb:cc:dd:ee:02", device_type="switch")  # même sprite
    nas = make_host("aa:bb:cc:dd:ee:03", device_type="nas")
    out = render_plantuml(_inv(sw, sw2, nas))
    includes = [ln for ln in out.splitlines() if ln.startswith("!include")]
    # Dédupliqué (un seul switch malgré deux hôtes) et trié.
    assert includes == sorted(includes)
    assert len(includes) == len(set(includes))
    assert any("network_wired" in ln for ln in includes)
    assert any("hard_drive" in ln for ln in includes)


def test_plantuml_node_label_starts_with_sprite():
    nas = make_host("aa:bb:cc:dd:ee:03", custom_name="Stockage",
                    device_type="nas")
    out = render_plantuml(_inv(nas))
    assert "<$hard_drive>" in out


def test_plantuml_explicit_device_type_selects_its_sprite():
    h = make_host("aa:bb:cc:dd:ee:01", vendor="Synology", device_type="camera")
    out = render_plantuml(_inv(h))
    assert "<$video>" in out          # camera, malgré le vendor NAS
    assert "<$hard_drive>" not in out


def test_plantuml_invalid_device_type_falls_back_to_question_sprite():
    h = make_host("aa:bb:cc:dd:ee:01", device_type="licorne")
    out = render_plantuml(_inv(h))
    assert "<$question>" in out


# ---------------------------------------------------------------------------
# Étiquettes : ne pas laisser fuir « None » quand l'IP est absente
# ---------------------------------------------------------------------------

def test_plantuml_label_omits_ip_when_null():
    h = make_host("aa:bb:cc:dd:ee:01", ip=None, custom_name="Switch",
                  device_type="switch")
    out = render_plantuml(_inv(h))
    assert "None" not in out


def test_graphviz_html_label_omits_ip_when_null():
    h = make_host("aa:bb:cc:dd:ee:01", ip=None, custom_name="Switch",
                  device_type="switch")
    out = render_graphviz(_inv(h))
    assert "None" not in out


# ---------------------------------------------------------------------------
# Légende
# ---------------------------------------------------------------------------

def test_plantuml_emits_legend(make_host_factory):
    inv = _inv(make_host_factory(vendor="Synology"))
    out = render_plantuml(inv)
    assert 'package "Légende"' in out
    legend = out.split('package "Légende"', 1)[1]
    assert "nas" in legend
    assert "router" not in legend


def test_graphviz_emits_legend(make_host_factory):
    inv = _inv(make_host_factory(vendor="Synology"))
    out = render_graphviz(inv)
    assert 'subgraph cluster_legend' in out
    legend = out.split('subgraph cluster_legend', 1)[1]
    assert "legend_nas" in legend
    assert "legend_router" not in legend


def test_plantuml_legend_includes_edge_styles(make_host_factory):
    inv = _inv(make_host_factory(vendor="Synology"))
    legend = render_plantuml(inv).split('package "Légende"', 1)[1]
    assert "wired" in legend and "PoE" in legend and "Wi-Fi" in legend


def test_graphviz_legend_includes_edge_styles(make_host_factory):
    inv = _inv(make_host_factory(vendor="Synology"))
    legend = render_graphviz(inv).split("subgraph cluster_legend", 1)[1]
    assert "legend_wired" in legend
    assert "legend_poe" in legend
    assert "legend_wifi" in legend


# ---------------------------------------------------------------------------
# Échappement robuste (guillemets ET backslash) dans les chaînes émises
# ---------------------------------------------------------------------------

def test_graphviz_tooltip_escapes_double_quote_in_vendor():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         custom_name="Box", vendor='Acme "Pro"'))
    out = render_graphviz(inv)
    # Le guillemet du vendor ne doit pas casser l'attribut tooltip="...".
    assert r'tooltip="Acme \"Pro\"' in out


def test_graphviz_escapes_backslash_in_cluster_label():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1", custom_name="Box",
                         location=Location(floor="Cave\\Nord", room="salon")))
    out = render_graphviz(inv)
    assert r'label="Cave\\Nord"' in out


def test_plantuml_escapes_backslash_in_name():
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1",
                         custom_name="PC\\test",
                         location=Location(floor="RDC", room="salon")))
    out = render_plantuml(inv)
    assert r"PC\\test" in out


def test_plantuml_label_newline_separator_preserved():
    # Le séparateur \n entre nom / ip / mac doit rester un saut de ligne
    # PlantUML (un seul backslash), pas être échappé en \\n par mégarde.
    inv = _inv(make_host("aa:bb:cc:dd:ee:01", "192.168.1.1", custom_name="Box"))
    out = render_plantuml(inv)
    assert r"Box\n192.168.1.1" in out
