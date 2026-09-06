"""Host tests for opaque session table and base64url IDs."""

import ast
from pathlib import Path

from src.provisioning.session import (
    SESSION_ID_CHARS,
    SESSION_ID_LEN,
    SessionTable,
    decode_session_id,
    encode_session_id,
    session_ids_equal,
)
from tests.test_network_coordinator import FakeTicks

_ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN = frozenset({"machine", "network", "socket", "ntptime"})


def test_encode_decode_roundtrip_and_alphabet():
    raw = bytes(range(16))
    encoded = encode_session_id(raw)
    assert len(encoded) == SESSION_ID_CHARS
    assert decode_session_id(encoded) == raw
    for ch in encoded:
        assert ch.isalnum() or ch in "-_"

    zeros = encode_session_id(b"\x00" * 16)
    assert zeros == "A" * 22
    assert decode_session_id(zeros) == b"\x00" * 16


def test_decode_rejects_malformed():
    assert decode_session_id("") is None
    assert decode_session_id("short") is None
    assert decode_session_id("A" * 21) is None
    assert decode_session_id("A" * 23) is None
    assert decode_session_id("A" * 21 + "+") is None
    assert decode_session_id("A" * 21 + "/") is None
    assert decode_session_id(None) is None


def test_session_ids_equal_constant_path():
    raw = b"\x01" * 16
    a = encode_session_id(raw)
    b = encode_session_id(raw)
    assert session_ids_equal(a, b) is True
    assert session_ids_equal(a, encode_session_id(b"\x02" * 16)) is False
    assert session_ids_equal("bad", a) is False


def test_create_lookup_renew_expire_and_full():
    ticks = FakeTicks(1000)
    counter = {"n": 0}

    def urandom(n):
        assert n == SESSION_ID_LEN
        counter["n"] += 1
        return bytes([counter["n"]] * n)

    table = SessionTable(
        max_sessions=2, idle_ms=100, urandom=urandom, ticks_module=ticks
    )
    first = table.create(1000)
    second = table.create(1000)
    assert first and second and first != second
    assert table.create(1000) is None
    assert table.is_full(1000) is True

    assert table.lookup(first, 1000) is not None
    assert table.renew(first, 1050) is True
    # first deadline was 1100; renewed at 1050 → 1150
    ticks.now = 1120
    assert table.lookup(second, 1120) is None  # second expired at 1100
    assert table.lookup(first, 1120) is not None
    assert table.is_full(1120) is False
    third = table.create(1120)
    assert third is not None


def test_keep_only_retains_acting_and_renews():
    ticks = FakeTicks(1000)
    counter = {"n": 0}

    def urandom(n):
        counter["n"] += 1
        return bytes([counter["n"]] * n)

    table = SessionTable(
        max_sessions=4, idle_ms=100, urandom=urandom, ticks_module=ticks
    )
    first = table.create(1000)
    second = table.create(1000)
    third = table.create(1000)
    assert len(table) == 3

    assert table.keep_only(second, 1050) is True
    assert len(table) == 1
    assert table.lookup(first, 1050) is None
    assert table.lookup(third, 1050) is None
    kept = table.lookup(second, 1050)
    assert kept is not None
    # Renewed at 1050 → deadline 1150
    ticks.now = 1120
    assert table.lookup(second, 1120) is not None
    ticks.now = 1160
    assert table.lookup(second, 1160) is None


def test_keep_only_missing_id_clears_table():
    ticks = FakeTicks(0)
    table = SessionTable(
        max_sessions=2, idle_ms=100, urandom=lambda n: b"\x07" * n, ticks_module=ticks
    )
    table.create(0)
    assert table.keep_only("A" * 22, 0) is False
    assert len(table) == 0
    assert table.keep_only("not-a-valid-session-id!", 0) is False


def test_expire_wrap_safe():
    ticks = FakeTicks(FakeTicks.PERIOD - 50)
    table = SessionTable(
        max_sessions=1,
        idle_ms=100,
        urandom=lambda n: b"\x03" * n,
        ticks_module=ticks,
    )
    sid = table.create(ticks.now)
    assert table.lookup(sid, ticks.now) is not None
    # Advance past wrap: now = PERIOD - 50 + 120 → 70
    later = ticks.ticks_add(ticks.now, 120)
    assert table.lookup(sid, later) is None


def test_session_module_forbids_device_imports():
    source = (_ROOT / "src/provisioning/session.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in _FORBIDDEN
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0] not in _FORBIDDEN
