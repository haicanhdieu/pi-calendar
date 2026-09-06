"""Host tests for wrap-safe tick helpers."""

from __future__ import annotations

import ast
from pathlib import Path

from src import ticks
from src.ticks import PERIOD, ticks_add, ticks_diff, ticks_ms

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device"}
)


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


def test_ticks_module_is_pure():
    roots = _imported_roots(ROOT / "src" / "ticks.py")
    forbidden = roots & FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"ticks.py imports forbidden modules: {forbidden}"


def test_ticks_ms_returns_masked_non_negative():
    value = ticks_ms()
    assert isinstance(value, int)
    assert 0 <= value < PERIOD


def test_ticks_add_wraps_at_period():
    assert ticks_add(PERIOD - 10, 15) == 5
    assert ticks_add(100, -30) == 70
    assert ticks_add(10, -20) == PERIOD - 10


def test_ticks_diff_signed_and_wrap_safe():
    assert ticks_diff(150, 100) == 50
    assert ticks_diff(100, 150) == -50
    # Across wrap: 5 is 15 ms after PERIOD-10
    assert ticks_diff(5, PERIOD - 10) == 15
    assert ticks_diff(PERIOD - 10, 5) == -15


def test_deadline_pattern_uses_add_and_diff():
    """Redraw/retry scheduling pattern: due when ticks_diff(deadline, now) <= 0."""
    now = 1_000_000
    deadline = ticks_add(now, 1000)
    assert ticks_diff(deadline, now) == 1000
    assert ticks_diff(deadline, ticks_add(now, 1000)) == 0
    assert ticks_diff(deadline, ticks_add(now, 1001)) == -1
