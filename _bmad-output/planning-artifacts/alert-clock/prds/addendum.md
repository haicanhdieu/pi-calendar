# Alert Clock — Technical Addendum

## Hardware Research: Installed HW-508 Buzzer

Supplied image URL resolves to [Maker's Electronics HW-508 Passive Buzzer Module](https://makerselectronics.com/product/hw-508-passive-buzzer-module/), but it is not controlling for installed hardware. The installed board's physical silkscreen is `S`, `VCC`, `GND`, and it produced audible output from direct 3.3 V GP15 pulses on 2026-09-21. The physical board evidence overrides that vendor listing's `S`/`NC`/`-` passive-module pinout for this Device.

Other retailers use `HW-508` for both active and passive modules; module labels and online listings are therefore not sufficient to identify this board. Generic passive-module guidance identifies `S`, unused middle pin, and `-` ground ([ArduinoModules HW-508/KY-006 guide](https://arduinomodules.info/ky-006-passive-buzzer-module/)); it does not apply to installed `S`/`VCC`/`GND` board.

Before implementation/deployment:

1. Photograph module front/back and read exact pin silkscreen.
2. Retain observed direct-GPIO `tut` cadence: 180 ms high, 220 ms low, repeating while alert is active; low output silences it.
3. Confirm `S`, `VCC`, `GND` header order from physical board.
4. Measure current and verify safe 3.3 V GPIO-drive arrangement. Pico W GPIO is 3.3 V only; never expose GPIO to 5 V ([Raspberry Pi Pico datasheet](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf)).
5. Determine whether direct GPIO control is safe or module needs transistor/level arrangement. Record confirmed GPIO/wiring in `docs/hardware_configuration.md` only after physical wiring changes.
6. Flash Device and capture serial/device evidence for repeated cadence, Stop, Postpone, Auto-stop, and recoverability.

## UX Reference

Comparable mobile clock products expose multiple alarms, enable state, repeat days, and distinct stop/snooze actions. Google Clock documents alarm creation, repeat scheduling, and configurable snooze duration ([Google Clock Help](https://support.google.com/android/answer/2840926?hl=en)); Apple documents per-alarm repeat, label, and snooze settings ([Apple iPhone User Guide](https://support.apple.com/en-ie/guide/iphone/iph2909d3a74/ios)). These references informed requirements but do not set Device behavior beyond PRD decisions.
