"""Host tests for credentials soft-check."""

from __future__ import annotations

import sys
import types

from src.credentials import credentials_valid


def _install_secrets(ssid, password):
    mod = types.ModuleType("secrets")
    mod.WIFI_SSID = ssid
    mod.WIFI_PASSWORD = password
    sys.modules["secrets"] = mod
    return mod


def _clear_secrets():
    sys.modules.pop("secrets", None)


def test_missing_secrets_module_is_invalid():
    _clear_secrets()
    # Ensure import fails even if a real secrets package exists on host.
    sys.modules["secrets"] = None  # type: ignore[assignment]
    try:
        assert credentials_valid() is False
    finally:
        _clear_secrets()


def test_empty_ssid_is_invalid():
    _clear_secrets()
    _install_secrets("", "password")
    try:
        assert credentials_valid() is False
    finally:
        _clear_secrets()


def test_whitespace_password_is_invalid():
    _clear_secrets()
    _install_secrets("home-wifi", "   ")
    try:
        assert credentials_valid() is False
    finally:
        _clear_secrets()


def test_nonempty_ssid_and_password_are_valid():
    _clear_secrets()
    _install_secrets("home-wifi", "s3cret")
    try:
        assert credentials_valid() is True
    finally:
        _clear_secrets()


def test_import_failure_other_than_import_error_is_invalid():
    _clear_secrets()

    class _Boom(types.ModuleType):
        def __getattr__(self, name):
            raise RuntimeError("broken secrets")

    sys.modules["secrets"] = _Boom("secrets")
    try:
        assert credentials_valid() is False
    finally:
        _clear_secrets()
