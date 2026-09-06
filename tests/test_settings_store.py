"""Host tests for SettingsStore AD-3 persistence and recovery."""

import json

from src.device.settings_store import (
    COMMIT_RENAME_FAIL,
    COMMIT_SYNC_FAIL,
    COMMIT_VALIDATE_FAIL,
    COMMIT_WRITE_FAIL,
    SettingsCommitError,
    SettingsStore,
)
from src.provisioning.verifier import derive_admin_verifier, verify_admin_password


class FakeFS:
    """Minimal injectable filesystem for SettingsStore."""

    def __init__(self, files=None):
        self.files = {} if files is None else dict(files)
        self.sync_calls = 0
        self.rename_calls = []
        self.remove_calls = []
        self.fail_rename_from = None
        self.fail_write_path = None

    def open(self, path, mode="r"):
        fs = self
        if "w" in mode:
            if path == self.fail_write_path:
                raise OSError("write fail")

            class Writer:
                def __init__(self):
                    self.buf = bytearray()

                def write(self, data):
                    if isinstance(data, str):
                        data = data.encode("utf-8")
                    self.buf.extend(data)
                    return len(data)

                def flush(self):
                    return None

                def close(self):
                    fs.files[path] = bytes(self.buf)

                def __enter__(self):
                    return self

                def __exit__(self, *_exc):
                    self.close()
                    return False

            return Writer()

        if path not in self.files:
            raise OSError(2, "missing")

        class Reader:
            def __init__(self, data):
                self._data = data

            def read(self):
                return self._data

            def close(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                self.close()
                return False

        return Reader(self.files[path])

    def exists(self, path):
        return path in self.files

    def rename(self, src, dst):
        self.rename_calls.append((src, dst))
        if src == self.fail_rename_from:
            raise OSError("rename fail")
        if src not in self.files:
            raise OSError(2, "missing")
        self.files[dst] = self.files.pop(src)

    def remove(self, path):
        self.remove_calls.append(path)
        if path not in self.files:
            raise OSError(2, "missing")
        del self.files[path]

    def sync(self):
        self.sync_calls += 1

    def urandom(self, n):
        return b"\x5a" * n


def _store(fs, path=".settings-v1"):
    return SettingsStore(
        path=path,
        open_fn=fs.open,
        rename_fn=fs.rename,
        remove_fn=fs.remove,
        sync_fn=fs.sync,
        urandom_fn=fs.urandom,
        exists_fn=fs.exists,
    )


def _record_bytes(**overrides):
    salt, verifier = derive_admin_verifier("admin-pass", salt=b"\x01" * 16)
    record = {
        "settings_version": 1,
        "wifi_ssid": "ssid",
        "wifi_password": "password1",
        "admin_verifier_version": "pbkdf2-sha256-v1",
        "admin_salt": salt,
        "admin_verifier": verifier,
        "color_scheme": "forest-amber",
    }
    record.update(overrides)
    return json.dumps(record).encode("utf-8")


def test_absent_record_is_unconfigured():
    store = _store(FakeFS())
    assert store.load() is None
    assert store.is_configured() is False


def test_valid_current_wins():
    fs = FakeFS({".settings-v1": _record_bytes(wifi_ssid="current")})
    store = _store(fs)
    loaded = store.load()
    assert loaded["wifi_ssid"] == "current"
    assert store.is_configured() is True


def test_malformed_current_preserved_without_delete():
    fs = FakeFS({".settings-v1": b"{not-json"})
    store = _store(fs)
    assert store.load() is None
    assert fs.files[".settings-v1"] == b"{not-json"


def test_unsupported_current_preserved():
    fs = FakeFS({".settings-v1": _record_bytes(settings_version=2)})
    store = _store(fs)
    assert store.load() is None
    assert ".settings-v1" in fs.files


def test_absent_current_restores_valid_bak():
    fs = FakeFS({".settings-v1.bak": _record_bytes(wifi_ssid="from-bak")})
    store = _store(fs)
    loaded = store.load()
    assert loaded["wifi_ssid"] == "from-bak"
    assert ".settings-v1" in fs.files
    assert ".settings-v1.bak" not in fs.files


def test_invalid_current_quarantined_then_bak_restored():
    fs = FakeFS(
        {
            ".settings-v1": b"corrupt",
            ".settings-v1.bak": _record_bytes(wifi_ssid="bak-ssid"),
        }
    )
    store = _store(fs)
    loaded = store.load()
    assert loaded["wifi_ssid"] == "bak-ssid"
    assert fs.files[".settings-v1.rejected"] == b"corrupt"
    assert fs.files[".settings-v1"]


def test_occupied_quarantine_preserves_evidence_and_stays_unconfigured():
    fs = FakeFS(
        {
            ".settings-v1": b"bad-current",
            ".settings-v1.bak": _record_bytes(wifi_ssid="bak"),
            ".settings-v1.rejected": b"old-rejected",
        }
    )
    store = _store(fs)
    assert store.load() is None
    assert fs.files[".settings-v1"] == b"bad-current"
    assert ".settings-v1.bak" in fs.files
    assert fs.files[".settings-v1.rejected"] == b"old-rejected"


def test_commit_writes_verifier_not_plaintext_and_is_atomic():
    fs = FakeFS()
    store = _store(fs)
    settings = store.commit(
        wifi_ssid="home",
        wifi_password="password1",
        admin_password="admin-secret",
    )
    assert "admin-secret" not in fs.files[".settings-v1"].decode("utf-8")
    assert settings["admin_salt"]
    assert settings["admin_verifier"]
    assert verify_admin_password(
        "admin-secret", settings["admin_salt"], settings["admin_verifier"]
    )
    assert fs.sync_calls >= 2
    assert store.is_configured() is True


def test_commit_rotates_current_to_bak():
    fs = FakeFS({".settings-v1": _record_bytes(wifi_ssid="old")})
    store = _store(fs)
    store.commit(
        wifi_ssid="new",
        wifi_password="password1",
        admin_password="admin-secret",
    )
    assert json.loads(fs.files[".settings-v1"])["wifi_ssid"] == "new"
    assert json.loads(fs.files[".settings-v1.bak"])["wifi_ssid"] == "old"
    assert ".settings-v1.tmp" not in fs.files


def test_commit_mid_rename_failure_is_named_and_leaves_no_plaintext():
    fs = FakeFS({".settings-v1": _record_bytes(wifi_ssid="prior")})
    fs.fail_rename_from = ".settings-v1.tmp"
    store = _store(fs)
    try:
        store.commit(
            wifi_ssid="new",
            wifi_password="password1",
            admin_password="admin-secret",
        )
        assert False, "expected SettingsCommitError"
    except SettingsCommitError as exc:
        assert exc.code == COMMIT_RENAME_FAIL
    blob = b"".join(fs.files.values())
    assert b"admin-secret" not in blob


def test_commit_write_failure_is_named():
    fs = FakeFS()
    fs.fail_write_path = ".settings-v1.tmp"
    store = _store(fs)
    try:
        store.commit(
            wifi_ssid="new",
            wifi_password="password1",
            admin_password="admin-secret",
        )
        assert False, "expected SettingsCommitError"
    except SettingsCommitError as exc:
        assert exc.code == COMMIT_WRITE_FAIL


def test_commit_accepts_precomputed_verifier_for_tests():
    fs = FakeFS()
    store = _store(fs)
    salt, verifier = derive_admin_verifier("x", salt=b"\x02" * 16)
    settings = store.commit(
        wifi_ssid="ssid",
        wifi_password="password1",
        admin_salt_hex=salt,
        admin_verifier_hex=verifier,
    )
    assert settings["admin_salt"] == salt
    assert settings["admin_verifier"] == verifier


def test_commit_sync_failure_is_named_and_leaves_no_plaintext():
    fs = FakeFS()

    def boom_sync():
        raise OSError("sync fail")

    store = SettingsStore(
        path=".settings-v1",
        open_fn=fs.open,
        rename_fn=fs.rename,
        remove_fn=fs.remove,
        sync_fn=boom_sync,
        urandom_fn=fs.urandom,
        exists_fn=fs.exists,
    )
    try:
        store.commit(
            wifi_ssid="new",
            wifi_password="password1",
            admin_password="admin-secret",
        )
        assert False, "expected SettingsCommitError"
    except SettingsCommitError as exc:
        assert exc.code == COMMIT_SYNC_FAIL
    blob = b"".join(fs.files.values())
    assert b"admin-secret" not in blob


def test_commit_rejects_partial_salt_or_verifier():
    fs = FakeFS()
    store = _store(fs)
    salt, verifier = derive_admin_verifier("x", salt=b"\x02" * 16)
    try:
        store.commit(
            wifi_ssid="ssid",
            wifi_password="password1",
            admin_password="admin-secret",
            admin_salt_hex=salt,
        )
        assert False, "expected SettingsCommitError"
    except SettingsCommitError as exc:
        assert exc.code == COMMIT_VALIDATE_FAIL
    try:
        store.commit(
            wifi_ssid="ssid",
            wifi_password="password1",
            admin_password="admin-secret",
            admin_verifier_hex=verifier,
        )
        assert False, "expected SettingsCommitError"
    except SettingsCommitError as exc:
        assert exc.code == COMMIT_VALIDATE_FAIL
    assert ".settings-v1" not in fs.files
