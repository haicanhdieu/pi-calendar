"""Pure Rotation/Bar touch-surface transition decisions."""

from src.config import TOUCH_IDLE_TIMEOUT_MS
from src.ticks import ticks_add, ticks_diff

SURFACE_ROTATION = "rotation"
SURFACE_BAR = "bar"
SURFACE_SETTINGS = "settings"


def next_surface(active_surface, surface_deadline, edge_down, now):
    """
    Return ``(next_surface, next_deadline)`` for a touch-surface evaluation.

    A fresh touch reveals the Bar only from Rotation.  The Bar's deadline is
    armed on that entry alone; later evaluations never renew it.  Settings is
    retained unchanged until its interaction is implemented by a later story.
    """
    if active_surface == SURFACE_ROTATION:
        if edge_down:
            return SURFACE_BAR, ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)
        return SURFACE_ROTATION, surface_deadline

    if active_surface == SURFACE_BAR:
        if surface_deadline is not None and ticks_diff(surface_deadline, now) <= 0:
            return SURFACE_ROTATION, None
        return SURFACE_BAR, surface_deadline

    if active_surface == SURFACE_SETTINGS:
        return SURFACE_SETTINGS, surface_deadline

    return active_surface, surface_deadline
