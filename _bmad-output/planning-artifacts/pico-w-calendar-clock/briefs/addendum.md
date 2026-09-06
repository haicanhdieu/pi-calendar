---
title: Pico W Universal Calendar & Clock — Brief Addendum
status: draft
created: 2026-09-05
updated: 2026-09-05
---

# Addendum

Detail that belongs downstream (PRD, architecture, test design) or that explains a decision the brief only states.

## Hardware configuration — source of truth

Reproduced from `docs/pico_w_calendar_clock_handoff.md` §10. These GPIO assignments must not be changed in software unless the physical wiring changes and the documentation is updated in the same change.

```text
TFT_SPI  = SPI0
TFT_MISO = GP16   (physical pin 21)
TFT_CS   = GP17   (physical pin 22)
TFT_SCK  = GP18   (physical pin 24)
TFT_MOSI = GP19   (physical pin 25)
TFT_DC   = GP20   (physical pin 26)
TFT_RST  = GP21   (physical pin 27)
TFT_VCC  = 3V3(OUT), physical pin 36
TFT_LED  = 3V3(OUT), physical pin 36
TFT_GND  = GND,      physical pin 23
```

GP numbers and physical pin numbers differ — GP18 is physical pin 24. Touch pins (`T_CLK`, `T_CS`, `T_DIN`, `T_DO`, `T_IRQ`) are unwired and out of scope. microSD is out of scope for v1.

The TFT backlight is tied directly to 3V3 rather than to a GPIO, so brightness is fixed and the display cannot be blanked in software. If dimming or a night mode is ever wanted, that is a wiring change (LED to a PWM-capable GPIO through a suitable transistor or current limit), not a firmware change.

`TFT_VCC` and `TFT_LED` share the Pico W 3V3 rail. Backlight current on these modules is not trivial; if display bring-up shows brownouts or resets under load, the shared rail is the first thing to measure.

## Push button — proposed wiring

Not yet fitted. Proposal: one momentary button between a free GPIO and GND, using the Pico's internal pull-up (`Pin(n, Pin.IN, Pin.PULL_UP)`), so the pin reads low when pressed and no external resistor is required. GP15 is a reasonable choice — it is clear of SPI0 (GP16–GP19) and clear of the DC/RST pair (GP20–GP21) — but the pin is not yet fixed and should be confirmed against the physical board before it is written into config.

Debouncing is required; a short lockout after an accepted edge is sufficient for a view-switch button and avoids timer-based debouncing in the main loop.

## Options considered and set aside

**C / Pico SDK instead of MicroPython.** Better SPI throughput, smaller and more predictable memory use, and materially better suited to the Phase 5 solar-term math on a chip without an FPU. Set aside because it requires building a host test harness before any calendar logic can be tested, and because the iteration loop is much slower for a project whose main uncertainty is visual layout. This is the decision most worth revisiting if Phase 5 performance disappoints.

**DS3231 RTC in v1 alongside NTP.** The most robust option: correct time with neither Wi-Fi nor power. Set aside as unnecessary for v1 once NTP was moved forward, since NTP covers the powered case and the device is expected to stay powered. The RTC's real job is retention across power loss, which is a Phase 6 concern.

**Keeping the 10s/10s auto-rotation with no button.** Ships exactly as specified in the handoff document and needs no additional hardware. Rejected on the grounds that a clock which shows a calendar on half of all glances has failed at its primary job.

## The acceptance-criteria contradiction, in full

`docs/pico_w_calendar_clock_handoff.md` §13 requires that "date and weekday are correct" for the first usable version. §11 places all time sources — NTP and DS3231 — in Phase 6, after the first usable version is declared complete in Phase 4.

With no time source, MicroPython's `time.localtime()` on a cold boot returns the RTC's power-on epoch (2021-01-01 on the RP2040 port), so the device would display a fixed wrong date after every power cycle. The stated acceptance criteria are therefore unreachable by Phases 1–4 as sequenced.

The resolution recorded in the brief is to move Wi-Fi NTP into v1. Any future re-plan that removes NTP from v1 must also amend §13, or the contradiction returns.

## Existing implementation — current state

`main.py` (349 lines, MicroPython) already contains:

- SPI0 setup and the pin constants above.
- A `color565` helper and a small named-colour palette.
- A `FONT_5X7` bitmap font as a dict of string-row tuples, with `draw_glyph`, `draw_text`, `text_width`, and `centered_text` helpers that scale glyphs by integer factors.
- An `ILI9341` class with reset, command/data framing, `set_window`, `fill_rect`, and `fill`.
- A `splash_screen` and a `main()` entry point.

Two conflicts with the handoff document, both unresolved:

1. **Controller identity is assumed.** The class is named `ILI9341` and its init sequence (0xB1, 0xB6, 0xC0, 0xC1, 0xC5, 0xC7, gamma tables 0xE0/0xE1) is an ILI9341 sequence, but the physical module was never probed. §5 of the handoff document explicitly flags this as something to verify.
2. **Orientation disagrees.** `main.py` sets `SCREEN_WIDTH = 320`, `SCREEN_HEIGHT = 240` and `_madctl()` returns a hardcoded `0xA8` (landscape). The handoff document §5 specifies portrait 240×320 and draws both view mockups in portrait.

The 5×7 scaled bitmap font is adequate for bring-up but will look coarse at the sizes the clock view needs. A dedicated large-digit glyph set for HH:MM is likely wanted before the clock view is considered finished; this is a UI-quality item, not a blocker.

`_madctl()` returning a constant means orientation is not configurable. If orientation is still genuinely open, it should become a config value rather than staying hardcoded.

## Layout notes for downstream UX work

The reading distance (one to three metres, at a glance) sets the type scale, not the screen size. HH:MM should be as large as the panel allows; seconds are secondary and can be small enough that they are legible only up close, since nobody reads seconds from across a room.

Seconds updating once per second means one region redraws 86,400 times a day. That region must be a tightly bounded dirty rect, both to avoid flicker (§6 of the handoff document) and to keep steady-state allocation near zero.

The seven-column calendar grid at 240 pixels wide gives roughly 34 pixels per column before margins, which is tight for a two-digit day plus a highlight treatment around today. At 320 wide it is comfortable. This is the practical argument in the orientation question and should be weighed against the handoff document's stated portrait default.

The time-trust indicator should be non-textual and ambient — a small mark that a user learns to ignore when everything is fine — rather than a message that competes with the time itself.

## Code conventions that follow from the MicroPython decision

MicroPython was chosen so that calendar logic runs unchanged under CPython on a laptop. That only holds if the logic stays importable off-device, which makes the following binding on implementation:

- Pure logic — calendar math, date arithmetic, view-state decisions, later the lunar conversion — must not import `machine`, `network`, `ntptime`, or any other MicroPython-only module. Those imports fail under CPython and take the whole test suite with them.
- Hardware access is confined to the display driver, the network layer, and the entry point. Anything that touches a pin, the SPI bus, or the radio lives there and nowhere else.
- Host tests run as `uv run pytest`; bare `pytest` runs outside the project environment. No suite exists yet — it should be created under `tests/` when the first calendar logic lands.

A convenient shortcut that reads the RTC or a pin from inside calendar code costs the entire testing rationale for choosing MicroPython in the first place.

## Deploying to the device

Use `mpremote` (`pipx install mpremote`) to copy the composition root and the
complete package tree without deleting anything already on the device. From the
repository root, with the Pico W at the documented serial path, run:

```sh
mpremote connect /dev/cu.usbmodem1101 fs cp -r src/* :src
mpremote connect /dev/cu.usbmodem1101 fs cp main.py :main.py
mpremote connect /dev/cu.usbmodem1101 reset
mpremote connect /dev/cu.usbmodem1101 fs tree :
```

To observe the reset interactively, attach the terminal first with
`mpremote connect /dev/cu.usbmodem1101 repl`, then press Ctrl-D to soft-reset
the Pico and watch its serial output and TFT. Use Ctrl-C to return to the REPL
after the Clock loop starts.

The tree must contain `main.py` and the recursive `src/` package paths used by
its imports; matching firmware files are overwritten, while unrelated device
files are preserved. The `src/*` form is intentional: when `:src` already
exists, copying the source directory itself would nest it as `:src/src`.
Watch the serial console and TFT through reset: `TFT
initialized; showing boot checkpoint`, a short high-contrast `TFT READY`
screen, then the Clock/App loop identifies a successful boundary. If no
checkpoint appears after this matching deployment, retain the serial output
and investigate the panel transport/controller/wiring rather than changing
hardware settings speculatively.

Firmware cannot be executed in the development environment. On-device behaviour is never observed by an agent working in this repository — it can only be reasoned about, flashed by the user, and reported back.

## Structuring the calendar module for the lunar phase

Recorded here because it is the one architectural constraint the brief asserts without justifying in detail.

The Gregorian month grid and the Vietnamese lunar calendar are different calendar systems that must be rendered into the same cell. If the month-grid generator returns bare day numbers, adding lunar dates later means changing its return type, its callers, and the renderer at once. If it returns a per-day record from the start — even one that initially carries only the Gregorian day number and a today flag — then the lunar phase adds fields to a record and a line to the renderer.

This costs nothing now. It is the difference between Phase 5 being an addition and Phase 5 being a rewrite, and it is the reason the brief keeps the lunar calendar in scope as an architectural concern while deferring it as a feature.

Solar-term computation should be treated as a once-per-day cached calculation from the outset, never as a per-render call.
