"""Shared status-layer compositor: badge visibility + draw-last (AD-12)."""

from src.time.model import TRUST_UNSYNCED
from src.ui.components import draw_unsynced_badge


class UiCompositor:
    """
    Owns previous badge visibility for Clock and Calendar base views.

    On a visibility change, invalidates the active base so underlying pixels
    restore, then always draws the UNSYNCED badge last (or nothing when synced).
    """

    def __init__(self, display):
        self._display = display
        self._prev_badge = None

    def render(self, base_view, snapshot, *args):
        show_badge = snapshot.trust == TRUST_UNSYNCED
        if self._prev_badge is not None and self._prev_badge != show_badge:
            if hasattr(base_view, "invalidate"):
                base_view.invalidate()
        base_view.render(snapshot, *args)
        draw_unsynced_badge(self._display, show_badge)
        self._prev_badge = show_badge
