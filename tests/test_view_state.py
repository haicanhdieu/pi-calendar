"""Host tests for pure view-state rotation and rollover helpers."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src.time.model import DateTime, TimeSnapshot, TRUST_UNSYNCED
from src.ui.view_state import (
    VIEW_CALENDAR,
    VIEW_CLOCK,
    classify_local_rollover,
    next_view_after_dwell,
)

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device"}
)
VIEW_STATE_PATH = ROOT / "src" / "ui" / "view_state.py"


def _remember_module(roots: set[str], name: str) -> None:
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


def _local(year=2026, month=9, day=6):
    return DateTime(year, month, day, 6, 14, 0, 0)


def _snapshot(local):
    return TimeSnapshot(utc=None, local=local, trust=TRUST_UNSYNCED, sync_age_ms=None)


def test_view_state_imports_under_cpython():
    from src.ui import view_state

    assert view_state.VIEW_CLOCK == "clock"
    assert view_state.VIEW_CALENDAR == "calendar"
    assert "machine" not in sys.modules


def test_view_state_module_is_pure():
    roots = _imported_roots(VIEW_STATE_PATH)
    forbidden = roots & FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"view_state imports forbidden: {forbidden}"


def test_classify_local_rollover_none_when_missing_or_unchanged():
    local = _local()
    assert classify_local_rollover(None, local) is None
    assert classify_local_rollover((2026, 9, 6), None) is None
    assert classify_local_rollover((2026, 9, 6), local) is None


def test_classify_local_rollover_day_and_month():
    assert classify_local_rollover((2026, 9, 6), _local(day=7)) == "day"
    assert classify_local_rollover((2026, 9, 30), _local(month=10, day=1)) == "month"
    assert classify_local_rollover((2026, 12, 31), _local(2027, 1, 1)) == "month"


def test_next_view_after_dwell_gates_calendar_on_local():
    assert next_view_after_dwell(VIEW_CLOCK, _snapshot(_local())) == VIEW_CALENDAR
    assert next_view_after_dwell(VIEW_CLOCK, _snapshot(None)) == VIEW_CLOCK
    assert next_view_after_dwell(VIEW_CALENDAR, _snapshot(_local())) == VIEW_CLOCK
    assert next_view_after_dwell(VIEW_CALENDAR, _snapshot(None)) == VIEW_CLOCK
