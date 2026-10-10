"""Touch surface transitions."""

from src.config import TOUCH_IDLE_TIMEOUT_MS
from src.ticks import ticks_add, ticks_diff

SURFACE_ROTATION = "rotation"
SURFACE_BAR = "bar"
SURFACE_SETTINGS = "settings"
# Reuse the destination token as the right-bar target to avoid another resident string.
SURFACE_ALERTS = "alerts"

BAR_TARGET_GEAR = "gear"
BAR_TARGET_IN_PANEL = "in_panel"
BAR_TARGET_OUTSIDE = "outside"



def next_surface(
    active_surface,
    surface_deadline,
    edge_down,
    now,
    bar_target=None,
):
    """Return the next surface and its entry deadline."""
    if active_surface == SURFACE_ROTATION:
        if edge_down:
            return SURFACE_BAR, ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)
        return SURFACE_ROTATION, surface_deadline

    if active_surface == SURFACE_BAR:
        if edge_down and (
            bar_target == BAR_TARGET_GEAR or bar_target == SURFACE_ALERTS
        ):
            surface = (
                SURFACE_SETTINGS
                if bar_target == BAR_TARGET_GEAR
                else SURFACE_ALERTS
            )
            return surface, ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)
        if edge_down and bar_target == BAR_TARGET_IN_PANEL:
            return SURFACE_BAR, surface_deadline
        if surface_deadline is not None and ticks_diff(surface_deadline, now) <= 0:
            return SURFACE_ROTATION, None
        if edge_down and bar_target == BAR_TARGET_OUTSIDE:
            return SURFACE_ROTATION, None
        if edge_down:
            return SURFACE_BAR, surface_deadline
        return SURFACE_BAR, surface_deadline

    if active_surface == SURFACE_SETTINGS or active_surface == SURFACE_ALERTS:
        if surface_deadline is not None and ticks_diff(surface_deadline, now) <= 0:
            return SURFACE_ROTATION, None
        if edge_down:
            return SURFACE_ROTATION, None
        return active_surface, surface_deadline

    return active_surface, surface_deadline
