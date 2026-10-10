# Paired buzzer cadence verification — 2026-10-10

User confirmed the direct-GPIO bench pattern audible and requested the same pattern for alerts.

Cadence: GP15 active-high, 180 ms pulses, successive low gaps of 220, 650, 220, and 1,400 ms. Repeats `tut.tut...tut.tut......`. Wiring unchanged.

Host evidence: `uv run pytest -q tests/test_buzzer_port.py tests/test_alert_app.py tests/test_alert_scheduler.py tests/test_alert_view.py` — 55 passed. Includes pattern repetition over timer wrap and dismiss during a pair pause followed by restart from first pulse.

Device: `/dev/cu.usbmodem101`, Raspberry Pi Pico W, MicroPython 1.20.0, `_mpy=4358`. Updated only `src/config.py`, `src/device/buzzer_port.py`, and `src/device/clock_mode.mpy`; clock module compiled with `uv tool run --from mpy-cross==1.20.0 mpy-cross -O3 src/device/clock_mode.py -o <staging>/clock_mode.mpy`. Device config matched the expected baseline before copying. Original files backed up outside repository in `/var/folders/83/64w45hb12zj0qcp7nfd2tnw90crlhh/T/buzzer-pattern-omx9qpro/`.

Device adapter exercised for 6.5 seconds. Serial reported initialization `ok`, pattern `(220, 650, 220, 1400)`, edges at 0/183/407/590/1241/1424/1648/1830/3230 ms, then repeated. Final silence result `silent`; reset command succeeded. Serial timing confirms actual adapter transitions with 5 ms polling jitter. Full scheduled alert, touch dismissal, and post-reset UI behavior were not observed in this test. Electrical validation remains open as documented in hardware configuration.
