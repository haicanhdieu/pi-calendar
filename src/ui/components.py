"""Shared status-layer drawing helpers (AD-12 seed)."""

from src import config

_OVERLAY_SETUP = "setup"
_OVERLAY_STATION_IP = "station_ip"

# Bottom-left network status strip (draw-last after base + UNSYNCED badge).
_STATUS_MARGIN_LEFT = 8
_STATUS_MARGIN_BOTTOM = 8
_STATUS_LINE_GAP = 2


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


def draw_network_status_overlay(display, status):
    """
    Draw Setup SSID+gateway continuously, or station IPv4 after connect.

    ``status`` is ``None`` or a dict with ``kind`` / ``ssid`` / ``ip``.
    Coordinator never calls this — App owns the overlay via compositor.
    """
    if not status:
        return
    kind = status.get("kind")
    if kind == _OVERLAY_SETUP:
        line1 = status.get("ssid") or config.SETUP_AP_SSID
        line2 = status.get("ip") or config.SETUP_AP_GATEWAY
        _draw_status_lines(display, line1, line2)
        return
    if kind == _OVERLAY_STATION_IP:
        ip = status.get("ip")
        if not ip:
            return
        _draw_status_lines(display, str(ip), None)


def _draw_status_lines(display, line1, line2):
    font = config.FONT_BADGE
    color = config.COLOR_PRIMARY
    _, th = display.measure_text("Ag", font)
    lines = [line1] if line2 is None else [line1, line2]
    total_h = len(lines) * th + (len(lines) - 1) * _STATUS_LINE_GAP
    y = display.height - _STATUS_MARGIN_BOTTOM - total_h
    x = _STATUS_MARGIN_LEFT
    for text in lines:
        if text is None:
            continue
        display.draw_text(str(text), x, y, font, color)
        y += th + _STATUS_LINE_GAP
