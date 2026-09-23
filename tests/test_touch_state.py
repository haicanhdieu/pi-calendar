"""Host tests for pure Rotation/Bar touch-surface transitions."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src import ticks
from src.config import TOUCH_IDLE_TIMEOUT_MS
from src.ui.touch_state import (
    BAR_TARGET_GEAR,
    BAR_TARGET_IN_PANEL,
    BAR_TARGET_OUTSIDE,
    SETTINGS_TARGET_REBOOT,
    SURFACE_BAR,
    SURFACE_ROTATION,
    SURFACE_SETTINGS,
    next_surface,
)

ROOT = Path(__file__).resolve().parents[1]
TOUCH_STATE_PATH = ROOT / "src" / "ui" / "touch_state.py"
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"machine", "network", "ntptime", "src.device"}
)


def _remember_module(roots: set[str], name: str) -> None:
    if not name:
        return
    parts = name.split(".")
    for index in range(len(parts)):
        roots.add(".".join(parts[: index + 1]))


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


def test_touch_state_imports_under_cpython():
    from src.ui import touch_state

    assert touch_state.SURFACE_ROTATION == "rotation"
    assert touch_state.SURFACE_BAR == "bar"
    assert touch_state.SURFACE_SETTINGS == "settings"
    assert "machine" not in sys.modules


def test_touch_state_module_is_pure():
    forbidden = _imported_roots(TOUCH_STATE_PATH) & FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"touch_state imports forbidden: {forbidden}"


def test_rotation_edge_reveals_bar_with_a_fresh_deadline():
    now = 12_345

    assert next_surface(SURFACE_ROTATION, None, True, now) == (
        SURFACE_BAR,
        ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS),
    )


def test_rotation_without_an_edge_is_a_noop():
    assert next_surface(SURFACE_ROTATION, None, False, 12_345) == (
        SURFACE_ROTATION,
        None,
    )


def test_bar_expires_when_its_deadline_is_due():
    now = 12_345

    assert next_surface(SURFACE_BAR, now, False, now) == (SURFACE_ROTATION, None)


def test_bar_retains_its_exact_future_deadline_without_an_edge():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(SURFACE_BAR, deadline, False, now) == (SURFACE_BAR, deadline)


def test_bar_routes_gear_edge_to_settings_and_outside_edges_to_rotation():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(SURFACE_BAR, deadline, True, now, BAR_TARGET_GEAR) == (
        SURFACE_SETTINGS,
        ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS),
    )
    assert next_surface(SURFACE_BAR, deadline, True, now, BAR_TARGET_OUTSIDE) == (
        SURFACE_ROTATION,
        None,
    )


def test_bar_in_panel_edge_stays_on_bar():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(SURFACE_BAR, deadline, True, now, BAR_TARGET_IN_PANEL) == (
        SURFACE_BAR,
        deadline,
    )


def test_bar_malformed_edge_stays_on_bar():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(SURFACE_BAR, deadline, True, now, None) == (
        SURFACE_BAR,
        deadline,
    )


def test_gear_edge_wins_when_bar_deadline_is_due():
    now = 12_345

    assert next_surface(SURFACE_BAR, now, True, now, BAR_TARGET_GEAR) == (
        SURFACE_SETTINGS,
        ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS),
    )


def test_bar_deadline_uses_wrap_safe_tick_comparison():
    now = ticks.PERIOD - 10
    future_deadline = ticks.ticks_add(now, 20)

    assert next_surface(SURFACE_BAR, future_deadline, False, now) == (
        SURFACE_BAR,
        future_deadline,
    )
    assert next_surface(SURFACE_BAR, future_deadline, False, future_deadline) == (
        SURFACE_ROTATION,
        None,
    )


def test_settings_expires_when_its_deadline_is_due():
    now = 12_345

    assert next_surface(SURFACE_SETTINGS, now, False, now) == (SURFACE_ROTATION, None)


def test_settings_outside_edge_returns_to_rotation():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(SURFACE_SETTINGS, deadline, True, now) == (
        SURFACE_ROTATION,
        None,
    )


def test_settings_reboot_edge_wins_when_settings_deadline_is_due():
    now = 12_345

    assert next_surface(
        SURFACE_SETTINGS, now, True, now, settings_target=SETTINGS_TARGET_REBOOT
    ) == (SURFACE_SETTINGS, now)


def test_settings_reboot_edge_stays_on_settings_without_renewing_deadline():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(
        SURFACE_SETTINGS, deadline, True, now, settings_target=SETTINGS_TARGET_REBOOT
    ) == (SURFACE_SETTINGS, deadline)


def test_settings_mode_edge_stays_on_settings_without_renewing_deadline():
    from src.ui.touch_state import SETTINGS_TARGET_MODE

    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)
    assert next_surface(
        SURFACE_SETTINGS, deadline, True, now, settings_target=SETTINGS_TARGET_MODE
    ) == (SURFACE_SETTINGS, deadline)


def test_settings_retains_its_exact_future_deadline_without_an_edge():
    now = 12_345
    deadline = ticks.ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)

    assert next_surface(SURFACE_SETTINGS, deadline, False, now) == (
        SURFACE_SETTINGS,
        deadline,
    )


def test_settings_deadline_uses_wrap_safe_tick_comparison():
    now = ticks.PERIOD - 10
    future_deadline = ticks.ticks_add(now, 20)

    assert next_surface(SURFACE_SETTINGS, future_deadline, False, now) == (
        SURFACE_SETTINGS,
        future_deadline,
    )
    assert next_surface(SURFACE_SETTINGS, future_deadline, False, future_deadline) == (
        SURFACE_ROTATION,
        None,
    )
