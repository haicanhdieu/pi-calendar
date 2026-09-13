"""Pure Rotation/Bar touch-surface transition decisions."""

from src.config import TOUCH_IDLE_TIMEOUT_MS
from src.ticks import ticks_add, ticks_diff

SURFACE_ROTATION = "rotation"
SURFACE_BAR = "bar"
SURFACE_SETTINGS = "settings"

BAR_TARGET_GEAR = "gear"
BAR_TARGET_IN_PANEL = "in_panel"
BAR_TARGET_OUTSIDE = "outside"

SETTINGS_TARGET_REBOOT = "reboot"


def next_surface(
    active_surface,
    surface_deadline,
    edge_down,
    now,
    bar_target=None,
    settings_target=None,
):
    """
    Return ``(next_surface, next_deadline)`` for a touch-surface evaluation.

    A fresh touch reveals the Bar only from Rotation.  Each surface's deadline
    is armed on entry alone; later evaluations never renew it.  Gear routing
    enters Settings with its own idle deadline; Settings dismisses to Rotation
    on expiry or an outside tap, preserving the Reboot target.
    """
    if active_surface == SURFACE_ROTATION:
        if edge_down:
            return SURFACE_BAR, ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)
        return SURFACE_ROTATION, surface_deadline

    if active_surface == SURFACE_BAR:
        if edge_down and bar_target == BAR_TARGET_GEAR:
            return SURFACE_SETTINGS, ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)
        if edge_down and bar_target == BAR_TARGET_IN_PANEL:
            return SURFACE_BAR, surface_deadline
        if surface_deadline is not None and ticks_diff(surface_deadline, now) <= 0:
            return SURFACE_ROTATION, None
        if edge_down and bar_target == BAR_TARGET_OUTSIDE:
            return SURFACE_ROTATION, None
        if edge_down:
            return SURFACE_BAR, surface_deadline
        return SURFACE_BAR, surface_deadline

    if active_surface == SURFACE_SETTINGS:
        if edge_down and settings_target == SETTINGS_TARGET_REBOOT:
            return SURFACE_SETTINGS, surface_deadline
        if surface_deadline is not None and ticks_diff(surface_deadline, now) <= 0:
            return SURFACE_ROTATION, None
        if edge_down:
            return SURFACE_ROTATION, None
        return SURFACE_SETTINGS, surface_deadline

    return active_surface, surface_deadline
