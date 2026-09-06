"""Host tests for Clock view, DisplayPort, and UI purity."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from src import config
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED, DateTime, TimeSnapshot
from src.ui.clock_view import ClockView
from src.ui.components import badge_rect, draw_unsynced_badge
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
    from src.ui import clock_view, components, display_port

    assert callable(clock_view.ClockView)
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
    assert config.BADGE_TEXT not in labels

    hhmm = next(t for t in texts if t[1] == "14:07")
    ss = next(t for t in texts if t[1] == "32")
    date = next(t for t in texts if t[1] == "Sat · Sep 6 2026")
    assert hhmm[4] == config.FONT_TIME
    assert hhmm[5] == config.COLOR_PRIMARY
    assert ss[4] == config.FONT_SECONDS
    assert ss[5] == config.COLOR_SECONDARY
    assert date[4] == config.FONT_DATE
    assert date[5] == config.COLOR_SECONDARY
    # SS sits to the right of HH:MM with fixed gap; HH:MM origin is left of SS.
    assert hhmm[2] < ss[2]
    assert ss[2] == hhmm[2] + display.measure_text("14:07", config.FONT_TIME)[0] + (
        config.CLOCK_SS_GAP_PX
    )

    hhmm_w, _ = display.measure_text("14:07", config.FONT_TIME)
    ss_w, _ = display.measure_text("00", config.FONT_SECONDS)
    row_w = hhmm_w + config.CLOCK_SS_GAP_PX + ss_w
    assert row_w <= config.SCREEN_WIDTH
    assert hhmm[2] == (config.SCREEN_WIDTH - row_w) // 2
    assert hhmm[2] >= 0
    assert hhmm[2] + row_w <= config.SCREEN_WIDTH


def test_seconds_only_tick_dirties_ss_without_shifting_hhmm():
    display = FakeDisplayPort()
    view = ClockView(display)
    view.render(_snapshot(_local(second=32), TRUST_SYNCED))
    hhmm_first = next(t for t in _texts(display.ops) if t[1] == "14:07")
    hhmm_origin = (hhmm_first[2], hhmm_first[3])

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
    view.render(
        TimeSnapshot(utc=None, local=None, trust=TRUST_UNSYNCED, sync_age_ms=None)
    )

    labels = [t[1] for t in _texts(display.ops)]
    assert config.CLOCK_PLACEHOLDER_HHMM in labels
    assert config.BADGE_TEXT in labels
    # No usable date line content required.
    assert not any("2026" in label for label in labels)

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


def test_unsynced_with_local_keeps_layout_and_draws_badge():
    display = FakeDisplayPort()
    synced = FakeDisplayPort()
    local = _local()

    ClockView(synced).render(_snapshot(local, TRUST_SYNCED))
    ClockView(display).render(_snapshot(local, TRUST_UNSYNCED))

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
    view.render(_snapshot(_local(second=32), TRUST_UNSYNCED))
    assert any(t[1] == config.BADGE_TEXT for t in _texts(display.ops))

    display.clear_ops()
    view.render(_snapshot(_local(second=33), TRUST_SYNCED))

    fills = _fills(display.ops)
    assert any(
        f[1] == 0 and f[2] == 0 and f[3] == display.width and f[4] == display.height
        for f in fills
    )
    labels = [t[1] for t in _texts(display.ops)]
    assert config.BADGE_TEXT not in labels
    assert "14:07" in labels
    assert "33" in labels


def test_draw_unsynced_badge_hidden_draws_nothing():
    display = FakeDisplayPort()
    draw_unsynced_badge(display, False)
    assert display.ops == []


def test_palette_rgb565_matches_independent_packing():
    assert config.COLOR_BACKGROUND == _pack_rgb565(*config.COLOR_BACKGROUND_RGB)
    assert config.COLOR_PRIMARY == _pack_rgb565(*config.COLOR_PRIMARY_RGB)
    assert config.COLOR_SECONDARY == _pack_rgb565(*config.COLOR_SECONDARY_RGB)
    assert config.COLOR_UNSYNCED == _pack_rgb565(*config.COLOR_UNSYNCED_RGB)
    assert config.COLOR_BACKGROUND == 0x00A0
    assert config.COLOR_PRIMARY == 0x3FEF
    assert config.COLOR_SECONDARY == 0x1B47
    assert config.COLOR_UNSYNCED == 0xFB47


def test_font_ids_are_stable_config_names():
    assert config.FONT_SCALES[config.FONT_TIME] == config.FONT_SCALE_TIME
    assert config.FONT_SCALES[config.FONT_SECONDS] == config.FONT_SCALE_SECONDS
    assert config.FONT_SCALES[config.FONT_DATE] == config.FONT_SCALE_DATE
    assert config.FONT_SCALES[config.FONT_BADGE] == config.FONT_SCALE_BADGE
