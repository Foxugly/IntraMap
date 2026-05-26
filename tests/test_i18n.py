"""Tests de l'infrastructure i18n (catalogue FR -> EN)."""
import pytest

from intramap.gui import i18n


@pytest.fixture(autouse=True)
def _reset_language():
    i18n.set_language("fr")
    yield
    i18n.set_language("fr")


def test_tr_returns_source_in_french():
    i18n.set_language("fr")
    assert i18n.tr("Nouveau") == "Nouveau"


def test_tr_translates_in_english():
    i18n.set_language("en")
    assert i18n.tr("Nouveau") == "New"


def test_tr_falls_back_to_source_when_missing():
    i18n.set_language("en")
    assert i18n.tr("Zzz jamais traduit") == "Zzz jamais traduit"


def test_set_language_invalid_defaults_to_french():
    i18n.set_language("klingon")
    assert i18n.current_language() == "fr"


def test_resolve_system_language(monkeypatch):
    from intramap import i18n as core
    monkeypatch.setattr(core.locale, "getlocale",
                        lambda *a: ("fr_FR", "UTF-8"))
    assert core.resolve_system_language() == "fr"
    monkeypatch.setattr(core.locale, "getlocale",
                        lambda *a: ("de_DE", "UTF-8"))
    assert core.resolve_system_language() == "en"


def test_available_languages_includes_system_fr_en():
    codes = [code for code, _label in i18n.available_languages()]
    assert codes == ["system", "fr", "en"]


def test_english_catalog_covers_key_chrome_strings():
    # Garantit qu'aucune chaîne-clé du chrome ne reste en français en anglais.
    for src in ("Nouveau", "Enregistrer", "Annuler", "Rétablir",
                "Ajouter un device", "Fermer l'inventaire"):
        assert src in i18n._CATALOG["en"], src


def _tr_literals(path):
    """Toutes les chaînes littérales passées à tr(...) dans un fichier."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            out.append(node.args[0].value)
    return out


def test_every_wrapped_string_has_english_translation():
    """Toute chaîne enrobée dans tr("…") (GUI + builders de rapports) doit
    avoir une entrée dans le catalogue anglais."""
    import pathlib
    import intramap as pkg
    root = pathlib.Path(pkg.__file__).parent
    files = sorted((root / "gui").glob("*.py"))
    files += [root / "wiring_report.py", root / "path_report.py",
              root / "diagnostics.py", root / "scan_diff.py"]
    missing = []
    for py in files:
        for lit in _tr_literals(py):
            if lit not in i18n._CATALOG["en"]:
                missing.append(f"{py.name}: {lit!r}")
    assert not missing, (
        "Chaînes enrobées sans traduction EN :\n" + "\n".join(missing))


def test_report_builders_translate_to_english():
    from datetime import datetime
    from intramap.models import Host, Inventory, Link
    from intramap.wiring_report import build_wiring_report
    from intramap.path_report import build_report
    from intramap.diagnostics import diagnose
    from intramap.scan_diff import diff_inventories, format_scan_diff

    now = datetime(2026, 5, 27)

    def _host(mac, **kw):
        d = dict(ip=None, hostname=None, vendor=None,
                 first_seen=now, last_seen=now)
        d.update(kw)
        return Host(mac=mac, **d)

    gw = _host("aa:bb:cc:dd:ee:01", is_gateway=True, device_type="router",
               custom_name="Box")
    sw = _host("aa:bb:cc:dd:ee:02", device_type="switch", custom_name="SW")
    inv = Inventory(hosts={gw.mac: gw, sw.mac: sw},
                    links=[Link(mac_a=sw.mac, port_a=1,
                                mac_b=gw.mac, port_b=8)])

    i18n.set_language("en")
    assert "Infrastructure device wiring" in build_wiring_report(inv)
    assert "Internet access ✓" in build_report(inv)
    no_gw = Inventory(hosts={sw.mac: sw})
    msgs = " ".join(f.message for f in diagnose(no_gw))
    assert "No Internet gateway declared" in msgs
    after = Inventory(hosts={sw.mac: sw})
    assert "New (" in format_scan_diff(diff_inventories(Inventory(), after),
                                       after)
