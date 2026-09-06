from machine import Pin, SPI
from time import sleep_ms

from src import config
from src.app import App
from src.credentials import credentials_valid
from src.device.clock_port import RtcClockPort
from src.device.display import ILI9341
from src.device.display.adapter import Ili9341DisplayPort
from src.ui.clock_view import ClockView


def main():
    led = Pin("LED", Pin.OUT)
    led.value(1)

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

    display = ILI9341(
        spi=spi,
        dc=config.TFT_DC,
        rst=config.TFT_RST,
        cs=config.TFT_CS,
    )

    display_port = Ili9341DisplayPort(display)
    clock_view = ClockView(display_port)
    clock_port = RtcClockPort()
    app = App(clock_port=clock_port, clock_view=clock_view)

    if not credentials_valid():
        app.report_time_source_failure("missing or empty Wi-Fi credentials")

    led.value(0)
    print("App loop starting (Clock view)")
    app.run_forever(sleep_ms_fn=sleep_ms)


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
