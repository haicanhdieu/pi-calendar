"""Host tests for Calendar view, UiCompositor badge layer, and UI purity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src import config
from src.calendar.gregorian import build_month_grid
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED, DateTime, TimeSnapshot
from src.ui.calendar_view import CalendarView
from src.ui.components import badge_rect
from src.ui.compositor import UiCompositor
from src.ui.display_port import FakeDisplayPort

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "src" / "ui"
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


def _local(day=6, month=9, year=2026, weekday=5):
    return DateTime(year, month, day, weekday, 14, 7, 32)


def _snapshot(local, trust=TRUST_SYNCED):
    return TimeSnapshot(utc=local, local=local, trust=trust, sync_age_ms=0)


def _grid_for(local):
    return build_month_grid(
        local.year, local.month, local.year, local.month, local.day
    )


def _texts(ops):
    return [op for op in ops if op[0] == "draw_text"]


def _fills(ops):
    return [op for op in ops if op[0] == "fill_rect"]


def _calendar_cell_geometry(display, grid):
    """Mirror CalendarView._full_redraw pad/gap/row math for host asserts."""
    content_x = config.CALENDAR_PAD_X
    content_y = config.CALENDAR_PAD_Y
    content_w = display.width - (2 * config.CALENDAR_PAD_X)
    content_h = display.height - (2 * config.CALENDAR_PAD_Y)
    label = (
        ("JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
         "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER")
        [grid.month - 1]
        + " "
        + str(grid.year)
    )
    _, label_h = display.measure_text(label, config.FONT_MONTH)
    header_y = content_y + label_h + config.CALENDAR_LABEL_GAP
    _, weekday_h = display.measure_text("M", config.FONT_WEEKDAY)
    cell_w = (content_w - (6 * config.CALENDAR_GAP)) // 7
    n_rows = len(grid.weeks)
    grid_top = header_y + weekday_h + config.CALENDAR_HEADER_GAP
    grid_h = content_y + content_h - grid_top
    cell_h = (grid_h - ((n_rows - 1) * config.CALENDAR_GAP)) // n_rows if n_rows else 0
    return content_x, cell_w, cell_h, grid_top


def _cell_rect(content_x, cell_w, cell_h, grid_top, row, col):
    x = content_x + col * (cell_w + config.CALENDAR_GAP)
    y = grid_top + row * (cell_h + config.CALENDAR_GAP)
    return x, y, cell_w, cell_h


def test_calendar_and_compositor_import_under_cpython():
    from src.ui import calendar_view, compositor

    assert callable(calendar_view.CalendarView)
    assert callable(compositor.UiCompositor)
    assert "machine" not in sys.modules


def test_new_ui_modules_do_not_import_device_or_micropython_apis():
    for name in ("calendar_view.py", "compositor.py"):
        path = UI_DIR / name
        roots = _imported_roots(path)
        forbidden = roots & FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{name} imports forbidden modules: {forbidden}"


def test_synced_calendar_draws_month_header_and_grid_without_badge():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local()
    grid = _grid_for(local)
    view.render(_snapshot(local, TRUST_SYNCED), grid)

    texts = _texts(display.ops)
    labels = [t[1] for t in texts]
    assert "SEPTEMBER 2026" in labels
    assert labels.count("M") >= 1
    assert "T" in labels
    assert "W" in labels
    assert "F" in labels
    assert "S" in labels
    assert "1" in labels
    assert "6" in labels
    assert "30" in labels
    assert config.BADGE_TEXT not in labels

    month = next(t for t in texts if t[1] == "SEPTEMBER 2026")
    assert month[4] == config.FONT_MONTH
    assert month[5] == config.COLOR_PRIMARY
    mw, _ = display.measure_text("SEPTEMBER 2026", config.FONT_MONTH)
    assert month[2] == config.CALENDAR_PAD_X + (
        (display.width - 2 * config.CALENDAR_PAD_X - mw) // 2
    )
    assert month[3] == config.CALENDAR_PAD_Y

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    assert not hasattr(display, "framebuffer")
    assert not hasattr(display, "pixels")


def test_weekday_header_is_monday_first_single_letters():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local()
    view.render(_snapshot(local), _grid_for(local))

    weekday_ops = [
        t for t in _texts(display.ops) if t[4] == config.FONT_WEEKDAY
    ]
    letters = [t[1] for t in weekday_ops]
    assert letters == ["M", "T", "W", "T", "F", "S", "S"]
    assert all(t[5] == config.COLOR_SECONDARY for t in weekday_ops)
    # Columns increase left-to-right within the padded content box.
    xs = [t[2] for t in weekday_ops]
    assert xs == sorted(xs)
    assert xs[0] >= config.CALENDAR_PAD_X


def test_today_cell_primary_fill_and_background_text():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local(day=6)
    grid = _grid_for(local)
    view.render(_snapshot(local), grid)

    today_row = today_col = None
    for row_i, week in enumerate(grid.weeks):
        for col, cell in enumerate(week):
            if cell.is_today:
                today_row, today_col = row_i, col
                break
        if today_row is not None:
            break
    assert today_row is not None

    content_x, cell_w, cell_h, grid_top = _calendar_cell_geometry(display, grid)
    cx, cy, cw, ch = _cell_rect(
        content_x, cell_w, cell_h, grid_top, today_row, today_col
    )
    assert (
        "fill_rect",
        cx,
        cy,
        cw,
        ch,
        config.COLOR_PRIMARY,
    ) in display.ops

    today_text = next(
        t
        for t in _texts(display.ops)
        if t[1] == "6" and t[4] == config.FONT_DAY and t[5] == config.COLOR_BACKGROUND
    )
    tw, th = display.measure_text("6", config.FONT_DAY)
    assert today_text[2] == cx + (cw - tw) // 2
    assert today_text[3] == cy + (ch - th) // 2


def test_in_month_primary_overflow_secondary():
    display = FakeDisplayPort()
    view = CalendarView(display)
    # Sep 2026 starts Tuesday → Monday cell is Aug 31 overflow.
    local = _local(day=6, month=9, year=2026)
    grid = _grid_for(local)
    view.render(_snapshot(local), grid)

    overflow = next(c for week in grid.weeks for c in week if not c.in_month)
    in_month = next(
        c for week in grid.weeks for c in week if c.in_month and not c.is_today
    )

    overflow_ops = [
        t
        for t in _texts(display.ops)
        if t[1] == str(overflow.day)
        and t[4] == config.FONT_DAY
        and t[5] == config.COLOR_SECONDARY
    ]
    in_month_ops = [
        t
        for t in _texts(display.ops)
        if t[1] == str(in_month.day)
        and t[4] == config.FONT_DAY
        and t[5] == config.COLOR_PRIMARY
    ]
    assert overflow_ops
    assert in_month_ops


def test_layout_uses_pad_and_gap_constants():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local()
    grid = _grid_for(local)
    view.render(_snapshot(local), grid)

    content_x, cell_w, _cell_h, _grid_top = _calendar_cell_geometry(display, grid)
    weekday_ops = [t for t in _texts(display.ops) if t[4] == config.FONT_WEEKDAY]
    assert len(weekday_ops) == 7
    for col in range(6):
        # Glyph x is centered in the cell; column slot advance is exact.
        left_cell_x = content_x + col * (cell_w + config.CALENDAR_GAP)
        right_cell_x = content_x + (col + 1) * (cell_w + config.CALENDAR_GAP)
        left_tw, _ = display.measure_text(weekday_ops[col][1], config.FONT_WEEKDAY)
        right_tw, _ = display.measure_text(
            weekday_ops[col + 1][1], config.FONT_WEEKDAY
        )
        assert weekday_ops[col][2] == left_cell_x + (cell_w - left_tw) // 2
        assert weekday_ops[col + 1][2] == right_cell_x + (cell_w - right_tw) // 2
        assert (right_cell_x - left_cell_x) == cell_w + config.CALENDAR_GAP


def test_unsynced_calendar_compositor_draws_badge_last():
    display = FakeDisplayPort()
    view = CalendarView(display)
    compositor = UiCompositor(display)
    local = _local()
    grid = _grid_for(local)

    compositor.render(view, _snapshot(local, TRUST_UNSYNCED), grid)

    texts = _texts(display.ops)
    assert "SEPTEMBER 2026" in [t[1] for t in texts]
    assert any(t[1] == config.BADGE_TEXT for t in texts)
    last_text = texts[-1]
    assert last_text[1] == config.BADGE_TEXT
    bx, by, bw, bh = badge_rect(display)
    assert (
        "fill_rect",
        bx,
        by,
        bw,
        bh,
        config.COLOR_UNSYNCED,
    ) in display.ops


def test_badge_hide_invalidates_base_and_restores_pixels():
    display = FakeDisplayPort()
    view = CalendarView(display)
    compositor = UiCompositor(display)
    local = _local()
    grid = _grid_for(local)

    compositor.render(view, _snapshot(local, TRUST_UNSYNCED), grid)
    assert any(t[1] == config.BADGE_TEXT for t in _texts(display.ops))

    display.clear_ops()
    compositor.render(view, _snapshot(local, TRUST_SYNCED), grid)

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert config.BADGE_TEXT not in labels
    assert "SEPTEMBER 2026" in labels


def test_calendar_invalidate_reenables_full_redraw():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local()
    grid = _grid_for(local)
    snap = _snapshot(local)

    view.render(snap, grid)
    display.clear_ops()
    view.render(snap, grid)
    assert display.ops == []

    view.invalidate()
    view.render(snap, grid)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in _fills(display.ops)
    )
    assert "SEPTEMBER 2026" in [t[1] for t in _texts(display.ops)]


def test_fake_display_records_ops_only_no_framebuffer():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local()
    view.render(_snapshot(local), _grid_for(local))
    assert isinstance(display.ops, list)
    assert all(op[0] in ("fill_rect", "draw_text") for op in display.ops)
    # No full 320×240×16 pixel buffer attribute on the fake.
    for name in ("framebuffer", "buffer", "pixels", "_fb", "_buf"):
        assert not hasattr(display, name)


def test_calendar_view_does_not_draw_badge_itself():
    display = FakeDisplayPort()
    view = CalendarView(display)
    local = _local()
    view.render(_snapshot(local, TRUST_UNSYNCED), _grid_for(local))
    assert config.BADGE_TEXT not in [t[1] for t in _texts(display.ops)]


def test_variable_week_row_count_from_grid():
    display = FakeDisplayPort()
    view = CalendarView(display)
    # Feb 2021: non-leap, starts Monday → 4 weeks.
    local = DateTime(2021, 2, 1, 0, 12, 0, 0)
    grid = build_month_grid(2021, 2, 2021, 2, 1)
    assert len(grid.weeks) == 4
    view.render(_snapshot(local), grid)
    day_ops = [t for t in _texts(display.ops) if t[4] == config.FONT_DAY]
    assert len(day_ops) == 28


def test_six_week_month_draws_forty_two_cells_with_positive_height():
    display = FakeDisplayPort()
    view = CalendarView(display)
    # May 2021 starts Saturday → 6 weeks (tight vertical budget).
    local = DateTime(2021, 5, 1, 5, 12, 0, 0)
    grid = build_month_grid(2021, 5, 2021, 5, 1)
    assert len(grid.weeks) == 6
    view.render(_snapshot(local), grid)

    day_ops = [t for t in _texts(display.ops) if t[4] == config.FONT_DAY]
    assert len(day_ops) == 42

    _content_x, _cell_w, cell_h, _grid_top = _calendar_cell_geometry(display, grid)
    assert cell_h > 0
