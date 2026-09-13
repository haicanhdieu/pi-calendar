"""Device boundary for resetting the Pico without exposing ``machine`` to App."""


class RebootPort:
    """Invoke an injected reset callback; host tests can provide a harmless fake."""

    def __init__(self, reset_callback):
        self._reset_callback = reset_callback

    def reset(self):
        """Request exactly one device reset."""
        self._reset_callback()
