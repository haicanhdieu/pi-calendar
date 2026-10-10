"""Full-screen, read-only alert list with per-alert enabled controls."""

from src import config
from src.ui.components import point_in_rect

HEADER_HEIGHT = 23
ROW_HEIGHT = 21
STATE_WIDTH = 48
STATE_X = 264
_WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def state_rect(display, index):
    return (STATE_X, HEADER_HEIGHT + int(index) * ROW_HEIGHT, STATE_WIDTH, ROW_HEIGHT)


def state_index(display, alerts, x, y):
    """Return the touched alert index, or None outside a state control."""
    for index in range(min(10, len(alerts))):
        if point_in_rect(x, y, state_rect(display, index)):
            return index
    return None


def handle_touch(app, x, y):
    """Apply a state-control touch and report (control_hit, valid_point)."""
    settings = app._alert_cfg[2]
    alerts = settings.get("alerts", []) if isinstance(settings, dict) else []
    index = state_index(app._view._display, alerts, x, y)
    if index is not None:
        from src.alert.runtime import toggle_enabled

        toggle_enabled(app, alerts[index].get("id"))
        return True, True
    try:
        int(x)
        int(y)
        return False, True
    except (TypeError, ValueError, OverflowError):
        return False, False


def recurrence_text(alert):
    weekdays = alert.get("weekdays") or []
    if not weekdays:
        return "Once"
    try:
        return " ".join(_WEEKDAYS[index] for index in range(7) if index in weekdays)
    except (TypeError, IndexError):
        return "Weekly"


class AlertListView:
    def __init__(self, display):
        self._display = display

    def state_index(self, alerts, x, y):
        return state_index(self._display, alerts, x, y)

    def render(self, alerts):
        display = self._display
        display.fill_rect(0, 0, display.width, display.height, config.COLOR_BACKGROUND)
        display.draw_text(
            "ALERTS", 8, 3, config.FONT_SETTINGS_STATUS, config.COLOR_SECONDARY
        )
        if not alerts:
            display.draw_text(
                "No alerts stored", 8, HEADER_HEIGHT + 8,
                config.FONT_SETTINGS_STATUS, config.COLOR_WHITE,
            )
            return
        for index, alert in enumerate(alerts[:10]):
            y = HEADER_HEIGHT + index * ROW_HEIGHT
            hour = int(alert.get("hour", 0))
            minute = int(alert.get("minute", 0))
            time_text = "%02d:%02d" % (hour, minute)
            display.draw_text(
                time_text, 8, y + 2, config.FONT_SETTINGS_STATUS, config.COLOR_WHITE
            )
            display.draw_text(
                recurrence_text(alert), 72, y + 4,
                config.FONT_LUNAR, config.COLOR_WHITE,
            )
            enabled = bool(alert.get("enabled"))
            rect = state_rect(display, index)
            color = config.COLOR_PRIMARY if enabled else config.COLOR_SECONDARY
            label = "ON" if enabled else "OFF"
            display.fill_rect(*rect, color)
            text_w, text_h = display.measure_text(label, config.FONT_SETTINGS_STATUS)
            display.draw_text(
                label,
                rect[0] + (rect[2] - text_w) // 2,
                rect[1] + (rect[3] - text_h) // 2,
                config.FONT_SETTINGS_STATUS,
                config.COLOR_BACKGROUND,
            )
