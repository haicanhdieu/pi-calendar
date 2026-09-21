"""Host tests for pure settings-record validation and import hygiene."""

import ast
from pathlib import Path

from src.provisioning.validation import (
    REASON_ABSENT,
    REASON_INCOMPLETE,
    REASON_INVALID,
    REASON_MALFORMED,
    REASON_UNSUPPORTED,
    validate_settings_json,
    validate_settings_object,
)
from src.provisioning.verifier import (
    ADMIN_VERIFIER_VERSION,
    derive_admin_verifier,
    verify_admin_password,
)
from src.device.web.alert_validation import validate_alert_form_fields, validate_alert_id
from src.device.web.postpone_route import validate_postpone_delay

_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = frozenset({"machine", "network", "socket", "ntptime"})


def _canonical_record(**overrides):
    salt, verifier = derive_admin_verifier(
        "admin-secret", salt=b"\x11" * 16
    )
    record = {
        "settings_version": 1,
        "wifi_ssid": "home-wifi",
        "wifi_password": "wifipass1",
        "admin_verifier_version": ADMIN_VERIFIER_VERSION,
        "admin_salt": salt,
        "admin_verifier": verifier,
        "color_scheme": "forest-amber",
    }
    record.update(overrides)
    return record


def test_valid_complete_record_is_ok():
    result = validate_settings_object(_canonical_record())
    assert result.ok is True
    assert result.settings["wifi_ssid"] == "home-wifi"


def test_absent_and_empty_are_unconfigured():
    assert validate_settings_json(None).reason == REASON_ABSENT
    assert validate_settings_json("").reason == REASON_ABSENT
    assert validate_settings_object(None).reason == REASON_ABSENT


def test_malformed_json_and_non_object():
    assert validate_settings_json("{not-json").reason == REASON_MALFORMED
    assert validate_settings_object([1, 2]).reason == REASON_MALFORMED


def test_unsupported_version_preserved_as_unconfigured():
    result = validate_settings_object(_canonical_record(settings_version=99))
    assert result.ok is False
    assert result.reason == REASON_UNSUPPORTED


def test_bool_true_is_not_settings_version_one():
    result = validate_settings_object(_canonical_record(settings_version=True))
    assert result.ok is False
    assert result.reason == REASON_MALFORMED


def test_incomplete_missing_key():
    record = _canonical_record()
    del record["wifi_password"]
    result = validate_settings_object(record)
    assert result.ok is False
    assert result.reason == REASON_INCOMPLETE


def test_ssid_and_password_length_rules():
    assert (
        validate_settings_object(_canonical_record(wifi_ssid="")).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(wifi_ssid="x" * 33)
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(wifi_password="short")
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(wifi_password="p" * 64)
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(wifi_password="bad\x00pass")
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(wifi_ssid="bad\x00ssid")
        ).reason
        == REASON_INVALID
    )


def test_verifier_hex_and_color_scheme_rules():
    assert (
        validate_settings_object(
            _canonical_record(admin_salt="ZZ")
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(admin_verifier="ab")
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(color_scheme="other")
        ).reason
        == REASON_INVALID
    )
    assert (
        validate_settings_object(
            _canonical_record(admin_verifier_version="other")
        ).reason
        == REASON_UNSUPPORTED
    )


def test_derive_and_verify_admin_password_roundtrip():
    salt, verifier = derive_admin_verifier("s3cret-admin", salt=b"\xab" * 16)
    assert len(salt) == 32
    assert len(verifier) == 64
    assert verify_admin_password("s3cret-admin", salt, verifier) is True
    assert verify_admin_password("wrong", salt, verifier) is False


def test_pure_provisioning_modules_forbid_device_imports():
    for rel in (
        "src/provisioning/validation.py",
        "src/provisioning/verifier.py",
        "src/device/network/models.py",
    ):
        source = (_ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in _FORBIDDEN
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert node.module.split(".")[0] not in _FORBIDDEN


def test_alert_form_validation_returns_canonical_weekday_alert():
    result = validate_alert_form_fields(
        {"alert_action": "add", "alert_time": "07:00",
         "alert_enabled": "on", "weekday_0": "on", "weekday_4": "on"},
        "alert-1", 0,
    )
    assert result.ok is True
    assert result.settings == {
        "id": "alert-1", "hour": 7, "minute": 0,
        "enabled": True, "weekdays": [0, 4],
    }


def test_alert_form_validation_rejects_unknown_and_invalid_fields():
    base = {"alert_action": "add", "alert_time": "07:00"}
    assert validate_alert_form_fields(dict(base, extra="x"), "alert-1", 0).reason == "fields"
    assert validate_alert_form_fields(dict(base, alert_enabled="false"), "alert-1", 0).reason == "enabled"
    assert validate_alert_form_fields(dict(base, weekday_0="yes"), "alert-1", 0).reason == "recurrence"
    assert validate_alert_form_fields(base, "alert-1", 10).reason == "limit"


def test_alert_form_validation_accepts_edit_and_requires_matching_id():
    fields = {"alert_action": "edit", "alert_id": "morning",
              "alert_time": "06:30", "weekday_0": "on"}
    result = validate_alert_form_fields(fields, "morning", 1)
    assert result.ok
    assert result.settings["id"] == "morning"
    assert result.settings["hour"] == 6
    assert result.settings["weekdays"] == [0]
    assert validate_alert_form_fields(fields, "evening", 1).reason == "fields"


def test_alert_id_validation_accepts_stable_ids_and_rejects_unsafe_ids():
    assert validate_alert_id("morning-1").ok
    assert validate_alert_id("Morning").reason == "fields"
    assert validate_alert_id("morning/").reason == "fields"
    assert validate_alert_id(1).reason == "fields"
    assert validate_alert_id("").reason == "fields"
    assert validate_alert_id(None).reason == "fields"
    assert validate_alert_id("morning.1").reason == "fields"
    assert validate_alert_id("morning_1").reason == "fields"
    assert validate_alert_id(" morning").reason == "fields"
    assert validate_alert_id("9").ok
    assert validate_alert_id("-").ok


def test_alert_form_validation_rejects_malformed_time_and_accepts_boundaries():
    def _time(value):
        return validate_alert_form_fields(
            {"alert_action": "add", "alert_time": value}, "alert-1", 0,
        )

    assert _time("00:00").ok
    assert _time("23:59").ok
    assert _time("24:00").reason == "time"
    assert _time("23:60").reason == "time"
    assert _time("9:00").reason == "time", "must reject a non-zero-padded hour"
    assert _time("09:0").reason == "time", "must reject a non-zero-padded minute"
    assert _time("ab:00").reason == "time"
    assert _time("07:0a").reason == "time"
    assert _time("07-00").reason == "time", "must require the colon separator"
    assert _time("070:00").reason == "time"
    assert _time("07:000").reason == "time"
    assert _time("0700").reason == "time"
    assert _time("").reason == "time"
    assert _time(None).reason == "time", "missing alert_time must reject, not KeyError"
    assert _time(7).reason == "time", "non-string alert_time must reject, not TypeError"
    assert _time("-1:00").reason == "time"
    assert _time("07:-1").reason == "time"


def test_alert_form_validation_rejects_unknown_action_values():
    base = {"alert_time": "07:00"}
    assert validate_alert_form_fields(dict(base, alert_action="delete"), "alert-1", 0).reason == "action"
    assert validate_alert_form_fields(dict(base, alert_action="bogus"), "alert-1", 0).reason == "action"
    assert validate_alert_form_fields(base, "alert-1", 0).reason == "action", (
        "a missing alert_action must reject, not KeyError"
    )
    assert validate_alert_form_fields(dict(base, alert_action=""), "alert-1", 0).reason == "action"


def test_alert_form_validation_enabled_is_case_sensitive_and_typed():
    base = {"alert_action": "add", "alert_time": "07:00"}
    assert validate_alert_form_fields(dict(base, alert_enabled="On"), "alert-1", 0).reason == "enabled"
    assert validate_alert_form_fields(dict(base, alert_enabled="1"), "alert-1", 0).reason == "enabled"
    assert validate_alert_form_fields(dict(base, alert_enabled="true"), "alert-1", 0).reason == "enabled"
    assert validate_alert_form_fields(dict(base, alert_enabled=""), "alert-1", 0).reason == "enabled"
    # Omitted entirely (real unchecked-checkbox semantics) must be accepted as disabled.
    ok = validate_alert_form_fields(base, "alert-1", 0)
    assert ok.ok and ok.settings["enabled"] is False


def test_alert_form_validation_weekday_boundaries_and_unknown_index():
    base = {"alert_action": "add", "alert_time": "07:00"}
    all_days = validate_alert_form_fields(
        dict(base, **{"weekday_{}".format(i): "on" for i in range(7)}), "alert-1", 0,
    )
    assert all_days.ok and all_days.settings["weekdays"] == [0, 1, 2, 3, 4, 5, 6]
    # weekday_7 is outside the 0-6 range the editor renders, so it is simply
    # an unrecognized field name, not a recurrence-shaped rejection.
    assert validate_alert_form_fields(dict(base, weekday_7="on"), "alert-1", 0).reason == "fields"
    assert validate_alert_form_fields(dict(base, weekday_0="off"), "alert-1", 0).reason == "recurrence"
    assert validate_alert_form_fields(dict(base, weekday_0=""), "alert-1", 0).reason == "recurrence"


def test_alert_form_validation_add_ignores_alert_id_field():
    # alert_id is only in the allowlist for "edit"; on "add" it is unknown.
    fields = {"alert_action": "add", "alert_time": "07:00", "alert_id": "morning"}
    assert validate_alert_form_fields(fields, "alert-1", 0).reason == "fields"


def test_postpone_delay_validation_accepts_only_whole_minutes_1_to_60():
    assert validate_postpone_delay("1") == 1
    assert validate_postpone_delay("60") == 60
    for value in ("0", "61", "1.5", "", "abc", 15, True):
        assert validate_postpone_delay(value) is None
