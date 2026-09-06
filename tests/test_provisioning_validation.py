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
