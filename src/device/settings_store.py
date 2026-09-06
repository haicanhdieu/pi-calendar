"""Sole FS boundary for the ignored version-1 device settings record (AD-3)."""

import json

from src import config
from src.provisioning.validation import (
    COLOR_SCHEME_V1,
    SETTINGS_VERSION,
    validate_settings_json,
)
from src.provisioning.verifier import (
    ADMIN_VERIFIER_VERSION,
    derive_admin_verifier,
)

SETTINGS_BASENAME = config.SETTINGS_BASENAME
COMMIT_OK = "ok"
COMMIT_VALIDATE_FAIL = "validate_fail"
COMMIT_WRITE_FAIL = "write_fail"
COMMIT_SYNC_FAIL = "sync_fail"
COMMIT_RENAME_FAIL = "rename_fail"
COMMIT_REMOVE_FAIL = "remove_fail"


class SettingsCommitError(Exception):
    """Named failure during atomic settings commit (no plaintext Admin)."""

    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)


class SettingsStore:
    """
    Read/validate/commit the device-local ``.settings-v1`` record.

    Inject open/replace/rename/remove/sync/urandom for host tests. Invalid or
    unsupported records are preserved and treated as unconfigured.
    """

    def __init__(
        self,
        path=SETTINGS_BASENAME,
        open_fn=None,
        rename_fn=None,
        remove_fn=None,
        sync_fn=None,
        urandom_fn=None,
        exists_fn=None,
    ):
        import os

        self._path = path
        self._tmp = path + ".tmp"
        self._bak = path + ".bak"
        self._rejected = path + ".rejected"
        self._open = open_fn if open_fn is not None else open
        self._rename = rename_fn if rename_fn is not None else os.rename
        self._remove = remove_fn if remove_fn is not None else os.remove
        self._sync = sync_fn if sync_fn is not None else getattr(os, "sync", None)
        self._urandom = urandom_fn if urandom_fn is not None else os.urandom
        self._exists = exists_fn if exists_fn is not None else self._default_exists
        self._cached = None
        self._loaded = False

    def _default_exists(self, path):
        try:
            self._open(path, "rb").close()
            return True
        except OSError:
            return False

    def _read_bytes(self, path):
        try:
            with self._open(path, "rb") as handle:
                return handle.read()
        except OSError:
            return None
        except Exception:
            return None

    def _validate_path(self, path):
        raw = self._read_bytes(path)
        if raw is None:
            return None
        result = validate_settings_json(raw)
        if result.ok:
            return result.settings
        return None

    def _call_sync(self):
        sync = self._sync
        if sync is None:
            return
        try:
            sync()
        except Exception as exc:
            raise SettingsCommitError(COMMIT_SYNC_FAIL, str(exc)) from exc

    def _safe_remove(self, path):
        if not self._exists(path):
            return
        try:
            self._remove(path)
        except OSError as exc:
            raise SettingsCommitError(COMMIT_REMOVE_FAIL, str(exc)) from exc

    def _restore_bak_to_current(self):
        try:
            self._rename(self._bak, self._path)
        except OSError:
            return False
        try:
            self._call_sync()
        except SettingsCommitError:
            # Rename already placed a valid current on disk; treat as restored.
            if self._validate_path(self._path) is not None:
                return True
            return False
        return True

    def load(self):
        """
        Boot-time load with AD-3 restore/quarantine.

        Returns the canonical settings dict, or None when unconfigured.
        Never deletes an invalid current record except via empty-only quarantine
        before a valid backup restore.
        """
        if self._loaded:
            return self._cached

        current_raw = self._read_bytes(self._path)
        current_exists = current_raw is not None
        current_settings = None
        if current_exists:
            result = validate_settings_json(current_raw)
            if result.ok:
                current_settings = result.settings

        if current_settings is not None:
            self._cached = current_settings
            self._loaded = True
            return self._cached

        bak_settings = self._validate_path(self._bak)

        if not current_exists:
            if bak_settings is not None:
                if self._restore_bak_to_current():
                    self._cached = bak_settings
                    self._loaded = True
                    return self._cached
            self._cached = None
            self._loaded = True
            return None

        # Current present but invalid/unsupported/incomplete.
        if bak_settings is None:
            self._cached = None
            self._loaded = True
            return None

        if self._exists(self._rejected):
            # Occupied quarantine: preserve evidence, enter setup.
            self._cached = None
            self._loaded = True
            return None

        try:
            self._rename(self._path, self._rejected)
            self._call_sync()
            if not self._restore_bak_to_current():
                self._cached = None
                self._loaded = True
                return None
        except (OSError, SettingsCommitError):
            self._cached = None
            self._loaded = True
            return None

        self._cached = bak_settings
        self._loaded = True
        return self._cached

    def is_configured(self):
        """True when boot load yields a valid complete record."""
        return self.load() is not None

    def commit(
        self,
        wifi_ssid,
        wifi_password,
        admin_password=None,
        admin_salt_hex=None,
        admin_verifier_hex=None,
        color_scheme=COLOR_SCHEME_V1,
    ):
        """
        Atomically persist a complete version-1 record.

        Accepts Admin plaintext (derived here) or a precomputed salt/verifier
        pair for tests. Never writes plaintext Admin to disk.
        """
        salt_given = admin_salt_hex is not None
        verifier_given = admin_verifier_hex is not None
        if salt_given != verifier_given:
            raise SettingsCommitError(
                COMMIT_VALIDATE_FAIL, "salt and verifier required together"
            )
        if not salt_given:
            if admin_password is None:
                raise SettingsCommitError(COMMIT_VALIDATE_FAIL, "missing admin")
            admin_salt_hex, admin_verifier_hex = derive_admin_verifier(
                admin_password, urandom=self._urandom
            )
        # Drop any reference to plaintext as soon as verifier exists.
        admin_password = None

        record = {
            "settings_version": SETTINGS_VERSION,
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
            "admin_verifier_version": ADMIN_VERIFIER_VERSION,
            "admin_salt": admin_salt_hex,
            "admin_verifier": admin_verifier_hex,
            "color_scheme": color_scheme,
        }
        check = validate_settings_json(json.dumps(record))
        if not check.ok:
            raise SettingsCommitError(COMMIT_VALIDATE_FAIL, check.reason)

        payload = json.dumps(check.settings)
        try:
            with self._open(self._tmp, "wb") as handle:
                data = payload.encode("utf-8")
                handle.write(data)
                try:
                    handle.flush()
                except Exception:
                    pass
        except OSError as exc:
            raise SettingsCommitError(COMMIT_WRITE_FAIL, str(exc)) from exc

        self._call_sync()
        self._safe_remove(self._bak)

        if self._exists(self._path):
            try:
                self._rename(self._path, self._bak)
            except OSError as exc:
                raise SettingsCommitError(COMMIT_RENAME_FAIL, str(exc)) from exc

        try:
            self._rename(self._tmp, self._path)
        except OSError as exc:
            raise SettingsCommitError(COMMIT_RENAME_FAIL, str(exc)) from exc

        self._call_sync()
        self._cached = check.settings
        self._loaded = True
        return check.settings
