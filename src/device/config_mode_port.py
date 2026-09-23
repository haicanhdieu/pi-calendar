"""Device boundary for requesting the existing config-mode boot."""

from src.device.mode_flag import request_config_mode


class ConfigModePort:
    """Write the config handoff flag, then reset only when the write succeeds."""

    def __init__(self, reboot_port, request_fn=None):
        self._reboot_port = reboot_port
        self._request_fn = request_config_mode if request_fn is None else request_fn

    def enter(self):
        """Request config mode; return False without resetting on write failure."""
        try:
            requested = self._request_fn()
        except Exception:
            return False
        if not requested:
            return False
        self._reboot_port.reset()
        return True
