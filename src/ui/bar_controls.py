"""Lazily loaded drawing and hit geometry for the touch bar buttons."""

from src import config
from src.ui.components import bar_rect


def _item_rect(display, center_x):
    size = config.TAP_TARGET_SIZE_PX
    _x, bar_y, _w, bar_h = bar_rect(display)
    return (center_x - size // 2, bar_y + bar_h // 2 - size // 2, size, size)


def gear_rect(display):
    return _item_rect(display, display.width // 4)


def alerts_rect(display):
    return _item_rect(display, display.width * 3 // 4)


def button_at(display, x, y):
    from src.ui.components import point_in_rect

    if point_in_rect(x, y, gear_rect(display)):
        return "gear"
    if point_in_rect(x, y, alerts_rect(display)):
        return "alerts"
    return None


def flash(display, target):
    from src.ui.components import draw_bar

    draw_bar(display, True, config.BAR_HEIGHT_PX, pressed_target=target)


def draw_buttons(display, pressed_target=None):
    for target, rect in (("gear", gear_rect(display)), ("alerts", alerts_rect(display))):
        x, y, w, h = rect
        cx, cy = x + w // 2, y + h // 2
        color = config.COLOR_PRESS_FLASH if target == pressed_target else config.COLOR_SECONDARY
        if target == "alerts":
            display.fill_rect(cx - 7, cy - 8, 15, 2, color)
            display.fill_rect(cx - 7, cy + 7, 15, 2, color)
            display.fill_rect(cx - 8, cy - 7, 2, 14, color)
            display.fill_rect(cx + 7, cy - 7, 2, 14, color)
            display.fill_rect(cx - 1, cy - 5, 2, 7, color)
            display.fill_rect(cx, cy, 5, 2, color)
        else:
            display.fill_rect(cx - 6, cy - 2, 13, 5, color)
            display.fill_rect(cx - 2, cy - 6, 5, 13, color)
            display.fill_rect(cx - 4, cy - 4, 9, 9, color)
            display.fill_rect(cx - 1, cy - 1, 3, 3, config.COLOR_BAR_PANEL)
