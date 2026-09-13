"""Full-screen Settings view (Stories 3.1–3.2)."""

from src import config
from src.ui.components import settings_reboot_rect

_KIND_SETUP = "setup"
_KIND_STATION_IP = "station_ip"


def _centered_text_x(display, text, font_id):
    tw, _ = display.measure_text(text, font_id)
    return (display.width - tw) // 2


def _draw_status_lines(display, lines):
    """Draw one or two centered status lines in FONT_SETTINGS_STATUS."""
    font = config.FONT_SETTINGS_STATUS
    color = config.COLOR_PRIMARY
    _, line_h = display.measure_text("Ag", font)
    y = config.SETTINGS_TOP_PADDING_PX
    for index, text in enumerate(lines):
        if not text:
            continue
        text = str(text)
        display.draw_text(text, _centered_text_x(display, text, font), y, font, color)
        if index < len(lines) - 1:
            y += line_h + config.SETTINGS_STATUS_LINE_GAP_PX
        else:
            y += line_h
    return y


def _draw_guideline(display, text, after_y):
    font = config.FONT_SETTINGS_GUIDELINE
    y = after_y + config.SETTINGS_STATUS_GUIDELINE_GAP_PX
    display.draw_text(
        text,
        _centered_text_x(display, text, font),
        y,
        font,
        config.COLOR_SECONDARY,
    )


class SettingsView:
    """Settings surface: status/guideline copy plus reboot placeholder region."""

    def __init__(self, display):
        self._display = display
        self._valid = False

    def invalidate(self):
        self._valid = False

    def render(self, status_snapshot):
        """Paint Settings; branch status/guideline copy on snapshot kind."""
        display = self._display
        display.fill_rect(
            0, 0, display.width, display.height, config.COLOR_BACKGROUND
        )
        if status_snapshot:
            kind = status_snapshot.get("kind")
            if kind == _KIND_SETUP:
                ssid = status_snapshot.get("ssid") or ""
                gateway = status_snapshot.get("ip") or ""
                after_y = _draw_status_lines(display, [ssid, gateway])
                _draw_guideline(
                    display,
                    f"Connect to Wi-Fi {ssid} then browse to {gateway}",
                    after_y,
                )
            elif kind == _KIND_STATION_IP:
                ip = status_snapshot.get("ip")
                if ip:
                    after_y = _draw_status_lines(display, [str(ip)])
                    _draw_guideline(display, f"Browse to http://{ip}", after_y)
        x, y, w, h = settings_reboot_rect(display)
        display.fill_rect(x, y, w, h, config.COLOR_BAR_PANEL)
        self._valid = True
