# Pi Calendar Hardware Configuration

This document is the hardware and display configuration source of truth for
future development.

## Controller

- Board: Raspberry Pi Pico W
- MCU: RP2040
- Firmware: MicroPython
- Current USB serial device during development: `/dev/cu.usbmodem1101`

The serial device name may change when the board is reconnected.

## TFT display

- Display: 2.4-inch SPI TFT
- Controller: ILI9341 (current driver assumption)
- Native resolution: 240 x 320
- Current orientation: landscape
- Logical resolution: 320 x 240
- Current MADCTL rotation value: `0xA8`

`0xA8` is the currently tested orientation for this physical display. It
keeps the display landscape and corrects the left-right mirroring observed
with `0x28`.

## TFT wiring

| TFT pin | Pico W GPIO | Pico W physical pin | Purpose |
|---|---:|---:|---|
| VCC | 3V3(OUT) | 36 | Display power |
| GND | GND | 23 | Common ground |
| CS | GP17 | 22 | SPI chip select |
| RST / RESET | GP21 | 27 | Display reset |
| DC / RS | GP20 | 26 | Data / command |
| SDI / MOSI | GP19 | 25 | SPI0 TX / MOSI |
| SCK / CLK | GP18 | 24 | SPI0 clock |
| SDO / MISO | GP16 | 21 | SPI0 RX / MISO |
| LED | 3V3(OUT) | 36 | TFT backlight |

## SPI configuration

```text
SPI bus: SPI0
MISO: GP16
CS:   GP17
SCK:  GP18
MOSI: GP19
DC:   GP20
RST:  GP21
```

The current firmware uses a 40 MHz SPI clock.

## Unused connections

- Touch pins are unused: `T_CLK`, `T_CS`, `T_DIN`, `T_DO`, `T_IRQ`
- microSD is currently out of scope.

## Software notes

- Source firmware: [`main.py`](../main.py)
- The onboard Pico W LED is set on during initialization and turned off after
  the splash screen; an unlit LED after startup is therefore expected.
- Keep the GPIO assignments and `0xA8` display orientation unchanged unless
  the physical wiring or display orientation is intentionally changed.
