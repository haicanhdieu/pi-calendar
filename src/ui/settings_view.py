"""Full-screen Settings view (Stories 3.1–3.3)."""

from src import config
from src.gfx import draw_spaced_text, measure_spaced_font_text
from src.ui.components import (
    point_in_rect,
    settings_mode_item_rect,
    settings_mode_rect,
    settings_reboot_item_rect,
    settings_reboot_rect,
)

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


def _draw_reboot_label(
    display,
    fill_color=None,
    label=config.SETTINGS_REBOOT_LABEL,
    region=None,
):
    """Draw a Settings control label centered in its tap-target block."""
    if region is None:
        region = settings_reboot_item_rect(display)
    region_x, region_y, region_w, region_h = region
    if fill_color is not None:
        display.fill_rect(region_x, region_y, region_w, region_h, fill_color)
    font = config.FONT_SETTINGS_REBOOT
    spacing = config.SETTINGS_REBOOT_LETTER_SPACING_PX
    text_w, text_h = measure_spaced_font_text(label, font, spacing)
    text_x = region_x + (region_w - text_w) // 2
    text_y = region_y + (region_h - text_h) // 2
    draw_spaced_text(
        display,
        label,
        text_x,
        text_y,
        font,
        config.COLOR_SECONDARY,
        spacing,
    )
class SettingsView:
    """Settings surface: status/guideline copy plus reboot control."""

    def __init__(self, display):
        self._display = display
        self._valid = False

    def invalidate(self):
        self._valid = False

    def reboot_item_rect(self):
        """Return the reboot button tap-target rect (x, y, w, h)."""
        return settings_reboot_item_rect(self._display)

    def reboot_hit(self, x, y):
        """Return whether a point lies inside the reboot tap target."""
        return point_in_rect(x, y, self.reboot_item_rect())

    def mode_item_rect(self):
        return settings_mode_item_rect(self._display)

    def mode_hit(self, x, y):
        return point_in_rect(x, y, self.mode_item_rect())

    def draw_reboot_press_flash(self):
        """Render the mandatory Press Flash on the reboot control."""
        _draw_reboot_label(self._display, fill_color=config.COLOR_PRESS_FLASH)

    def draw_mode_press_flash(self):
        """Render the mandatory Press Flash on the Setting Mode control."""
        _draw_reboot_label(
            self._display,
            fill_color=config.COLOR_PRESS_FLASH,
            label=config.SETTINGS_MODE_LABEL,
            region=settings_mode_rect(self._display),
        )

    def draw_mode_control(self):
        """Restore the normal Setting Mode control after a failed request."""
        region = settings_mode_rect(self._display)
        self._display.fill_rect(*region, config.COLOR_BAR_PANEL)
        _draw_reboot_label(
            self._display,
            label=config.SETTINGS_MODE_LABEL,
            region=region,
        )

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
        self.draw_mode_control()
        _x, y, _w, h = settings_reboot_rect(display)
        display.fill_rect(_x, y, _w, h, config.COLOR_BAR_PANEL)
        _draw_reboot_label(display)
        self._valid = True
