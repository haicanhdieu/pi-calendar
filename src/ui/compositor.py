"""Shared status-layer compositor: badge visibility + draw-last (AD-12)."""

from src.time.model import TRUST_UNSYNCED
from src import config
from src.ui.components import draw_bar, draw_unsynced_badge
from src.ui.touch_state import SURFACE_BAR


class UiCompositor:
    """
    Owns previous status-overlay visibility for Clock and Calendar base views.

    On a visibility change, invalidates the active base so underlying pixels
    restore, then draws the UNSYNCED badge followed by the Bar when active.
    """

    def __init__(self, display):
        self._display = display
        self._prev_badge = None
        self._prev_bar = None

    def render(self, base_view, snapshot, *args, active_surface="rotation", bar_elapsed_ms=0):
        show_badge = snapshot.trust == TRUST_UNSYNCED
        show_bar = active_surface == SURFACE_BAR
        if (
            self._prev_badge is not None
            and self._prev_badge != show_badge
            or self._prev_bar is not None
            and self._prev_bar != show_bar
        ):
            if hasattr(base_view, "invalidate"):
                base_view.invalidate()
        base_view.render(snapshot, *args)
        draw_unsynced_badge(self._display, show_badge)
        if bar_elapsed_ms < 0:
            bar_elapsed_ms = 0
        if bar_elapsed_ms >= config.BAR_SLIDE_DURATION_MS:
            bar_height = config.BAR_HEIGHT_PX
        else:
            bar_height = (
                config.BAR_HEIGHT_PX * int(bar_elapsed_ms)
            ) // config.BAR_SLIDE_DURATION_MS
        draw_bar(self._display, show_bar, bar_height)
        self._prev_badge = show_badge
        self._prev_bar = show_bar
