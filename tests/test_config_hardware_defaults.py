"""Host lock for TFT pin/SPI/MADCTL defaults after config extraction."""

from src import config


def test_tft_spi_and_madctl_match_hardware_docs():
    # docs/hardware_configuration.md — SPI0 GP16–21, 40 MHz mode 0, 320×240, MADCTL 0xA8
    assert config.TFT_MISO == 16
    assert config.TFT_CS == 17
    assert config.TFT_SCK == 18
    assert config.TFT_MOSI == 19
    assert config.TFT_DC == 20
    assert config.TFT_RST == 21
    assert config.SCREEN_WIDTH == 320
    assert config.SCREEN_HEIGHT == 240
    assert config.SPI_BAUDRATE == 40_000_000
    assert config.SPI_POLARITY == 0
    assert config.SPI_PHASE == 0
    assert config.MADCTL == 0xA8


def test_network_proof_mode_defaults_off():
    # Product boot must not silently divert into the Story 1.4 harness.
    assert config.NETWORK_PROOF_MODE is False
