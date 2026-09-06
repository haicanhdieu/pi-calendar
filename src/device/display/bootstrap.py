"""Host-testable display boot boundary for the composition root."""

from src import config


def initialize_display(spi, display_factory, splash_renderer, sleep_ms_fn, log_fn):
    """Initialize the panel, render its checkpoint, and wait briefly."""
    display = display_factory(
        spi=spi,
        dc=config.TFT_DC,
        rst=config.TFT_RST,
        cs=config.TFT_CS,
    )
    log_fn("TFT initialized; showing boot checkpoint")
    splash_renderer(display)
    sleep_ms_fn(config.BOOT_CHECKPOINT_DWELL_MS)
    return display
