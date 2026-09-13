"""Shared status-layer drawing helpers (AD-12 seed)."""

from src import config


def badge_rect(display):
    """Return the fixed top-right badge fill rect (x, y, w, h), unclipped."""
    tw, th = display.measure_text(config.BADGE_TEXT, config.FONT_BADGE)
    w = tw + (2 * config.BADGE_PADDING_X)
    h = th + (2 * config.BADGE_PADDING_Y)
    x = display.width - config.BADGE_MARGIN_RIGHT - w
    y = config.BADGE_MARGIN_TOP
    return (x, y, w, h)


def draw_unsynced_badge(display, visible):
    """
    Draw the orange UNSYNCED badge at fixed top-right when visible.

    When hidden, draws nothing and reserves no layout space.
    """
    if not visible:
        return

    x, y, w, h = badge_rect(display)
    display.fill_rect(x, y, w, h, config.COLOR_UNSYNCED)
    text_x = x + config.BADGE_PADDING_X
    text_y = y + config.BADGE_PADDING_Y
    display.draw_text(
        config.BADGE_TEXT,
        text_x,
        text_y,
        config.FONT_BADGE,
        config.COLOR_BACKGROUND,
    )


def bar_rect(display, height=None):
    """Return the bottom-docked Bar rectangle (x, y, w, h)."""
    if height is None:
        height = config.BAR_HEIGHT_PX
    height = max(0, min(int(height), config.BAR_HEIGHT_PX, display.height))
    return (0, display.height - height, display.width, height)


def bar_gear_item_rect(display):
    """Return the centered generous hit geometry for the future gear item."""
    size = config.TAP_TARGET_SIZE_PX
    _x, bar_y, _w, bar_h = bar_rect(display)
    center_y = bar_y + bar_h // 2
    return (
        (display.width - size) // 2,
        center_y - size // 2,
        size,
        size,
    )


def settings_status_rect(display):
    """Return the Settings status region rect (x, y, w, h)."""
    y = config.SETTINGS_TOP_PADDING_PX
    return (0, y, display.width, config.TAP_TARGET_SIZE_PX)


def settings_guideline_rect(display):
    """Return the Settings guideline region rect (x, y, w, h)."""
    _x, status_y, _w, status_h = settings_status_rect(display)
    y = status_y + status_h + config.SETTINGS_STATUS_GUIDELINE_GAP_PX
    return (0, y, display.width, config.TAP_TARGET_SIZE_PX // 2)


def settings_reboot_rect(display):
    """Return the Settings reboot control region rect (x, y, w, h)."""
    _x, guide_y, _w, guide_h = settings_guideline_rect(display)
    y = guide_y + guide_h + config.SETTINGS_GUIDELINE_REBOOT_GAP_PX
    return (0, y, display.width, config.TAP_TARGET_SIZE_PX)


def point_in_rect(x, y, rect):
    """Return whether an integer point lies in the rect's half-open bounds.

    Invalid or absent samples are deliberately not hits: touch adapters are
    allowed to report an edge before they have a stable coordinate pair.
    """
    try:
        x = int(x)
        y = int(y)
        rx, ry, rw, rh = rect
    except (TypeError, ValueError, OverflowError):
        return False
    return rx <= x < rx + rw and ry <= y < ry + rh


def draw_bar(display, visible, height=None):
    """Draw the bounded Bar panel and its centered amber gear, draw-last only."""
    if not visible:
        return

    x, y, w, h = bar_rect(display, height)
    if h <= 0:
        return
    display.fill_rect(x, y, w, h, config.COLOR_BAR_PANEL)

    # Keep every gear pixel inside the revealed panel.  The icon appears once
    # the panel is fully revealed; the hit geometry remains available earlier.
    if h != config.BAR_HEIGHT_PX:
        return
    item_x, item_y, item_w, item_h = bar_gear_item_rect(display)
    cx = item_x + item_w // 2
    cy = item_y + item_h // 2
    color = config.COLOR_SECONDARY
    # Compact gear built exclusively from DisplayPort rectangles.
    display.fill_rect(cx - 6, cy - 2, 13, 5, color)
    display.fill_rect(cx - 2, cy - 6, 5, 13, color)
    display.fill_rect(cx - 4, cy - 4, 9, 9, color)
    display.fill_rect(cx - 1, cy - 1, 3, 3, config.COLOR_BAR_PANEL)
