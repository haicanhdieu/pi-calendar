# Pico W Universal Calendar & Clock --- Project Handoff

## 1. Project Goal

Build a compact **clock + universal calendar** using a **Raspberry Pi
Pico W** and the **2.4-inch SPI TFT display** already connected.

The UI has only two main views:

1.  **Large Clock View** --- large time, weekday, and date.
2.  **Calendar View** --- full monthly calendar with today's date
    highlighted.

The TFT is **not touch-enabled**, so touch pins are not used.

## 2. Current Hardware

-   Raspberry Pi Pico W
-   2.4-inch 240×320 SPI TFT
-   Jumper wires / breadboard
-   USB power for Pico W

Optional later: - DS3231 RTC for accurate time retention after power
loss - One push button for manual view switching

## 3. Confirmed TFT ↔ Pico W Wiring

This configuration matches the wiring diagram used during assembly.

  TFT Pin       Pico W       Physical Pin Purpose
  ------------- ---------- -------------- ------------------
  VCC           3V3(OUT)               36 TFT power
  GND           GND                    23 Ground
  CS            GP17                   22 SPI0 Chip Select
  RESET / RST   GP21                   27 TFT reset
  DC / RS       GP20                   26 Data / Command
  SDI / MOSI    GP19                   25 SPI0 TX / MOSI
  SCK / CLK     GP18                   24 SPI0 clock
  SDO / MISO    GP16                   21 SPI0 RX / MISO
  LED           3V3(OUT)               36 TFT backlight

### SPI0 mapping

``` text
GP16 = SPI0 RX   / MISO
GP17 = SPI0 CSn  / TFT CS
GP18 = SPI0 SCK  / TFT SCK
GP19 = SPI0 TX   / MOSI
GP20 = GPIO      / TFT DC
GP21 = GPIO      / TFT RESET
```

### Power

``` text
Pico W Pin 36 — 3V3(OUT)
        |
        +---- TFT VCC
        |
        +---- TFT LED

Pico W Pin 23 — GND
        |
        +---- TFT GND
```

Important: GP numbers and physical pin numbers are different. Example:
**GP18 is physical pin 24**.

## 4. Unused Pins

Touch is not used:

``` text
T_CLK
T_CS
T_DIN
T_DO
T_IRQ
```

microSD is also out of scope for the first version.

## 5. Display Assumptions

-   Resolution: 240×320
-   Interface: SPI
-   Default orientation: portrait
-   No touch

**Implementation note:** verify the exact TFT controller on the physical
module (for example, ILI9341) before finalizing the display driver.

## 6. View 1 --- Large Clock

``` text
+------------------------+
|                        |
|        15:42           |
|           36           |
|                        |
|       SATURDAY         |
|      05/09/2026        |
|                        |
+------------------------+
```

Requirements:

-   HH:MM should use the largest practical font.
-   Seconds are smaller.
-   Show weekday and Gregorian date.
-   Avoid full-screen redraw every second to reduce flicker.

## 7. View 2 --- Calendar

``` text
+------------------------+
|     SEPTEMBER 2026     |
| Mo Tu We Th Fr Sa Su   |
|     1  2  3  4  5  6  |
|  7  8  9 10 11 12 13  |
| 14 15 16 17 18 19 20  |
| 21 22 23 24 25 26 27  |
| 28 29 30              |
|                        |
| Today: 05/09/2026      |
+------------------------+
```

Requirements:

-   Full current month
-   Correct weekday placement
-   Leap-year support
-   Highlight today
-   Layout optimized for 240×320

Future universal-calendar features: - Vietnamese lunar date - Can Chi -
Solar terms - Vietnamese holidays

## 8. View Switching

No touch is available, so start with automatic switching:

``` text
Clock View
    |
    | configurable interval
    v
Calendar View
    |
    | configurable interval
    v
Clock View
```

Initial suggestion: - Clock: 10 seconds - Calendar: 10 seconds

Keep these values configurable. A push button can be added later.

## 9. Suggested Software Structure

``` text
src/
├── main
├── config
├── display
│   ├── tft_driver
│   └── fonts
├── time
│   └── clock
├── calendar
│   ├── gregorian
│   └── lunar          # phase 2
└── ui
    ├── clock_view
    └── calendar_view
```

-   `config`: GPIO, SPI speed, screen dimensions, view intervals
-   `display`: TFT initialization and drawing
-   `time`: current time/date source
-   `calendar`: calendar calculations
-   `clock_view`: large clock renderer
-   `calendar_view`: month renderer
-   `main`: initialization and view state machine

## 10. Hardware Configuration Source of Truth

``` text
TFT_SPI       = SPI0

TFT_MISO      = GP16
TFT_CS        = GP17
TFT_SCK       = GP18
TFT_MOSI      = GP19
TFT_DC        = GP20
TFT_RST       = GP21

TFT_VCC       = 3V3_OUT
TFT_LED       = 3V3_OUT
TFT_GND       = GND
```

Do not change these GPIO assignments in software unless the physical
wiring is also changed.

## 11. Time Strategy

### Initial version

Maintain time while the Pico W is powered. Wi-Fi/NTP can later provide
current network time.

### Recommended final version

Add a DS3231 RTC:

``` text
Internet / NTP
      |
      v
   Pico W
      |
      +---- sync ----> DS3231
      |
      +---- SPI -----> TFT
```

Use Vietnam timezone (`UTC+7`). DS3231 can retain time while power is
removed; NTP can periodically correct it when Wi-Fi is available.

## 12. Development Milestones

### Phase 1 --- Display Bring-up

-   Initialize SPI0
-   Initialize TFT
-   Clear screen
-   Draw test text/shapes
-   Verify orientation and colors

### Phase 2 --- Clock

-   Current date/time
-   Large HH:MM
-   Seconds, weekday, date
-   Reduce redraw/flicker

### Phase 3 --- Gregorian Calendar

-   Generate current month
-   Calculate first weekday
-   Handle month lengths and leap years
-   Highlight today

### Phase 4 --- Two-view UI

-   Clock/Calendar state machine
-   Automatic switching
-   Configurable timing

### Phase 5 --- Universal Calendar

-   Vietnamese lunar calendar
-   Can Chi
-   Solar terms
-   Holidays

### Phase 6 --- Accurate Time

-   DS3231 and/or NTP
-   Vietnam UTC+7
-   Correct time after restart

## 13. Acceptance Criteria

First usable version is complete when:

-   Pico W boots reliably
-   TFT initializes automatically
-   Large clock is clearly readable
-   Date and weekday are correct
-   Calendar shows the correct month
-   Today is highlighted
-   Clock and Calendar automatically switch
-   No touch input is required
-   Application can run continuously without instability

## 14. Handoff Notes

1.  Current SPI bus is **SPI0 on GP16--GP19**.
2.  `GP20` and `GP21` are GPIOs for `DC` and `RESET`.
3.  TFT `VCC` and `LED` share Pico W `3V3(OUT)` in the current wiring.
4.  Touch is out of scope.
5.  microSD is out of scope for v1.
6.  Verify the exact TFT controller before choosing the driver.
7.  Prioritize a clean two-view UI over additional features.
