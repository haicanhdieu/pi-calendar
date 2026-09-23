"""Shared status-layer compositor: badge visibility + draw-last (AD-12)."""

from src.time.model import TRUST_UNSYNCED
from src import config
from src.ui.components import (
    bar_gear_item_rect,
    bar_rect,
    draw_bar,
    draw_unsynced_badge,
    point_in_rect,
    settings_reboot_item_rect,
    settings_mode_item_rect,
)
from src.ui.touch_state import SURFACE_BAR, SURFACE_SETTINGS


class UiCompositor:
    """
    Owns previous status-overlay visibility for Clock and Calendar base views.

    On a visibility change, invalidates the active base so underlying pixels
    restore, then draws the UNSYNCED badge followed by the Bar when active.
    """

    def __init__(self, display):
        self._display = display
        self._prev_badge = None
        self._prev_bar_height = 0
        self._prev_was_settings = False

    def bar_gear_hit(self, x, y):
        """Test a sampled point against the named Bar gear geometry."""
        return point_in_rect(x, y, bar_gear_item_rect(self._display))

    def bar_panel_hit(self, x, y):
        """Test a sampled point against the named Bar panel geometry."""
        return point_in_rect(x, y, bar_rect(self._display))

    def bar_outside_edge(self, x, y):
        """True when coords are valid integers outside the named Bar panel."""
        if self.bar_panel_hit(x, y):
            return False
        try:
            int(x)
            int(y)
        except (TypeError, ValueError, OverflowError):
            return False
        return True

    def settings_reboot_hit(self, x, y):
        """Test a sampled point against the Settings reboot tap geometry."""
        return point_in_rect(x, y, settings_reboot_item_rect(self._display))

    def settings_mode_hit(self, x, y):
        return point_in_rect(x, y, settings_mode_item_rect(self._display))

    def settings_outside_edge(self, x, y):
        """True when coords are valid integers outside the reboot target."""
        if self.settings_reboot_hit(x, y):
            return False
        try:
            int(x)
            int(y)
        except (TypeError, ValueError, OverflowError):
            return False
        return True

    def render(
        self,
        base_view,
        snapshot,
        *args,
        active_surface="rotation",
        bar_elapsed_ms=0,
        bar_retract_elapsed_ms=None,
        bar_retract_start_height=None,
    ):
        if active_surface == SURFACE_SETTINGS:
            if not self._prev_was_settings:
                # Settings content is static for the whole time it's open
                # (the status snapshot is captured once on entry); redrawing
                # identical content every tick just flickers the screen.
                if self._prev_badge or self._prev_bar_height > 0:
                    self._display.fill_rect(
                        0,
                        0,
                        self._display.width,
                        self._display.height,
                        config.COLOR_BACKGROUND,
                    )
                if hasattr(base_view, "invalidate"):
                    base_view.invalidate()
                base_view.render(snapshot)
                self._prev_badge = False
                self._prev_bar_height = 0
                self._prev_was_settings = True
            return
        if self._prev_was_settings:
            # Settings painted the whole screen; the base view's own
            # previously-drawn pixels no longer match what it thinks is on
            # screen, so a resumed diff-redraw would only repaint deltas.
            if hasattr(base_view, "invalidate"):
                base_view.invalidate()
            self._prev_was_settings = False
        show_badge = snapshot.trust == TRUST_UNSYNCED
        if bar_retract_elapsed_ms is not None:
            elapsed = max(0, int(bar_retract_elapsed_ms))
            if bar_retract_start_height is None:
                bar_retract_start_height = config.BAR_HEIGHT_PX
            bar_retract_start_height = max(
                0, min(int(bar_retract_start_height), config.BAR_HEIGHT_PX)
            )
            bar_height = max(
                0,
                bar_retract_start_height
                - (bar_retract_start_height * elapsed) // config.BAR_SLIDE_DURATION_MS,
            )
        elif active_surface == SURFACE_BAR:
            if bar_elapsed_ms < 0:
                bar_elapsed_ms = 0
            if bar_elapsed_ms >= config.BAR_SLIDE_DURATION_MS:
                bar_height = config.BAR_HEIGHT_PX
            else:
                bar_height = (
                    config.BAR_HEIGHT_PX * int(bar_elapsed_ms)
                ) // config.BAR_SLIDE_DURATION_MS
        else:
            bar_height = 0
        if self._prev_badge is not None and self._prev_badge != show_badge:
            if hasattr(base_view, "invalidate"):
                base_view.invalidate()
        # The base render cannot know a former overlay existed. Restore only
        # newly uncovered Bar pixels, before it and before the draw-last Bar.
        if bar_height < self._prev_bar_height:
            if hasattr(base_view, "invalidate"):
                base_view.invalidate()
            restore_y = self._display.height - self._prev_bar_height
            restore_w = self._display.width
            restore_h = self._prev_bar_height - bar_height
            self._display.fill_rect(
                0, restore_y, restore_w, restore_h, config.COLOR_BACKGROUND
            )
        base_view.render(snapshot, *args)
        draw_unsynced_badge(self._display, show_badge)
        draw_bar(self._display, bar_height > 0, bar_height)
        self._prev_badge = show_badge
        self._prev_bar_height = bar_height
