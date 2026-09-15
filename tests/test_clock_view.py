"""Host tests for Clock view, DisplayPort, and UI purity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src import config
from src.calendar.gregorian import build_month_grid
from src.device.display.font import _CHARS
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED, DateTime, TimeSnapshot
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.components import (
    bar_gear_item_rect,
    bar_rect,
    badge_rect,
    draw_unsynced_badge,
    point_in_rect,
    settings_guideline_rect,
    settings_reboot_rect,
    settings_status_rect,
)
from src.ui.compositor import UiCompositor
from src.ui.settings_view import SettingsView
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


def _pack_rgb565(red, green, blue):
    """Independent RGB888→RGB565 packer (must not call config.rgb888_to_rgb565)."""
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def _local(hour=14, minute=7, second=32, weekday=5, day=6, month=9, year=2026):
    # weekday 5 = Saturday when Monday=0
    return DateTime(year, month, day, weekday, hour, minute, second)


def _snapshot(local, trust=TRUST_SYNCED):
    return TimeSnapshot(utc=local, local=local, trust=trust, sync_age_ms=0)


def _texts(ops):
    return [op for op in ops if op[0] == "draw_text"]


def _fills(ops):
    return [op for op in ops if op[0] == "fill_rect"]


def test_ui_modules_import_under_cpython():
    from src.ui import calendar_view, clock_view, components, compositor, display_port

    assert callable(clock_view.ClockView)
    assert callable(calendar_view.CalendarView)
    assert callable(compositor.UiCompositor)
    assert callable(components.draw_unsynced_badge)
    assert display_port.FakeDisplayPort is not None


def test_ui_modules_do_not_import_device_or_micropython_apis():
    for path in sorted(UI_DIR.glob("*.py")):
        roots = _imported_roots(path)
        forbidden = roots & FORBIDDEN_IMPORT_ROOTS
        assert not forbidden, f"{path.name} imports forbidden modules: {forbidden}"
    assert "machine" not in sys.modules


def test_adapter_does_not_import_ui():
    roots = _imported_roots(ROOT / "src" / "device" / "display" / "adapter.py")
    assert "src.ui" not in roots
    assert not any(r.startswith("src.ui.") for r in roots)


def test_fake_display_port_clips_half_open_rects():
    display = FakeDisplayPort(width=10, height=10)
    display.fill_rect(-2, -3, 5, 6, 0xABCD)
    assert display.ops == [("fill_rect", 0, 0, 3, 3, 0xABCD)]
    display.clear_ops()
    display.fill_rect(8, 8, 10, 10, 1)
    assert display.ops == [("fill_rect", 8, 8, 2, 2, 1)]


def test_synced_valid_local_draws_time_date_no_badge():
    display = FakeDisplayPort()
    view = ClockView(display)
    local = _local()
    view.render(_snapshot(local, TRUST_SYNCED))

    texts = _texts(display.ops)
    labels = [t[1] for t in texts]
    assert "14:07" in labels
    assert "32" in labels
    assert "Sat · Sep 6 2026" in labels
    assert "AL · 25/7" in labels
    assert config.BADGE_TEXT not in labels

    hhmm = next(t for t in texts if t[1] == "14:07")
    ss = next(t for t in texts if t[1] == "32")
    date = next(t for t in texts if t[1] == "Sat · Sep 6 2026")
    lunar = next(t for t in texts if t[1] == "AL · 25/7")
    assert hhmm[4] == config.FONT_TIME
    assert hhmm[5] == config.COLOR_PRIMARY
    assert ss[4] == config.FONT_SECONDS
    assert ss[5] == config.COLOR_SECONDARY
    assert date[4] == config.FONT_DATE
    assert date[5] == config.COLOR_SECONDARY
    assert lunar[4] == config.FONT_LUNAR
    assert lunar[5] == config.COLOR_LUNAR
    # SS sits to the right of HH:MM with fixed gap; HH:MM origin is left of SS.
    assert hhmm[2] < ss[2]
    assert ss[2] == hhmm[2] + display.measure_text("14:07", config.FONT_TIME)[0] + (
        config.CLOCK_SS_GAP_PX
    )
    # Today sits top-left, luna-today top-right, both flush at the same y.
    assert date[2] == config.CLOCK_CORNER_PAD_X_PX
    assert date[3] == config.CLOCK_CORNER_PAD_Y_PX
    assert lunar[3] == config.CLOCK_CORNER_PAD_Y_PX
    lunar_w, lunar_h = display.measure_text("AL · 25/7", config.FONT_LUNAR)
    assert lunar[2] == (
        config.SCREEN_WIDTH - lunar_w - config.CLOCK_CORNER_PAD_X_PX
    )

    hhmm_w, hhmm_h = display.measure_text("14:07", config.FONT_TIME)
    ss_w, ss_h = display.measure_text("00", config.FONT_SECONDS)
    row_w = hhmm_w + config.CLOCK_SS_GAP_PX + ss_w
    assert row_w <= config.SCREEN_WIDTH
    assert hhmm[2] == (config.SCREEN_WIDTH - row_w) // 2
    assert hhmm[2] >= 0
    assert hhmm[2] + row_w <= config.SCREEN_WIDTH
    # Clock centers between the corner band and the reserved events band.
    assert config.FONT_SCALE_TIME == 9
    date_h = display.measure_text("Sat · Sep 6 2026", config.FONT_DATE)[1]
    time_h = hhmm_h if hhmm_h >= ss_h else ss_h
    corner_row_h = date_h if date_h >= lunar_h else lunar_h
    band_bottom = (
        config.CLOCK_CORNER_PAD_Y_PX
        + corner_row_h
        + config.CLOCK_CORNER_CLOCK_GAP_PX
    )
    available_bottom = config.SCREEN_HEIGHT - config.CLOCK_EVENTS_BAND_H_PX
    assert hhmm[3] == band_bottom + (
        (available_bottom - band_bottom - time_h) // 2
    )
    assert hhmm[3] + time_h <= available_bottom


def test_lunar_corner_font_is_75_percent_of_date_corner_font():
    # Regression guard for the collision fix's follow-up: on-device the old
    # scale=1 (8px, 50% of date) read as too small; FONT_SCALE_LUNAR is now
    # the fractional 1.5 (12px) -- bigger than before, still smaller than
    # the date's 16px so the two corner strings stay visually distinct.
    display = FakeDisplayPort()
    assert config.FONT_SCALE_DATE == 2
    assert config.FONT_SCALE_LUNAR == 1.5
    date_h = display.measure_text("X", config.FONT_DATE)[1]
    lunar_h = display.measure_text("X", config.FONT_LUNAR)[1]
    assert date_h == 16
    assert lunar_h == 12
    assert lunar_h == round(date_h * 0.75)
    assert lunar_h > 8  # strictly bigger than the old scale=1 (8px)
    assert lunar_h < date_h  # still strictly smaller than the date text


def test_seconds_only_tick_dirties_ss_without_shifting_hhmm():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local(second=32), TRUST_SYNCED))
    hhmm_first = next(t for t in _texts(display.ops) if t[1] == "14:07")
    hhmm_origin = (hhmm_first[2], hhmm_first[3])
    lunar_first = next(t for t in _texts(display.ops) if t[4] == config.FONT_LUNAR)

    display.clear_ops()
    view.render(_snapshot(_local(second=33), TRUST_SYNCED))

    ops = display.ops
    assert all(op[0] in ("fill_rect", "draw_text") for op in ops)
    texts = _texts(ops)
    fills = _fills(ops)
    assert len(texts) == 1
    assert texts[0][1] == "33"
    assert texts[0][4] == config.FONT_SECONDS
    # Only the SS glyph box is cleared — not a full-screen fill.
    assert len(fills) == 1
    assert fills[0][3] < display.width  # w
    assert fills[0][4] < display.height  # h
    assert (
        "draw_text",
        "14:07",
        hhmm_origin[0],
        hhmm_origin[1],
        config.FONT_TIME,
        config.COLOR_PRIMARY,
    ) not in ops
    # Seconds-only path must not redraw or reformat lunar/date lines.
    assert not any(t[4] == config.FONT_LUNAR for t in texts)
    assert not any("Sep" in t[1] for t in texts)
    assert view._cache["lunar"] == lunar_first[1]


def test_cold_no_local_omits_gregorian_and_lunar_date_lines():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(
        TimeSnapshot(utc=None, local=None, trust=TRUST_UNSYNCED, sync_age_ms=None)
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert config.CLOCK_PLACEHOLDER_HHMM in labels
    assert not any(" · " in label and label.startswith(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")) for label in labels)
    assert not any(t[4] == config.FONT_LUNAR for t in _texts(display.ops))


def test_minute_rollover_full_redraws_hhmm():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local(minute=7, second=59), TRUST_SYNCED))
    display.clear_ops()
    view.render(_snapshot(_local(minute=8, second=0), TRUST_SYNCED))

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert "14:08" in labels
    assert "00" in labels
    assert "14:07" not in labels


def test_identical_rerender_is_noop():
    display = FakeDisplayPort()
    view = ClockView(display)
    snap = _snapshot(_local(), TRUST_SYNCED)
    view.render(snap)
    display.clear_ops()
    view.render(snap)
    assert display.ops == []


def test_cold_no_local_shows_placeholder_and_badge():
    display = FakeDisplayPort()
    view = ClockView(display)
    compositor = UiCompositor(display)
    compositor.render(
        view,
        TimeSnapshot(utc=None, local=None, trust=TRUST_UNSYNCED, sync_age_ms=None),
    )

    labels = [t[1] for t in _texts(display.ops)]
    assert config.CLOCK_PLACEHOLDER_HHMM in labels
    assert config.BADGE_TEXT in labels
    # No usable date line content required.
    assert not any("2026" in label for label in labels)
    assert not any(t[4] == config.FONT_LUNAR for t in _texts(display.ops))

    badge = next(t for t in _texts(display.ops) if t[1] == config.BADGE_TEXT)
    assert badge[4] == config.FONT_BADGE
    assert badge[5] == config.COLOR_BACKGROUND
    bx, by, bw, bh = badge_rect(display)
    assert badge[2] == bx + config.BADGE_PADDING_X
    assert by == config.BADGE_MARGIN_TOP
    assert bx + bw == display.width - config.BADGE_MARGIN_RIGHT
    assert (
        "fill_rect",
        bx,
        by,
        bw,
        bh,
        config.COLOR_UNSYNCED,
    ) in display.ops


def test_leap_lunar_month_draws_plus_suffix():
    display = FakeDisplayPort()
    view = ClockView(display)
    # 2025-07-25 → lunar 1/6 leap (Hồ Ngọc Đức)
    local = _local(year=2025, month=7, day=25, weekday=4)
    view.render(_snapshot(local, TRUST_SYNCED))
    labels = [t[1] for t in _texts(display.ops)]
    assert "AL · 1/6+" in labels
    lunar = next(t for t in _texts(display.ops) if t[1] == "AL · 1/6+")
    assert lunar[4] == config.FONT_LUNAR
    assert lunar[5] == config.COLOR_LUNAR


def test_day_change_full_redraws_lunar_line():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local(day=6, weekday=5), TRUST_SYNCED))
    assert "AL · 25/7" in [t[1] for t in _texts(display.ops)]

    display.clear_ops()
    # Next Gregorian day: Sunday 2026-09-07 → lunar 26/7
    view.render(_snapshot(_local(day=7, weekday=6), TRUST_SYNCED))

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert "AL · 26/7" in labels
    assert "AL · 25/7" not in labels
    assert "Sun · Sep 7 2026" in labels


def test_no_events_draws_nothing_in_band():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local()), events=None)
    band_top = display.height - config.CLOCK_EVENTS_BAND_H_PX
    for op in display.ops:
        if op[0] == "draw_text":
            _, _text, x, y, font, _color = op
            assert not (
                y >= band_top and font == config.FONT_SETTINGS_STATUS
            )

    display.clear_ops()
    view2 = ClockView(display)
    view2.render(_snapshot(_local()), events=[])
    band_top = display.height - config.CLOCK_EVENTS_BAND_H_PX
    for op in display.ops:
        if op[0] == "draw_text":
            _, _text, x, y, font, _color = op
            assert not (
                y >= band_top and font == config.FONT_SETTINGS_STATUS
            )


def test_one_event_draws_one_row_in_band():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local()), events=[("09:00", "Standup")])

    band_top = display.height - config.CLOCK_EVENTS_BAND_H_PX
    rows = [
        op
        for op in _texts(display.ops)
        if op[4] == config.FONT_SETTINGS_STATUS
    ]
    assert len(rows) == 1
    text, x, y, font, color = rows[0][1], rows[0][2], rows[0][3], rows[0][4], rows[0][5]
    assert text == "09:00  Standup"
    assert x == config.CLOCK_CORNER_PAD_X_PX
    assert y == band_top + config.CLOCK_EVENTS_ROW_TOP_PAD_PX
    assert color == config.COLOR_SECONDARY


def test_three_events_draw_three_rows_in_order():
    display = FakeDisplayPort()
    view = ClockView(display)
    events = [
        ("09:00", "Standup"),
        ("11:30", "Design review"),
        ("15:00", "1:1"),
    ]
    view.render(_snapshot(_local()), events=events)

    rows = [
        op
        for op in _texts(display.ops)
        if op[4] == config.FONT_SETTINGS_STATUS
    ]
    assert len(rows) == 3
    assert [r[1] for r in rows] == [
        "09:00  Standup",
        "11:30  Design review",
        "15:00  1:1",
    ]
    row_h = display.measure_text("Ag", config.FONT_SETTINGS_STATUS)[1]
    band_top = display.height - config.CLOCK_EVENTS_BAND_H_PX
    expected_y = band_top + config.CLOCK_EVENTS_ROW_TOP_PAD_PX
    for row in rows:
        assert row[3] == expected_y
        assert row[2] == config.CLOCK_CORNER_PAD_X_PX
        assert row[3] + row_h <= display.height
        expected_y += row_h + config.CLOCK_EVENTS_ROW_GAP_PX


def test_more_than_three_events_only_draws_first_three():
    display = FakeDisplayPort()
    view = ClockView(display)
    events = [
        ("09:00", "Standup"),
        ("11:30", "Design review"),
        ("15:00", "1:1"),
        ("18:00", "Dinner"),
    ]
    view.render(_snapshot(_local()), events=events)

    rows = [
        op
        for op in _texts(display.ops)
        if op[4] == config.FONT_SETTINGS_STATUS
    ]
    assert len(rows) == 3
    assert [r[1] for r in rows] == [
        "09:00  Standup",
        "11:30  Design review",
        "15:00  1:1",
    ]
    assert "18:00  Dinner" not in [r[1] for r in rows]


def test_long_title_is_truncated_within_band_right_edge():
    display = FakeDisplayPort()
    view = ClockView(display)
    long_title = "Quarterly Planning Offsite With Extended Leadership Team"
    view.render(_snapshot(_local()), events=[("09:00", long_title)])

    rows = [
        op
        for op in _texts(display.ops)
        if op[4] == config.FONT_SETTINGS_STATUS
    ]
    assert len(rows) == 1
    text = rows[0][1]
    x = rows[0][2]
    assert text.endswith("...")
    assert text != "09:00  " + long_title
    width, _height = display.measure_text(text, config.FONT_SETTINGS_STATUS)
    assert x + width <= config.CLOCK_EVENTS_ROW_RIGHT_PX


def test_events_unchanged_seconds_tick_keeps_ss_only_fast_path():
    display = FakeDisplayPort()
    view = ClockView(display)
    events = [("09:00", "Standup")]
    view.render(_snapshot(_local(second=32)), events=events)

    display.clear_ops()
    view.render(_snapshot(_local(second=33)), events=events)

    ops = display.ops
    texts = _texts(ops)
    assert len(texts) == 1
    assert texts[0][1] == "33"
    assert not any(op[4] == config.FONT_SETTINGS_STATUS for op in texts)
    fills = _fills(ops)
    assert len(fills) == 1
    assert not any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )


def test_events_changed_time_unchanged_triggers_full_redraw():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local()), events=None)

    display.clear_ops()
    view.render(_snapshot(_local()), events=[])

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )

    display.clear_ops()
    view.render(_snapshot(_local()), events=[("09:00", "Standup")])
    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert "09:00  Standup" in labels


def test_font_5x7_has_slash_and_plus_glyphs():
    assert "/" in _CHARS
    assert "+" in _CHARS


def test_unsynced_with_local_keeps_layout_and_draws_badge():
    display = FakeDisplayPort()
    synced = FakeDisplayPort()
    local = _local()

    UiCompositor(synced).render(ClockView(synced), _snapshot(local, TRUST_SYNCED))
    UiCompositor(display).render(ClockView(display), _snapshot(local, TRUST_UNSYNCED))

    synced_texts = {
        (t[1], t[2], t[3], t[4], t[5])
        for t in _texts(synced.ops)
        if t[1] != config.BADGE_TEXT
    }
    unsynced_texts = {
        (t[1], t[2], t[3], t[4], t[5])
        for t in _texts(display.ops)
        if t[1] != config.BADGE_TEXT
    }
    assert synced_texts == unsynced_texts
    assert any(t[1] == config.BADGE_TEXT for t in _texts(display.ops))
    bx, by, bw, bh = badge_rect(display)
    assert (
        "fill_rect",
        bx,
        by,
        bw,
        bh,
        config.COLOR_UNSYNCED,
    ) in display.ops


def test_synced_after_unsynced_drops_badge_and_full_invalidates():
    """Trust flip with a second change must invalidate, not take the SS-only path."""
    display = FakeDisplayPort()
    view = ClockView(display)
    compositor = UiCompositor(display)
    compositor.render(view, _snapshot(_local(second=32), TRUST_UNSYNCED))
    assert any(t[1] == config.BADGE_TEXT for t in _texts(display.ops))

    display.clear_ops()
    compositor.render(view, _snapshot(_local(second=33), TRUST_SYNCED))

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert config.BADGE_TEXT not in labels
    assert "14:07" in labels
    assert "33" in labels


def test_clock_view_alone_does_not_draw_badge():
    display = FakeDisplayPort()
    ClockView(display).render(
        TimeSnapshot(utc=None, local=None, trust=TRUST_UNSYNCED, sync_age_ms=None)
    )
    assert config.BADGE_TEXT not in [t[1] for t in _texts(display.ops)]


def test_draw_unsynced_badge_hidden_draws_nothing():
    display = FakeDisplayPort()
    draw_unsynced_badge(display, False)
    assert display.ops == []


def test_settings_layout_rects_match_specified_spacing():
    display = FakeDisplayPort()
    status_x, status_y, status_w, status_h = settings_status_rect(display)
    guide_x, guide_y, guide_w, guide_h = settings_guideline_rect(display)
    reboot_x, reboot_y, reboot_w, reboot_h = settings_reboot_rect(display)

    assert status_y == config.SETTINGS_TOP_PADDING_PX
    assert guide_y == status_y + status_h + config.SETTINGS_STATUS_GUIDELINE_GAP_PX
    assert reboot_y == guide_y + guide_h + config.SETTINGS_GUIDELINE_REBOOT_GAP_PX
    assert status_w == guide_w == reboot_w == display.width
    assert reboot_h == config.TAP_TARGET_SIZE_PX


def test_settings_view_tolerates_none_snapshot():
    display = FakeDisplayPort()
    view = SettingsView(display)
    view.render(None)
    assert any(
        op[0] == "fill_rect"
        and op[3] == display.width
        and op[4] == display.height
        for op in display.ops
    )


def test_settings_surface_suppresses_badge_and_bar():
    display = FakeDisplayPort()
    clock = ClockView(display)
    settings = SettingsView(display)
    compositor = UiCompositor(display)
    snapshot = _snapshot(_local(), TRUST_UNSYNCED)

    from src.ui.touch_state import SURFACE_BAR, SURFACE_SETTINGS

    compositor.render(
        clock,
        snapshot,
        active_surface=SURFACE_BAR,
        bar_elapsed_ms=config.BAR_SLIDE_DURATION_MS,
    )
    assert config.BADGE_TEXT in [op[1] for op in display.ops if op[0] == "draw_text"]

    display.clear_ops()
    compositor.render(settings, None, active_surface=SURFACE_SETTINGS)

    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert config.BADGE_TEXT not in texts
    bx, by, bw, bh = bar_rect(display)
    assert ("fill_rect", bx, by, bw, bh, config.COLOR_BAR_PANEL) not in display.ops
    assert (
        "fill_rect",
        0,
        0,
        display.width,
        display.height,
        config.COLOR_BACKGROUND,
    ) in display.ops
    reboot_x, reboot_y, reboot_w, reboot_h = settings_reboot_rect(display)
    assert (
        "fill_rect",
        reboot_x,
        reboot_y,
        reboot_w,
        reboot_h,
        config.COLOR_BAR_PANEL,
    ) in display.ops
    reboot_labels = [
        op[1]
        for op in display.ops
        if op[0] == "draw_text" and op[1] in config.SETTINGS_REBOOT_LABEL
    ]
    assert len(reboot_labels) == len(config.SETTINGS_REBOOT_LABEL)


def test_bar_is_a_bounded_draw_last_overlay_and_visibility_restores_base():
    display = FakeDisplayPort()
    view = ClockView(display)
    compositor = UiCompositor(display)
    snapshot = _snapshot(_local(), TRUST_SYNCED)

    compositor.render(
        view,
        snapshot,
        active_surface="bar",
        bar_elapsed_ms=config.BAR_SLIDE_DURATION_MS,
    )
    bx, by, bw, bh = bar_rect(display)
    panel = ("fill_rect", bx, by, bw, bh, config.COLOR_BAR_PANEL)
    assert panel in display.ops
    panel_index = display.ops.index(panel)
    assert all(op[0] == "fill_rect" for op in display.ops[panel_index + 1 :])
    assert all(
        not (op[0] == "fill_rect" and op[3] == display.width and op[4] == display.height and op[5] == config.COLOR_BAR_PANEL)
        for op in display.ops
    )
    ix, iy, iw, ih = bar_gear_item_rect(display)
    assert ix == (display.width - config.TAP_TARGET_SIZE_PX) // 2
    assert iy + ih // 2 == by + bh // 2
    assert iw == ih == config.TAP_TARGET_SIZE_PX

    display.clear_ops()
    compositor.render(view, snapshot, active_surface="rotation")
    assert (
        "fill_rect",
        0,
        display.height - config.BAR_HEIGHT_PX,
        display.width,
        config.BAR_HEIGHT_PX,
        config.COLOR_BACKGROUND,
    ) in display.ops


def test_bar_reverse_restores_only_uncovered_bottom_pixels():
    display = FakeDisplayPort()

    class BottomStripView:
        def __init__(self):
            self.valid = False
            self.invalidations = 0

        def invalidate(self):
            self.valid = False
            self.invalidations += 1

        def render(self, _snapshot):
            if not self.valid:
                display.fill_rect(
                    5,
                    display.height - config.BAR_HEIGHT_PX + 2,
                    10,
                    5,
                    config.COLOR_PRIMARY,
                )
                self.valid = True

    view = BottomStripView()
    compositor = UiCompositor(display)
    snapshot = _snapshot(_local(), TRUST_SYNCED)
    compositor.render(
        view,
        snapshot,
        active_surface="bar",
        bar_elapsed_ms=config.BAR_SLIDE_DURATION_MS,
    )

    display.clear_ops()
    compositor.render(
        view,
        snapshot,
        active_surface="rotation",
        bar_retract_elapsed_ms=config.BAR_SLIDE_DURATION_MS // 2,
    )
    reverse_height = config.BAR_HEIGHT_PX // 2
    restores = [op for op in _fills(display.ops) if op[5] == config.COLOR_BACKGROUND]
    assert restores == [
        (
            "fill_rect",
            0,
            display.height - config.BAR_HEIGHT_PX,
            display.width,
            config.BAR_HEIGHT_PX - reverse_height,
            config.COLOR_BACKGROUND,
        )
    ]
    assert view.invalidations == 1
    assert (
        "fill_rect",
        5,
        display.height - config.BAR_HEIGHT_PX + 2,
        10,
        5,
        config.COLOR_PRIMARY,
    ) in display.ops
    assert (
        "fill_rect",
        0,
        display.height - reverse_height,
        display.width,
        reverse_height,
        config.COLOR_BAR_PANEL,
    ) in display.ops
    assert not any(op[3] == display.width and op[4] == display.height for op in restores)


def test_bar_reverse_restores_cached_calendar_bottom_cells():
    display = FakeDisplayPort()
    view = CalendarView(display)
    compositor = UiCompositor(display)
    local = _local()
    grid = build_month_grid(
        local.year,
        local.month,
        local.year,
        local.month,
        local.day,
    )
    snapshot = _snapshot(local, TRUST_SYNCED)
    compositor.render(
        view,
        snapshot,
        grid,
        active_surface="bar",
        bar_elapsed_ms=config.BAR_SLIDE_DURATION_MS,
    )

    display.clear_ops()
    compositor.render(
        view,
        snapshot,
        grid,
        active_surface="rotation",
        bar_retract_elapsed_ms=config.BAR_SLIDE_DURATION_MS // 2,
        bar_retract_start_height=config.BAR_HEIGHT_PX,
    )
    reverse_height = config.BAR_HEIGHT_PX // 2
    strip_restores = [
        op
        for op in _fills(display.ops)
        if op[5] == config.COLOR_BACKGROUND
        and not (
            op[1] == 0
            and op[2] == 0
            and op[3] == display.width
            and op[4] == display.height
        )
    ]
    assert strip_restores == [
        (
            "fill_rect",
            0,
            display.height - config.BAR_HEIGHT_PX,
            display.width,
            config.BAR_HEIGHT_PX - reverse_height,
            config.COLOR_BACKGROUND,
        )
    ]
    labels = [t[1] for t in _texts(display.ops)]
    assert "30" in labels
    assert (
        "fill_rect",
        0,
        display.height - reverse_height,
        display.width,
        reverse_height,
        config.COLOR_BAR_PANEL,
    ) in display.ops


def test_bar_point_hit_testing_is_half_open_and_tolerates_bad_coordinates():
    display = FakeDisplayPort()
    rect = bar_gear_item_rect(display)
    assert point_in_rect(rect[0], rect[1], rect)
    assert not point_in_rect(rect[0] + rect[2], rect[1], rect)
    assert not point_in_rect(None, "bad", rect)
    assert not point_in_rect(float("inf"), 0, rect)


def test_palette_rgb565_matches_independent_packing():
    assert config.COLOR_BACKGROUND == _pack_rgb565(*config.COLOR_BACKGROUND_RGB)
    assert config.COLOR_PRIMARY == _pack_rgb565(*config.COLOR_PRIMARY_RGB)
    assert config.COLOR_SECONDARY == _pack_rgb565(*config.COLOR_SECONDARY_RGB)
    assert config.COLOR_UNSYNCED == _pack_rgb565(*config.COLOR_UNSYNCED_RGB)
    assert config.COLOR_BACKGROUND == 0x0841
    assert config.COLOR_PRIMARY == 0x3FEF
    assert config.COLOR_SECONDARY == 0xFD87
    assert config.COLOR_UNSYNCED == 0xFA69


def test_font_ids_are_stable_config_names():
    assert config.FONT_SCALES[config.FONT_TIME] == config.FONT_SCALE_TIME
    assert config.FONT_SCALES[config.FONT_SECONDS] == config.FONT_SCALE_SECONDS
    assert config.FONT_SCALES[config.FONT_DATE] == config.FONT_SCALE_DATE
    assert config.FONT_SCALES[config.FONT_BADGE] == config.FONT_SCALE_BADGE
    assert config.FONT_SCALES[config.FONT_MONTH] == config.FONT_SCALE_MONTH
    assert config.FONT_SCALES[config.FONT_WEEKDAY] == config.FONT_SCALE_WEEKDAY
    assert config.FONT_SCALES[config.FONT_DAY] == config.FONT_SCALE_DAY
