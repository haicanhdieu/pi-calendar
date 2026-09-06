"""Host tests for pure time snapshots and import purity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src.time.model import (
    TRUST_SYNCED,
    TRUST_UNSYNCED,
    DateTime,
    calendar_entry_allowed,
)
from src.time.service import make_snapshot, utc_to_local

ROOT = Path(__file__).resolve().parents[1]
PURE_TIME_MODULES = (
    ROOT / "src" / "time" / "model.py",
    ROOT / "src" / "time" / "service.py",
)
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device"}
)


def _remember_module(roots: set[str], name: str) -> None:
    """Record a module path and every dotted prefix (so src.device.foo hits src.device)."""
    if not name:
        return
    parts = name.split(".")
    for i in range(len(parts)):
        roots.add(".".join(parts[: i + 1]))


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _remember_module(roots, alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            _remember_module(roots, node.module)
            for alias in node.names:
                _remember_module(roots, f"{node.module}.{alias.name}")
    return roots


def test_pure_modules_import_under_cpython():
    from src.time import model, service

    assert model.TRUST_SYNCED == "synced"
    assert callable(service.make_snapshot)


def test_pure_modules_do_not_import_device_or_micropython_apis():
    for path in PURE_TIME_MODULES:
        roots = _imported_roots(path)
        forbidden = roots & FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{path.name} imports forbidden modules: {forbidden}"
        assert "machine" not in sys.modules


def test_valid_utc_to_local_preserves_trust_and_age():
    utc = DateTime(2026, 9, 6, 6, 10, 15, 30)  # Sunday
    snapshot = make_snapshot(utc, TRUST_SYNCED, 1_500)

    assert snapshot.utc == utc
    assert snapshot.local == DateTime(2026, 9, 6, 6, 17, 15, 30)
    assert snapshot.trust == TRUST_SYNCED
    assert snapshot.sync_age_ms == 1_500
    assert calendar_entry_allowed(snapshot) is True


def test_utc_near_day_boundary_advances_local_date_and_weekday():
    # Spec matrix cites 16:30; UTC+7 at 17:00 crosses local midnight.
    utc = DateTime(2026, 9, 6, 6, 17, 0, 0)  # Sunday 17:00 UTC
    local = utc_to_local(utc)

    assert local == DateTime(2026, 9, 7, 0, 0, 0, 0)  # Monday
    snapshot = make_snapshot(utc, TRUST_SYNCED, 0)
    assert snapshot.local == local
    assert calendar_entry_allowed(snapshot) is True


def test_utc_1630_stays_same_local_calendar_day():
    utc = DateTime(2026, 9, 6, 6, 16, 30, 0)
    assert utc_to_local(utc) == DateTime(2026, 9, 6, 6, 23, 30, 0)


def test_cold_boot_absent_snapshot_forbids_calendar():
    snapshot = make_snapshot(None, TRUST_SYNCED, 999)

    assert snapshot.utc is None
    assert snapshot.local is None
    assert snapshot.sync_age_ms is None
    assert snapshot.trust == TRUST_UNSYNCED
    assert calendar_entry_allowed(snapshot) is False


def test_unsynced_with_known_utc_derives_local_and_allows_calendar():
    utc = DateTime(2026, 3, 1, 6, 20, 0, 0)  # Sunday → local Monday after +7
    snapshot = make_snapshot(utc, TRUST_UNSYNCED, 60_000)

    assert snapshot.utc == utc
    assert snapshot.local == DateTime(2026, 3, 2, 0, 3, 0, 0)
    assert snapshot.trust == TRUST_UNSYNCED
    assert snapshot.sync_age_ms == 60_000
    assert calendar_entry_allowed(snapshot) is True


def test_month_and_year_rollover_on_offset():
    utc = DateTime(2025, 12, 31, 2, 20, 0, 0)  # Wednesday
    local = utc_to_local(utc)
    assert local == DateTime(2026, 1, 1, 3, 3, 0, 0)  # Thursday


def test_leap_day_rollover():
    utc = DateTime(2024, 2, 28, 2, 20, 0, 0)  # Wednesday
    local = utc_to_local(utc)
    assert local == DateTime(2024, 2, 29, 3, 3, 0, 0)  # Thursday


def test_non_leap_feb_rollover_to_march():
    utc = DateTime(2025, 2, 28, 4, 20, 0, 0)  # Friday
    local = utc_to_local(utc)
    assert local == DateTime(2025, 3, 1, 5, 3, 0, 0)  # Saturday
