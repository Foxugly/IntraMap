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
