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
    """Return whether a touch is in the lower 25% POSTPONE band."""
    top = height // 4
    middle = height // 2
    return y is not None and top + middle <= y < height


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
        display.draw_text(headline, x, max(0, (top - h) // 2), config.FONT_SETTINGS_STATUS, config.COLOR_PRIMARY)

        time_text = _two_digit(local.hour) + ":" + _two_digit(local.minute)
        x, h = _center(display, time_text, config.FONT_TIME)
        display.draw_text(time_text, x, max(0, top - h - 4), config.FONT_TIME, config.COLOR_PRIMARY)
        if count > 1:
            count_text = str(count) + " ALERTS"
            x, h = _center(display, count_text, config.FONT_SETTINGS_STATUS)
            display.draw_text(count_text, x, top - h - 2, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY)

        stop = "STOP"
        x, h = _center(display, stop, config.FONT_TIME)
        display.draw_text(stop, x, top + (middle - h) // 2, config.FONT_TIME, config.COLOR_PRIMARY)

        postpone = "POSTPONE " + str(int(postpone_minutes)) + " MIN"
        x, h = _center(display, postpone, config.FONT_SETTINGS_STATUS)
        display.draw_text(postpone, x, top + middle + (bottom - h) // 2, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY)
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
