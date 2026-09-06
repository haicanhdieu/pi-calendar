"""Host tests for Vietnamese lunar conversion and calendar purity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from src.calendar.lunar import gregorian_to_lunar

ROOT = Path(__file__).resolve().parents[1]
LUNAR_PATH = ROOT / "src" / "calendar" / "lunar.py"
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


def test_lunar_imports_under_cpython():
    from src.calendar import lunar

    assert callable(lunar.gregorian_to_lunar)


def test_lunar_module_does_not_import_device_or_micropython_apis():
    roots = _imported_roots(LUNAR_PATH)
    forbidden = roots & FORBIDDEN_IMPORT_ROOTS
    assert not forbidden, f"lunar.py imports forbidden modules: {forbidden}"
    assert "machine" not in sys.modules


@pytest.mark.parametrize(
    "year,month,day,lunar_day,lunar_month,is_leap",
    [
        # Inclusive supported-year bounds (module docstring)
        (1900, 1, 1, 1, 12, False),
        (2100, 12, 31, 1, 12, False),
        # Tet Ất Tỵ / Lunar New Year 2026
        (2026, 2, 17, 1, 1, False),
        # Ordinary mid-year date (Clock fixture day)
        (2026, 9, 6, 25, 7, False),
        # Non-leap neighbor immediately before leap month 6 of 2025
        (2025, 7, 24, 30, 6, False),
        # Leap month 6 of 2025 (Hồ Ngọc Đức / UTC+7)
        (2025, 7, 25, 1, 6, True),
        (2025, 8, 1, 8, 6, True),
        # 2004 leap month 2 (reference article example window)
        (2004, 3, 21, 1, 2, True),
    ],
)
def test_gregorian_to_lunar_vectors(
    year, month, day, lunar_day, lunar_month, is_leap
):
    assert gregorian_to_lunar(year, month, day) == (
        lunar_day,
        lunar_month,
        is_leap,
    )


def test_gregorian_to_lunar_rejects_out_of_range_years():
    with pytest.raises(ValueError):
        gregorian_to_lunar(1899, 12, 31)
    with pytest.raises(ValueError):
        gregorian_to_lunar(2101, 1, 1)
