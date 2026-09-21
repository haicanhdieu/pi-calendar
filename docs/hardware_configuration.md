# Pi Calendar Hardware Configuration

This document is the hardware and display configuration source of truth for
future development.

## Controller

- Board: Raspberry Pi Pico W
- MCU: RP2040
- Firmware: MicroPython
- Current USB serial device during development: `/dev/cu.usbmodem1101`

The serial device name may change when the board is reconnected.

## TFT display and touch

- Display: 2.8-inch SPI TFT with resistive touch
- Display controller: ILI9341 (current driver assumption; confirm the module
  label before changing the driver)
- Touch controller: XPT2046-compatible (confirm the module label; common
  labels are `XPT2046` and `ADS7846`)
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

## Touch wiring

The touch controller uses the same SPI0 bus as the TFT. Each shared Pico GPIO
must physically branch to **both pins on the new module**: `GP18` to `SCK`
**and** `T_CLK`, `GP19` to `SDI` **and** `T_DIN`, and `GP16` to `SDO` **and**
`T_DO`. Connecting only the `T_*` pin does not connect the TFT controller.
Do **not** connect the touch `T_CS` pin to the TFT `CS` pin.

| Touch pin | Pico W connection | Pico W physical pin | Purpose |
|---|---:|---:|---|
| `T_CLK` | GP18 (shared with TFT `SCK`) | 24 | SPI0 clock |
| `T_DIN` | GP19 (shared with TFT `SDI` / MOSI) | 25 | SPI0 MOSI, Pico → touch controller |
| `T_DO` | GP16 (shared with TFT `SDO` / MISO) | 21 | SPI0 MISO, touch controller → Pico |
| `T_CS` | GP22 | 29 | Touch-controller chip select |
| `T_IRQ` | GP26 | 31 | Active-low touch interrupt input |

`T_IRQ` is optional for initial polling-based touch support, but connect it
now so firmware can detect a touch without continuously reading the
controller. Configure it as a pulled-up input; the XPT2046 drives it low while
the panel is touched. Do not connect this pin to 5 V.

The display and touch board must use a common ground with the Pico. Keep VCC
at the module's documented logic voltage; this configuration assumes a
3.3 V-compatible SPI module, as the Pico GPIOs are not 5 V tolerant.

## HW-508 buzzer wiring

The installed three-pin HW-508 board is silk-screened `S`, `VCC`, `GND`.
This differs from the `S`/`NC`/`-` passive-module variant; use the physical
silkscreen on this board as controlling evidence.

| HW-508 pin | Pico W connection | Pico W physical pin | Purpose |
|---|---|---:|---|
| `S` | GP15 | 20 | Direct-GPIO control signal |
| `VCC` | 3V3(OUT) | 36 | 3.3 V module power |
| `GND` | GND | 23 | Common ground |

Flashed-device bench evidence, 2026-09-21: GP15 direct 3.3 V control produced
audible output for a 10-second test and a repeating `tut` cadence (180 ms high,
220 ms low). This proves audibility only, not deployment approval. Before
enabling production firmware control or making a permanent connection, measure
current, confirm the `S` input polarity and 3.3 V safety, and confirm direct
GPIO drive stays within Pico and module limits. Do not connect `VCC` or `S` to
Pico `VBUS`/5 V. Keep GP15 driven low before applying power. If validation
fails, use a suitable driver/buffer circuit instead of direct GPIO drive and
update this section.

## SPI configuration

```text
SPI bus: SPI0
MISO: GP16
TFT CS:   GP17
SCK:  GP18
MOSI: GP19
DC:   GP20
RST:  GP21
Touch CS:  GP22
Touch IRQ: GP26
Buzzer S: GP15 (direct-GPIO audibility verified; electrical validation pending)
```

The current firmware uses a 40 MHz SPI clock.

## Unused connections

- microSD is currently out of scope.

## Software notes

- Source firmware: [`main.py`](../main.py)
- Hardware constants, including `TOUCH_CS` and `TOUCH_IRQ`, are in
  [`src/config.py`](../src/config.py). These constants record the wiring only;
  touch input is not yet initialized by the firmware.
- The onboard Pico W LED is set on during initialization and turned off after
  the splash screen; an unlit LED after startup is therefore expected.
- Keep the GPIO assignments and `0xA8` display orientation unchanged unless
  the physical wiring or display orientation is intentionally changed.
- HW-508 production firmware control remains disabled until current, polarity,
  and direct-drive safety checks pass; audible bench output alone does not
  establish electrical safety.
