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
    monkeypatch.setattr(i18n.locale, "getlocale",
                        lambda *a: ("fr_FR", "UTF-8"))
    assert i18n.resolve_system_language() == "fr"
    monkeypatch.setattr(i18n.locale, "getlocale",
                        lambda *a: ("de_DE", "UTF-8"))
    assert i18n.resolve_system_language() == "en"


def test_available_languages_includes_system_fr_en():
    codes = [code for code, _label in i18n.available_languages()]
    assert codes == ["system", "fr", "en"]


def test_english_catalog_covers_key_chrome_strings():
    # Garantit qu'aucune chaîne-clé du chrome ne reste en français en anglais.
    for src in ("Nouveau", "Enregistrer", "Annuler", "Rétablir",
                "Ajouter un device", "Fermer l'inventaire"):
        assert src in i18n._CATALOG["en"], src
