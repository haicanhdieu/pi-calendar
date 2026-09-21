# Epic 2 Context: Audible Alert Occurrence and Resolution

Epic 2 adds audible alert behavior to the existing cooperative Pico W clock loop. Story 2.1 owns only the device buzzer adapter and composition-root construction; scheduler, active-alert UI, stop, postpone, auto-stop, collision, persistence, and device evidence remain later stories.

## Constraints

- HW-508 signal is GP15, active-high, 3.3 V only; wiring is documented in `docs/hardware_configuration.md`.
- Buzzer cadence is 180 ms high / 220 ms low and must use wrap-safe `ticks_add`/`ticks_diff`.
- Device imports stay in `src/device`; pure alert code must remain free of `machine`, `network`, and `ntptime` imports.
- Port construction drives low before exposure. Failures return named secret-free results, mark output unknown, attempt one best-effort low, and require fresh initialization before retry.
- Main loop remains cooperative; this story does not make App own alert state or tick the port during active alerts.

## Relevant code

- `src/config.py` -- named hardware and timing constants.
- `main.py` -- composition root; injects configured buzzer port.
- `src/ticks.py` -- host-testable wrap-safe tick helpers.
- `docs/hardware_configuration.md` -- authoritative HW-508 wiring and safety notes.
- `tests/` -- host pytest suite; hardware behavior remains unverified until flashed.
