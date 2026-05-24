import pytest

from intramap.models import normalize_mac


@pytest.mark.parametrize("raw, expected", [
    ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
    ("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
    ("aa-bb-cc-dd-ee-ff", "aa:bb:cc:dd:ee:ff"),
    ("AABBCCDDEEFF", "aa:bb:cc:dd:ee:ff"),
    ("  aa:bb:cc:dd:ee:ff  ", "aa:bb:cc:dd:ee:ff"),
])
def test_normalize_mac_accepts_common_formats(raw, expected):
    assert normalize_mac(raw) == expected


@pytest.mark.parametrize("bad", [
    "",
    "not-a-mac",
    "aa:bb:cc:dd:ee",          # too short
    "aa:bb:cc:dd:ee:ff:gg",    # too long
    "zz:bb:cc:dd:ee:ff",       # invalid hex
])
def test_normalize_mac_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_mac(bad)
