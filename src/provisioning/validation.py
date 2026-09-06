"""Whole-record validation for the version-1 device settings object.

Pure module: no ``machine``, ``network``, or socket imports.
"""

from src.provisioning.verifier import ADMIN_VERIFIER_VERSION

SETTINGS_VERSION = 1
COLOR_SCHEME_V1 = "forest-amber"

_REQUIRED_KEYS = frozenset(
    (
        "settings_version",
        "wifi_ssid",
        "wifi_password",
        "admin_verifier_version",
        "admin_salt",
        "admin_verifier",
        "color_scheme",
    )
)

REASON_ABSENT = "absent"
REASON_MALFORMED = "malformed"
REASON_UNSUPPORTED = "unsupported"
REASON_INCOMPLETE = "incomplete"
REASON_INVALID = "invalid"
REASON_OK = "ok"


class ValidationResult:
    """Outcome of validating a settings record as a whole."""

    __slots__ = ("ok", "reason", "settings")

    def __init__(self, ok, reason, settings=None):
        self.ok = bool(ok)
        self.reason = reason
        self.settings = settings

    def __repr__(self):
        return "ValidationResult(ok={!r}, reason={!r}, settings={!r})".format(
            self.ok, self.reason, self.settings
        )


def _utf8_len(value):
    return len(value.encode("utf-8"))


def _is_lowercase_hex(text, length):
    if not isinstance(text, str) or len(text) != length:
        return False
    for ch in text:
        if ch not in "0123456789abcdef":
            return False
    return True


def validate_settings_object(obj):
    """
    Validate a decoded settings object.

    Returns a :class:`ValidationResult`. Absent/None → unconfigured. Wrong
    types or non-object JSON → malformed. Unsupported version → unsupported.
    Missing/extra keys or field-rule failures → incomplete/invalid.
    """
    if obj is None:
        return ValidationResult(False, REASON_ABSENT)
    if not isinstance(obj, dict):
        return ValidationResult(False, REASON_MALFORMED)

    keys = frozenset(obj.keys())
    if not _REQUIRED_KEYS.issubset(keys):
        return ValidationResult(False, REASON_INCOMPLETE)
    if keys != _REQUIRED_KEYS:
        return ValidationResult(False, REASON_INVALID)

    version = obj.get("settings_version")
    if type(version) is not int:
        return ValidationResult(False, REASON_MALFORMED)
    if version != SETTINGS_VERSION:
        return ValidationResult(False, REASON_UNSUPPORTED)

    ssid = obj.get("wifi_ssid")
    password = obj.get("wifi_password")
    if not isinstance(ssid, str) or not isinstance(password, str):
        return ValidationResult(False, REASON_MALFORMED)

    try:
        ssid_len = _utf8_len(ssid)
        password_len = _utf8_len(password)
        ssid_bytes = ssid.encode("utf-8")
        password_bytes = password.encode("utf-8")
    except Exception:
        return ValidationResult(False, REASON_MALFORMED)

    if ssid_len < 1 or ssid_len > 32:
        return ValidationResult(False, REASON_INVALID)
    if password_len < 8 or password_len > 63:
        return ValidationResult(False, REASON_INVALID)
    if "\x00" in ssid or b"\x00" in ssid_bytes:
        return ValidationResult(False, REASON_INVALID)
    if "\x00" in password or b"\x00" in password_bytes:
        return ValidationResult(False, REASON_INVALID)

    if obj.get("admin_verifier_version") != ADMIN_VERIFIER_VERSION:
        return ValidationResult(False, REASON_UNSUPPORTED)

    salt = obj.get("admin_salt")
    verifier = obj.get("admin_verifier")
    if not _is_lowercase_hex(salt, 32) or not _is_lowercase_hex(verifier, 64):
        return ValidationResult(False, REASON_INVALID)

    if obj.get("color_scheme") != COLOR_SCHEME_V1:
        return ValidationResult(False, REASON_INVALID)

    return ValidationResult(
        True,
        REASON_OK,
        {
            "settings_version": SETTINGS_VERSION,
            "wifi_ssid": ssid,
            "wifi_password": password,
            "admin_verifier_version": ADMIN_VERIFIER_VERSION,
            "admin_salt": salt,
            "admin_verifier": verifier,
            "color_scheme": COLOR_SCHEME_V1,
        },
    )


def validate_settings_json(text):
    """Parse JSON text and validate as a whole record."""
    if text is None:
        return ValidationResult(False, REASON_ABSENT)
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except Exception:
            return ValidationResult(False, REASON_MALFORMED)
    if not isinstance(text, str):
        return ValidationResult(False, REASON_MALFORMED)
    stripped = text.strip()
    if not stripped:
        return ValidationResult(False, REASON_ABSENT)
    try:
        import json

        obj = json.loads(stripped)
    except Exception:
        return ValidationResult(False, REASON_MALFORMED)
    return validate_settings_object(obj)


def _field_utf8_ok(value, min_len, max_len):
    if not isinstance(value, str):
        return False
    if "\x00" in value:
        return False
    try:
        encoded = value.encode("utf-8")
    except Exception:
        return False
    length = len(encoded)
    return min_len <= length <= max_len


def validate_setup_form_fields(ssid, wifi_password, admin_password):
    """
    Validate Connect form fields before creating a setup candidate.

    SSID 1–32 and Wi-Fi password 8–63 match the persisted record rules.
    Admin password uses the same 8–63 UTF-8 length band (never persisted
    as plaintext).
    """
    if not _field_utf8_ok(ssid, 1, 32):
        return ValidationResult(False, REASON_INVALID)
    if not _field_utf8_ok(wifi_password, 8, 63):
        return ValidationResult(False, REASON_INVALID)
    if not _field_utf8_ok(admin_password, 8, 63):
        return ValidationResult(False, REASON_INVALID)
    return ValidationResult(
        True,
        REASON_OK,
        {
            "ssid": ssid,
            "wifi_password": wifi_password,
            "admin_password": admin_password,
        },
    )
