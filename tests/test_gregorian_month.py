"""Host tests for Gregorian month grid and calendar import purity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src.calendar.gregorian import (
    build_month_grid,
    days_in_month,
    weekday_from_ymd,
)
from src.calendar.models import (
    ALLOWED_ANNOTATION_KINDS,
    ANNOTATION_KIND_ORDER,
    CalendarAnnotation,
    DayCell,
    MonthGrid,
)

ROOT = Path(__file__).resolve().parents[1]
PURE_CALENDAR_MODULES = (
    ROOT / "src" / "calendar" / "__init__.py",
    ROOT / "src" / "calendar" / "models.py",
    ROOT / "src" / "calendar" / "gregorian.py",
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


def _flat_cells(grid: MonthGrid):
    cells = []
    for week in grid.weeks:
        assert len(week) == 7
        cells.extend(week)
    return cells


def test_pure_modules_import_under_cpython():
    from src.calendar import gregorian, models

    assert callable(gregorian.build_month_grid)
    assert models.ALLOWED_ANNOTATION_KINDS == ()
    assert models.ANNOTATION_KIND_ORDER == ()


def test_pure_modules_do_not_import_device_or_micropython_apis():
    for path in PURE_CALENDAR_MODULES:
        roots = _imported_roots(path)
        forbidden = roots & FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{path.name} imports forbidden modules: {forbidden}"
        assert "machine" not in sys.modules


def test_annotation_kind_ownership_surface_exists():
    assert isinstance(ALLOWED_ANNOTATION_KINDS, tuple)
    assert isinstance(ANNOTATION_KIND_ORDER, tuple)
    assert ALLOWED_ANNOTATION_KINDS == ()
    assert ANNOTATION_KIND_ORDER == ()
    ann = CalendarAnnotation("lunar-day", "15")
    assert ann.kind == "lunar-day"
    assert ann.value == "15"


def test_ordinary_month_september_2026():
    # 2026-09-01 is Tuesday (wd=1); today mid-month 2026-09-06 (Sunday).
    grid = build_month_grid(2026, 9, 2026, 9, 6)

    assert grid.year == 2026
    assert grid.month == 9
    assert all(len(week) == 7 for week in grid.weeks)

    cells = _flat_cells(grid)
    in_month = [c for c in cells if c.in_month]
    assert len(in_month) == 30
    assert in_month[0] == DayCell(2026, 9, 1, True, False, ())
    assert weekday_from_ymd(2026, 9, 1) == 1  # Tuesday

    # Week 0: Mon Aug 31, Tue Sep 1, …
    w0 = grid.weeks[0]
    assert w0[0] == DayCell(2026, 8, 31, False, False, ())
    assert w0[1] == DayCell(2026, 9, 1, True, False, ())

    today_cells = [c for c in cells if c.is_today]
    assert len(today_cells) == 1
    assert today_cells[0] == DayCell(2026, 9, 6, True, True, ())


def test_leap_february_2024():
    grid = build_month_grid(2024, 2, 2024, 2, 15)
    assert days_in_month(2024, 2) == 29

    cells = _flat_cells(grid)
    in_month = [c for c in cells if c.in_month]
    assert len(in_month) == 29
    assert in_month[-1].day == 29

    # Day after 29 must be March overflow.
    idx_29 = next(i for i, c in enumerate(cells) if c.in_month and c.day == 29)
    after = cells[idx_29 + 1]
    assert after == DayCell(2024, 3, 1, False, False, ())


def test_non_leap_february_2025():
    grid = build_month_grid(2025, 2, 2025, 2, 10)
    assert days_in_month(2025, 2) == 28

    cells = _flat_cells(grid)
    in_month = [c for c in cells if c.in_month]
    assert len(in_month) == 28
    assert all(c.day != 29 for c in cells if c.month == 2)


def test_century_leap_rule_in_days_in_month():
    assert days_in_month(1900, 2) == 28
    assert days_in_month(2000, 2) == 29


def test_january_prior_year_december_lead_in():
    # 2026-01-01 is Thursday (wd=3) → Mon–Wed are Dec 2025.
    assert weekday_from_ymd(2026, 1, 1) == 3
    grid = build_month_grid(2026, 1, 2026, 1, 15)
    w0 = grid.weeks[0]
    assert w0[0] == DayCell(2025, 12, 29, False, False, ())
    assert w0[1] == DayCell(2025, 12, 30, False, False, ())
    assert w0[2] == DayCell(2025, 12, 31, False, False, ())
    assert w0[3] == DayCell(2026, 1, 1, True, False, ())


def test_december_next_year_january_trail():
    # 2026-12-01 is Tuesday (wd=1); Dec 31 is Thursday → Fri–Sun are Jan 2027.
    assert weekday_from_ymd(2026, 12, 1) == 1
    grid = build_month_grid(2026, 12, 2026, 12, 15)
    cells = _flat_cells(grid)
    idx_31 = next(i for i, c in enumerate(cells) if c.in_month and c.day == 31)
    assert cells[idx_31 + 1] == DayCell(2027, 1, 1, False, False, ())
    assert cells[idx_31 + 2] == DayCell(2027, 1, 2, False, False, ())
    assert cells[idx_31 + 3] == DayCell(2027, 1, 3, False, False, ())


def test_overflow_cell_is_today():
    # View September with today = Aug 31 lead-in overflow.
    grid = build_month_grid(2026, 9, 2026, 8, 31)
    today_cells = [c for c in _flat_cells(grid) if c.is_today]
    assert len(today_cells) == 1
    assert today_cells[0] == DayCell(2026, 8, 31, False, True, ())


def test_month_starts_monday_no_lead_in():
    # 2026-06-01 is Monday.
    assert weekday_from_ymd(2026, 6, 1) == 0
    grid = build_month_grid(2026, 6, 2026, 6, 1)

    w0 = grid.weeks[0]
    assert w0[0] == DayCell(2026, 6, 1, True, True, ())
    assert all(c.in_month for c in w0[:1])
    # No prior-month lead-in before the 1st.
    assert w0[0].day == 1 and w0[0].in_month is True


def test_month_starts_sunday_six_lead_in():
    # 2026-02-01 is Sunday (wd=6) → six prior-month cells then the 1st.
    assert weekday_from_ymd(2026, 2, 1) == 6
    grid = build_month_grid(2026, 2, 2026, 2, 1)

    w0 = grid.weeks[0]
    lead = list(w0[:6])
    assert all(c.in_month is False for c in lead)
    assert all(c.month == 1 for c in lead)
    assert w0[6] == DayCell(2026, 2, 1, True, True, ())
    assert [c.day for c in lead] == [26, 27, 28, 29, 30, 31]


def test_adjacent_overflow_weeks_length_seven():
    grid = build_month_grid(2026, 9, 2026, 9, 6)
    for week in grid.weeks:
        assert len(week) == 7

    cells = _flat_cells(grid)
    assert len(cells) % 7 == 0
    trailing = [c for c in cells if not c.in_month and (c.month != 8 or c.year != 2026)]
    # September 2026 ends mid-week; trailing October overflow present.
    assert any(c.month == 10 and not c.in_month for c in cells)
    assert trailing


def test_today_identification_exactly_one_matching_cell():
    grid = build_month_grid(2026, 9, 2026, 9, 15)
    cells = _flat_cells(grid)
    today_cells = [c for c in cells if c.is_today]
    assert len(today_cells) == 1
    assert today_cells[0].year == 2026
    assert today_cells[0].month == 9
    assert today_cells[0].day == 15
    assert today_cells[0].in_month is True

    # Overflow cells for current-month build are not today.
    overflow = [c for c in cells if not c.in_month]
    assert all(c.is_today is False for c in overflow)


def test_every_cell_has_empty_ordered_annotations():
    grid = build_month_grid(2026, 9, 2026, 9, 6)
    for cell in _flat_cells(grid):
        assert cell.annotations == ()
        assert isinstance(cell.annotations, tuple)


def test_weekday_monday_zero_known_dates():
    assert weekday_from_ymd(2026, 9, 6) == 6  # Sunday
    assert weekday_from_ymd(2026, 9, 7) == 0  # Monday
    assert weekday_from_ymd(2024, 2, 29) == 3  # Thursday (leap)
    assert weekday_from_ymd(2000, 2, 29) == 1  # Tuesday (divisible by 400)
    assert weekday_from_ymd(1900, 2, 28) == 2  # Wednesday (non-leap century)
