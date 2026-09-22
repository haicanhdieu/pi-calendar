from machine import Pin, SPI, reset
from time import sleep_ms

from src import config
from src.device.clock_port import RtcClockPort
from src.device.mode_flag import consume_config_mode
from src.device.reboot_port import RebootPort
from src.device.display.bootstrap import initialize_display
from src.device.display.ili9341 import ILI9341
from src.device.display.splash import splash_screen
from src.device.settings_store import SettingsStore


def main():
    led = Pin("LED", Pin.OUT)
    led.value(1)

    # Story 1.4: gated proof harness (set NETWORK_PROOF_MODE True only for flash).
    if config.NETWORK_PROOF_MODE:
        print("NETWORK_PROOF_MODE: running Story 1.4 mailbox proof harness")
        led.value(0)
        from src.device.network.proof import run_proof

        run_proof()
        return

    # Read and clear the handoff flag before anything else can fail. Clearing
    # on entry is what makes config mode self-healing: a crash below returns
    # the device to the clock on the next reset (issue #2).
    config_mode = consume_config_mode()

    print("Initializing SPI0 TFT + App loop")
    import gc

    gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
    # The XPT2046 shares SPI0 with the TFT.  Hold it deselected before any
    # display traffic so its MISO output cannot be active during TFT bring-up.
    touch_cs = Pin(config.TOUCH_CS, Pin.OUT)
    touch_cs.value(1)
    spi = SPI(
        0,
        baudrate=config.SPI_BAUDRATE,
        polarity=config.SPI_POLARITY,
        phase=config.SPI_PHASE,
        sck=Pin(config.TFT_SCK),
        mosi=Pin(config.TFT_MOSI),
        miso=Pin(config.TFT_MISO),
    )

    display = initialize_display(spi, ILI9341, splash_screen, sleep_ms, print)

    # Splash rendering creates temporary command and pixel buffers. Release
    # them before constructing the mode stack; otherwise the Pico can fail a
    # later contiguous allocation on first boot.
    gc.collect()
    print("TFT checkpoint complete; app construction")

    clock_port = RtcClockPort()
    reboot_port = RebootPort(reset)
    settings_store = SettingsStore(path=config.SETTINGS_BASENAME)

    # Exactly one of these two stacks is ever imported. That is the whole
    # mitigation: the clock stack and the station web stack are never live in
    # the same 179,328-byte heap (issue #2).
    if config_mode:
        from src.device.config_mode import run as run_config_mode

        run_config_mode(
            display,
            settings_store,
            clock_port,
            reboot_port,
            sleep_ms,
            led=led,
        )
        return

    from src.device.clock_mode import run as run_clock_mode

    run_clock_mode(
        display,
        spi,
        touch_cs,
        settings_store,
        clock_port,
        reboot_port,
        sleep_ms,
        led=led,
    )


try:
    main()
except Exception as exc:
    print("App failed:", exc)
    led = Pin("LED", Pin.OUT)
    while True:
        led.value(1)
        sleep_ms(150)
        led.value(0)
        sleep_ms(150)
