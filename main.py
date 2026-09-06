from machine import Pin, SPI
from time import sleep_ms

from src import config
from src.app import App
from src.credentials import credentials_valid
from src.device.clock_port import RtcClockPort
from src.device.display.bootstrap import initialize_display
from src.device.display.adapter import Ili9341DisplayPort
from src.device.display.ili9341 import ILI9341
from src.device.display.splash import splash_screen
from src.device.network.mailbox import Mailbox
from src.device.network.coordinator import NetworkCoordinator
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.compositor import UiCompositor


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

    print("Initializing SPI0 TFT + App loop")
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

    display_port = Ili9341DisplayPort(display)
    clock_view = ClockView(display_port)
    calendar_view = CalendarView(display_port)
    compositor = UiCompositor(display_port)
    clock_port = RtcClockPort()

    mailbox = Mailbox()
    sync_enabled = credentials_valid()
    coordinator = NetworkCoordinator(
        mailbox, ntp_address=config.NTP_SERVER_ADDRESS
    )

    app = App(
        clock_port=clock_port,
        clock_view=clock_view,
        calendar_view=calendar_view,
        compositor=compositor,
        mailbox=mailbox,
        sync_enabled=sync_enabled,
    )

    if not sync_enabled:
        app.report_time_source_failure("missing or empty Wi-Fi credentials")

    led.value(0)
    print("App loop starting (Clock view)")
    app.boot()
    while True:
        coordinator.tick()
        app.step()
        sleep_ms(10)


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
