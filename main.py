from machine import Pin, SPI
from time import sleep_ms

from src import config
from src.device.display import ILI9341, splash_screen


def main():
    led = Pin("LED", Pin.OUT)
    led.value(1)

    print("Initializing SPI0 TFT demo")
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

    print("Drawing hello world splash")
    splash_screen(display)
    led.value(0)
    print("Splash shown; leaving the board alive")

    while True:
        sleep_ms(1000)


try:
    main()
except Exception as exc:
    print("TFT demo failed:", exc)
    led = Pin("LED", Pin.OUT)
    while True:
        led.value(1)
        sleep_ms(150)
        led.value(0)
        sleep_ms(150)
