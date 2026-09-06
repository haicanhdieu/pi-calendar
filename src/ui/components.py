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
