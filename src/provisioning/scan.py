"""Pure SSID decode and dedupe for WLAN scan results.

No ``machine``, ``network``, or socket imports.
"""


def decode_ssid(raw):
    """
    Decode a scan SSID to a displayable UTF-8 string.

    Accepts ``str`` or ``bytes``/``bytearray``. Returns ``None`` when the value
    is empty, undecodable, contains NUL, or exceeds 32 UTF-8 bytes.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, (bytes, bytearray)):
        try:
            text = bytes(raw).decode("utf-8")
        except Exception:
            return None
    else:
        return None
    if not text or "\x00" in text:
        return None
    try:
        encoded = text.encode("utf-8")
    except Exception:
        return None
    if len(encoded) < 1 or len(encoded) > 32:
        return None
    return text


def ssids_from_scan_rows(rows):
    """
    Extract deduplicated SSIDs from MicroPython-style scan rows.

    Each row may be a sequence whose first element is the SSID, or a bare
    SSID value. Undecodable / empty / oversized entries are omitted. Order of
    first appearance is preserved. Never returns BSSID or passwords.
    """
    if rows is None:
        return []
    seen = set()
    out = []
    for row in rows:
        raw = row[0] if isinstance(row, (tuple, list)) and row else row
        ssid = decode_ssid(raw)
        if ssid is None or ssid in seen:
            continue
        seen.add(ssid)
        out.append(ssid)
    return out
