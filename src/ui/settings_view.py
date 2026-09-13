"""Full-screen Settings view scaffold (Story 3.1)."""

from src import config
from src.ui.components import (
    settings_guideline_rect,
    settings_reboot_rect,
    settings_status_rect,
)


class SettingsView:
    """Settings surface: full-screen clear plus three positioned regions."""

    def __init__(self, display):
        self._display = display
        self._valid = False

    def invalidate(self):
        self._valid = False

    def render(self, status_snapshot):
        """Paint the Settings scaffold; tolerates a None status snapshot."""
        del status_snapshot  # exact copy is Story 3.2's scope
        display = self._display
        display.fill_rect(
            0, 0, display.width, display.height, config.COLOR_BACKGROUND
        )
        for rect in (
            settings_status_rect(display),
            settings_guideline_rect(display),
            settings_reboot_rect(display),
        ):
            x, y, w, h = rect
            display.fill_rect(x, y, w, h, config.COLOR_BAR_PANEL)
        self._valid = True
