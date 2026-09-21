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
    assert config.TOUCH_CS == 22
    assert config.TOUCH_IRQ == 26
    assert config.TOUCH_SPI_BAUDRATE <= 2_000_000


def test_touch_ui_defaults_are_named_and_bounded():
    assert config.TOUCH_SAMPLE_COUNT > 0
    assert config.TOUCH_SAMPLE_MAX_SPREAD >= 0
    assert config.TOUCH_PRESSURE_MIN > 0
    assert config.TOUCH_IDLE_TIMEOUT_MS == 15_000
    assert 200 <= config.BAR_SLIDE_DURATION_MS <= 300
    assert config.BAR_ANIMATION_FRAME_MS > 0
    assert config.BAR_HEIGHT_PX == 36
    assert config.TAP_TARGET_SIZE_PX > 0
    assert config.PRESS_FLASH_MS > 0


def test_network_proof_mode_defaults_off():
    # Product boot must not silently divert into the Story 1.4 harness.
    assert config.NETWORK_PROOF_MODE is False


def test_buzzer_defaults_match_hw508_cadence():
    assert config.BUZZER_SIGNAL_PIN == 15
    assert config.BUZZER_ACTIVE_HIGH is True
    assert config.BUZZER_HIGH_MS == 180
    assert config.BUZZER_LOW_MS == 220


def test_station_recovery_budgets():
    assert config.STATION_FAILURE_LIMIT == 3
    assert config.STATION_IP_DISPLAY_MS is None
    assert config.STATION_RECONNECT_GAP_MS >= 0
    # Pin map untouched by story 1.3 constants.
    assert config.TFT_SCK == 18
    assert config.TFT_MOSI == 19
