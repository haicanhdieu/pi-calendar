# Story 2.9 Flashed-Device Evidence

Date: 2026-09-21
Device: Raspberry Pi Pico W
Port: `/dev/cu.usbmodem1101`
Deploy command: `uv run tools/deploy.py --port /dev/cu.usbmodem1101`

## Observed

- Deploy command completed far enough to reset the board; subsequent serial capture reached application boot.
- Firmware query returned MicroPython `1.20.0`, machine `Raspberry Pi Pico W with RP2040`, `_mpy=4358`.
- Serial capture after soft reboot returned:

```text
MPY: soft reboot
Initializing SPI0 TFT + App loop
TFT initialized; showing boot checkpoint
TFT checkpoint complete; app construction
App loop starting (Clock view)
station_assets_ready
```

- Device filesystem listed deployed `src/app.mpy` and project source directories.

## Not observed

- No audible buzzer cadence measurement or audio observation.
- No display photograph or visual confirmation of `ALERT`, occurrence time, `STOP`, `POSTPONE`, or `UNSYNCED`.
- No touch calibration, STOP, or POSTPONE interaction evidence.
- No five-minute auto-stop observation.
- No collision, reboot/power-loss persistence, overdue skip, Wi-Fi-unavailable, or browser-during-alert evidence.

## Status

Partial device evidence only. Story 2.9 remains blocked pending direct observation and capture of listed hardware behaviors. No unobserved hardware behavior is claimed.
