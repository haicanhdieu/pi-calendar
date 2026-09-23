"""Device boundary for resetting the Pico without exposing ``machine`` to App."""

from src.device.mode_flag import request_config_mode


class RebootPort:
    """Invoke an injected reset callback; host tests can provide a harmless fake."""

    def __init__(self, reset_callback):
        self._reset_callback = reset_callback

    def reset(self, config_mode=False):
        """Reset; write one-shot mode flag first when requested."""
        if config_mode and not request_config_mode():
            return False
        self._reset_callback()
        if config_mode:
            return True
