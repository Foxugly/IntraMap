import re


_HEX12 = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(raw: str) -> str:
    """Return MAC in canonical form: lowercase, ':' separator.

    Accepts common variants (colons, dashes, no separator, mixed case).
    Raises ValueError on anything that is not a 48-bit MAC.
    """
    if not isinstance(raw, str):
        raise ValueError(f"MAC must be a string, got {type(raw).__name__}")
    compact = raw.strip().lower().replace(":", "").replace("-", "")
    if not _HEX12.match(compact):
        raise ValueError(f"Not a valid MAC address: {raw!r}")
    return ":".join(compact[i:i + 2] for i in range(0, 12, 2))
