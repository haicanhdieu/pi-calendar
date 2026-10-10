"""Full-screen, read-only alert list with per-alert enabled controls."""

from src import config
from src.ui.components import point_in_rect

HEADER_HEIGHT = 23
ROW_HEIGHT = 38
FOOTER_HEIGHT = 27
ROWS_PER_PAGE = 5
STATE_WIDTH = 80
STATE_HEIGHT = 30
STATE_X = 232
PAGE_BUTTON_WIDTH = 72
PAGE_PREV_X = 160
PAGE_NEXT_X = 240
_WEEKDAYS = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")


def state_rect(display, index):
    row_y = HEADER_HEIGHT + (int(index) % ROWS_PER_PAGE) * ROW_HEIGHT
    return (
        STATE_X,
        row_y + (ROW_HEIGHT - STATE_HEIGHT) // 2,
        STATE_WIDTH,
        STATE_HEIGHT,
    )


def state_index(display, alerts, x, y, page=0):
    """Return visible alert index, or None outside a state control."""
    start = max(0, int(page)) * ROWS_PER_PAGE
    for index in range(start, min(start + ROWS_PER_PAGE, len(alerts))):
        if point_in_rect(x, y, state_rect(display, index)):
            return index
    return None


def page_action(display, alerts, page, x, y):
    """Return previous/next page action for visible footer targets."""
    pages = max(1, (len(alerts) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE)
    footer_y = display.height - FOOTER_HEIGHT
    if pages < 2:
        return None
    if page > 0 and point_in_rect(
        x, y, (PAGE_PREV_X, footer_y, PAGE_BUTTON_WIDTH, FOOTER_HEIGHT)
    ):
        return "previous"
    if page + 1 < pages and point_in_rect(
        x, y, (PAGE_NEXT_X, footer_y, PAGE_BUTTON_WIDTH, FOOTER_HEIGHT)
    ):
        return "next"
    return None


def handle_touch(app, x, y):
    """Apply a state-control touch and report (control_hit, valid_point)."""
    view = getattr(app, "_alert_list_view", None)
    if view is None:
        view = AlertListView(app._view._display)
        app._alert_list_view = view
    settings = app._alert_cfg[2]
    alerts = settings.get("alerts", []) if isinstance(settings, dict) else []
    index = state_index(app._view._display, alerts, x, y, view.page)
    if index is not None:
        from src.alert.runtime import toggle_enabled

        toggle_enabled(app, alerts[index].get("id"))
        return True, True
    action = page_action(app._view._display, alerts, view.page, x, y)
    if action == "previous":
        view.page -= 1
        return True, True
    if action == "next":
        view.page += 1
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
        self.page = 0

    def state_index(self, alerts, x, y):
        return state_index(self._display, alerts, x, y, self.page)

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
        page_count = (len(alerts) + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE
        self.page = min(max(0, self.page), max(0, page_count - 1))
        if page_count > 1:
            display.draw_text(
                "%d/%d" % (self.page + 1, page_count),
                display.width - 38, 4, config.FONT_WEEKDAY, config.COLOR_SECONDARY,
            )
        start = self.page * ROWS_PER_PAGE
        for index, alert in enumerate(alerts[start:start + ROWS_PER_PAGE], start):
            y = HEADER_HEIGHT + (index % ROWS_PER_PAGE) * ROW_HEIGHT
            hour = int(alert.get("hour", 0))
            minute = int(alert.get("minute", 0))
            time_text = "%02d:%02d" % (hour, minute)
            display.draw_text(
                time_text, 8, y + 2, config.FONT_SETTINGS_STATUS, config.COLOR_WHITE
            )
            display.draw_text(
                recurrence_text(alert), 72, y + 4,
                config.FONT_WEEKDAY, config.COLOR_SECONDARY,
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
        if self.page > 0:
            self._draw_page_button(PAGE_PREV_X, display.height - FOOTER_HEIGHT, "PREV")
        if self.page + 1 < page_count:
            self._draw_page_button(PAGE_NEXT_X, display.height - FOOTER_HEIGHT, "NEXT")

    def _draw_page_button(self, x, y, label):
        display = self._display
        rect = (x, y, PAGE_BUTTON_WIDTH, FOOTER_HEIGHT)
        display.fill_rect(*rect, config.COLOR_BAR_PANEL)
        text_w, text_h = display.measure_text(label, config.FONT_WEEKDAY)
        display.draw_text(
            label,
            x + (PAGE_BUTTON_WIDTH - text_w) // 2,
            y + (FOOTER_HEIGHT - text_h) // 2,
            config.FONT_WEEKDAY,
            config.COLOR_SECONDARY,
        )
