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
    """Return the left 48×48 Settings target in the bottom bar."""
    from src.ui.bar_controls import gear_rect

    return gear_rect(display)


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


def settings_reboot_item_rect(display):
    """Return generous hit geometry for the Settings reboot control."""
    return settings_reboot_rect(display)


def settings_mode_item_rect(display):
    _x, reboot_y, _w, _h = settings_reboot_rect(display)
    y = reboot_y - config.SETTINGS_MODE_REBOOT_GAP_PX - config.TAP_TARGET_SIZE_PX
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


def draw_bar(display, visible, height=None, pressed_target=None):
    """Draw the bounded bar and its Settings/Alerts icons, draw-last only."""
    if not visible:
        return

    x, y, w, h = bar_rect(display, height)
    if h <= 0:
        return
    display.fill_rect(x, y, w, h, config.COLOR_BAR_PANEL)

    # Icons appear once the panel is fully revealed; hit geometry is available
    # earlier so the reveal animation retains its existing behavior.
    if h != config.BAR_HEIGHT_PX:
        return
    from src.ui.bar_controls import draw_buttons

    draw_buttons(display, pressed_target)
