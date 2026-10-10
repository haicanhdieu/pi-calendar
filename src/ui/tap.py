"""Lazy touch routing helpers for normal clock surfaces."""

from src import config
from src.ui.touch_state import (
    BAR_TARGET_GEAR, BAR_TARGET_IN_PANEL, BAR_TARGET_OUTSIDE,
    SURFACE_ALERTS, SURFACE_BAR,
)


def touch(app, surface, edge_down, x, y, now):
    bar_target = None
    surface_edge_down = edge_down
    control_pressed = False
    if surface == SURFACE_BAR and edge_down:
        from src.ui.bar_controls import button_at, flash

        button = button_at(app._view._display, x, y)
        if button == BAR_TARGET_GEAR or button == SURFACE_ALERTS:
            bar_target = button
            flash(app._view._display, button)
            app.state.redraw_deadline = app._ticks.ticks_add(now, config.PRESS_FLASH_MS)
        elif app._compositor.bar_panel_hit(x, y):
            bar_target = BAR_TARGET_IN_PANEL
        elif app._compositor.bar_outside_edge(x, y):
            bar_target = BAR_TARGET_OUTSIDE
    elif surface == SURFACE_ALERTS and edge_down:
        from src.ui.alert_list_view import handle_touch

        control_hit, valid_point = handle_touch(app, x, y)
        control_pressed = control_hit
        if control_hit or not valid_point:
            surface_edge_down = False
    return bar_target, surface_edge_down, control_pressed
