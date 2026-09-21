"""Whole-record validation for the version-1 device settings object.

Pure module: no ``machine``, ``network``, or socket imports.
"""

from src.provisioning.constants import (
    ADMIN_VERIFIER_VERSION,
    LEGACY_ADMIN_VERIFIER_VERSION,
)

LEGACY_SETTINGS_VERSION = 1
SETTINGS_VERSION = 2
COLOR_SCHEME_V1 = "forest-amber"

_LEGACY_REQUIRED_KEYS = frozenset(
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
_ALERT_REQUIRED_KEYS = frozenset(("id", "hour", "minute", "enabled", "weekdays"))
_V2_REQUIRED_KEYS = _LEGACY_REQUIRED_KEYS | frozenset(
    ("alerts", "postpone_delay_minutes")
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
    version = obj.get("settings_version")
    if type(version) is not int:
        return ValidationResult(False, REASON_MALFORMED)
    if version == LEGACY_SETTINGS_VERSION:
        required_keys = _LEGACY_REQUIRED_KEYS
    elif version == SETTINGS_VERSION:
        required_keys = _V2_REQUIRED_KEYS
    else:
        return ValidationResult(False, REASON_UNSUPPORTED)
    if not required_keys.issubset(keys):
        return ValidationResult(False, REASON_INCOMPLETE)
    if keys != required_keys:
        return ValidationResult(False, REASON_INVALID)

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

    if obj.get("admin_verifier_version") not in (
        ADMIN_VERIFIER_VERSION,
        LEGACY_ADMIN_VERIFIER_VERSION,
    ):
        return ValidationResult(False, REASON_UNSUPPORTED)

    salt = obj.get("admin_salt")
    verifier = obj.get("admin_verifier")
    if not _is_lowercase_hex(salt, 32) or not _is_lowercase_hex(verifier, 64):
        return ValidationResult(False, REASON_INVALID)

    if obj.get("color_scheme") != COLOR_SCHEME_V1:
        return ValidationResult(False, REASON_INVALID)

    alerts = []
    postpone_delay_minutes = 10
    if version == SETTINGS_VERSION:
        raw_alerts = obj.get("alerts")
        postpone_delay_minutes = obj.get("postpone_delay_minutes")
        if not isinstance(raw_alerts, list) or len(raw_alerts) > 10:
            return ValidationResult(False, REASON_INVALID)
        if type(postpone_delay_minutes) is not int or not 1 <= postpone_delay_minutes <= 60:
            return ValidationResult(False, REASON_INVALID)
        for alert in raw_alerts:
            if not isinstance(alert, dict) or frozenset(alert.keys()) != _ALERT_REQUIRED_KEYS:
                return ValidationResult(False, REASON_INVALID)
            alert_id = alert.get("id")
            if (
                not isinstance(alert_id, str)
                or not alert_id
                or len(alert_id) > 64
                or alert_id != alert_id.lower()
                or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in alert_id)
            ):
                return ValidationResult(False, REASON_INVALID)
            if type(alert.get("hour")) is not int or not 0 <= alert["hour"] <= 23:
                return ValidationResult(False, REASON_INVALID)
            if type(alert.get("minute")) is not int or not 0 <= alert["minute"] <= 59:
                return ValidationResult(False, REASON_INVALID)
            if type(alert.get("enabled")) is not bool:
                return ValidationResult(False, REASON_INVALID)
            weekdays = alert.get("weekdays")
            if (
                not isinstance(weekdays, list)
                or len(weekdays) > 7
                or any(type(day) is not int or not 0 <= day <= 6 for day in weekdays)
                or len(set(weekdays)) != len(weekdays)
            ):
                return ValidationResult(False, REASON_INVALID)
            alerts.append(
                {
                    "id": alert_id,
                    "hour": alert["hour"],
                    "minute": alert["minute"],
                    "enabled": alert["enabled"],
                    "weekdays": list(weekdays),
                }
            )

    settings = {
        "settings_version": version,
        "wifi_ssid": ssid,
        "wifi_password": password,
        "admin_verifier_version": ADMIN_VERIFIER_VERSION,
        "admin_salt": salt,
        "admin_verifier": verifier,
        "color_scheme": COLOR_SCHEME_V1,
    }
    if version == SETTINGS_VERSION:
        settings["alerts"] = alerts
        settings["postpone_delay_minutes"] = postpone_delay_minutes
    return ValidationResult(True, REASON_OK, settings)


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


def validate_admin_password_field(admin_password):
    """
    Validate an Admin password field (Setup admin / Config change band).

    UTF-8 length 8–63 with no NUL. Never persists plaintext.
    """
    if not _field_utf8_ok(admin_password, 8, 63):
        return ValidationResult(False, REASON_INVALID)
    return ValidationResult(
        True,
        REASON_OK,
        {"admin_password": admin_password},
    )


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
    check = validate_admin_password_field(admin_password)
    if not check.ok:
        return check
    return ValidationResult(
        True,
        REASON_OK,
        {
            "ssid": ssid,
            "wifi_password": wifi_password,
            "admin_password": admin_password,
        },
    )
