"""Full-frame active-alert DisplayPort renderer."""

from src import config
from src.ui.components import draw_unsynced_badge


def _two_digit(value):
    value = int(value)
    return str(value) if value >= 10 else "0" + str(value)


def _center(display, text, font):
    width, height = display.measure_text(text, font)
    return (display.width - width) // 2, height


def postpone_hit(y, height):
    """Return whether a touch is inside the visible POSTPONE button."""
    top = height // 4
    middle = height // 2
    gap = config.ALERT_BUTTON_GAP_PX
    return y is not None and top + middle + gap <= y < height


def stop_hit(y, height):
    """Return whether a touch is inside the visible STOP button."""
    top = height // 4
    middle = height // 2
    gap = config.ALERT_BUTTON_GAP_PX
    return y is not None and top + gap <= y < top + middle - gap


class AlertView:
    """Flat 25/50/25 active-alert screen; no touch or hardware ownership."""

    def __init__(self, display):
        self._display = display

    def render(self, snapshot, local, postpone_minutes, count=1):
        display = self._display
        top = display.height // 4
        middle = display.height // 2
        bottom = display.height - top - middle
        display.fill_rect(0, 0, display.width, display.height, config.COLOR_BACKGROUND)

        headline = "ALERT"
        x, h = _center(display, headline, config.FONT_SETTINGS_STATUS)
        display.draw_text(headline, x, max(0, (top - h) // 2), config.FONT_SETTINGS_STATUS, config.COLOR_ALERT)

        time_text = _two_digit(local.hour) + ":" + _two_digit(local.minute)
        x, h = _center(display, time_text, config.FONT_TIME)
        display.draw_text(time_text, x, max(0, top - h - 4), config.FONT_TIME, config.COLOR_ALERT_TIME)
        if count > 1:
            count_text = str(count) + " ALERTS"
            x, h = _center(display, count_text, config.FONT_SETTINGS_STATUS)
            display.draw_text(count_text, x, top - h - 2, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY)

        stop = "STOP"
        gap = config.ALERT_BUTTON_GAP_PX
        stop_y = top + gap
        stop_height = middle - gap * 2
        display.fill_rect(0, stop_y, display.width, stop_height, config.COLOR_PRIMARY)
        x, h = _center(display, stop, config.FONT_TIME)
        display.draw_text(stop, x, stop_y + (stop_height - h) // 2, config.FONT_TIME, config.COLOR_BACKGROUND)

        postpone = "POSTPONE " + str(int(postpone_minutes)) + " MIN"
        postpone_y = top + middle + gap
        postpone_height = bottom - gap
        display.fill_rect(0, postpone_y, display.width, postpone_height, config.COLOR_SECONDARY)
        x, h = _center(display, postpone, config.FONT_SETTINGS_STATUS)
        display.draw_text(postpone, x, postpone_y + (postpone_height - h) // 2, config.FONT_SETTINGS_STATUS, config.COLOR_BACKGROUND)
        draw_unsynced_badge(display, snapshot.trust != "synced")

    def render_postponed(self, snapshot, due, count=1):
        display = self._display
        display.fill_rect(0, 0, display.width, display.height, config.COLOR_BACKGROUND)

        headline = "POSTPONED"
        x, h = _center(display, headline, config.FONT_SETTINGS_STATUS)
        display.draw_text(headline, x, display.height // 4, config.FONT_SETTINGS_STATUS, config.COLOR_PRIMARY)

        due_text = (
            "DUE {}-{}-{} {}:{}".format(
                due.year,
                _two_digit(due.month),
                _two_digit(due.day),
                _two_digit(due.hour),
                _two_digit(due.minute),
            )
        )
        x, h = _center(display, due_text, config.FONT_SETTINGS_STATUS)
        display.draw_text(due_text, x, display.height // 2 - h // 2, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY)
        if count > 1:
            count_text = str(count) + " ALERTS"
            x, h = _center(display, count_text, config.FONT_SETTINGS_STATUS)
            display.draw_text(count_text, x, display.height - h - 8, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY)
        draw_unsynced_badge(display, snapshot.trust != "synced")
