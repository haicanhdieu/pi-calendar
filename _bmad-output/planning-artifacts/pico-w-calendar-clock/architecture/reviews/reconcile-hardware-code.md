# Hardware, Structure, and Current-Code Reconciliation

**Reviewed inputs:** `docs/hardware_configuration.md`, `docs/pico_w_calendar_clock_handoff.md`, `_bmad-output/planning-artifacts/pico-w-calendar-clock/architecture/project-structure.md`, and `main.py`  
**Artifact checked:** `ARCHITECTURE-SPINE.md`  
**Verdict:** **Two spine gaps and two implementation conflicts need explicit handling.** The GPIO map, orientation, memory posture, pure/device split, v1 input scope, timezone, controller uncertainty, and deployment shape otherwise landed correctly.

## Findings

### HIGH — The working SPI/display protocol baseline did not fully land

The spine binds SPI0, 40 MHz, GP16–GP21, logical `320×240`, and `MADCTL 0xA8`, but omits other choices on which the current display code depends:

- `main.py:314–322` initializes SPI mode 0 (`polarity=0`, `phase=0`).
- `main.py:213–214` selects 16-bit pixels (`COLMOD 0x55`) and the tested `MADCTL 0xA8` orientation.
- `main.py:228–254` establishes the existing primitive semantics: logical landscape coordinates; `fill_rect(x, y, width, height, color)`; clipping to the panel; inclusive controller window endpoints; RGB565 values written high byte first.

Two independently extracted display units could obey the spine while choosing a different SPI mode, pixel encoding, byte order, or rectangle convention. One can fail electrically; the others make the separately built renderer and adapter incompatible. These are not all controller-command-table internals: SPI mode, logical primitive semantics, and color ownership cross module boundaries.

**Recommended reconciliation:** Ratify SPI mode 0 in the hardware source of truth and spine seed. Add the narrow renderer/display-port contract identified by the adversarial review: logical `320×240` coordinates, width/height rectangles with clipping, and one owner for RGB888-design-token to RGB565-wire conversion. Treat the exact ILI9341 initialization/gamma command sequence as adapter-owned seed copied from `main.py`, not as a permanent AD; preserve it until a replacement passes a user-run flashed-device check.

### MEDIUM — The brownfield extraction transition is missing

The target convention says `main.py` is composition only and reusable code lives under `src/` (`project-structure.md:41–44`). The spine repeats that as a convention and structural seed. Current `main.py`, however, contains GPIO/configuration constants (`main.py:5–24`), the ILI9341 driver (`main.py:157–257`), font/render functions (`main.py:260–306`), composition (`main.py:309–337`), and the fatal boundary (`main.py:340–349`). This is a working bring-up monolith, not the stated target.

The project-structure source explicitly says not to migrate immediately and to move files only in an implementation task that verifies the device deployment layout (`project-structure.md:54–58`). The spine records the final layout and says device-only claims require a flashed-device check, but it does not identify extraction from `main.py` as a compatibility-preserving migration or identify the current code as the baseline.

**Recommended reconciliation:** Add a seed/transition note: implementation extracts the current driver and drawing primitives rather than replacing them wholesale; host checks bracket pure-code moves; the user flashes and verifies display initialization, orientation, colors, and import layout before the old monolithic paths are retired. This is structural seed, not a new architecture decision.

### MEDIUM — Current fatal handling conflicts with the spine’s runtime policy

The spine says recoverable network failure cannot stop rendering and that only display initialization failure is fatal to normal rendering. Current `main.py:340–349` catches every exception from all future work under `main()` and enters a permanent LED-blink loop. Once network, time, calendar, and rendering orchestration are added under the same `main()`, an expected adapter exception or incidental runtime defect can stop the clock through this blanket boundary.

The existing code does not yet violate a shipped clock path—it is only a display demo—but copying its top-level exception structure into the target app would conflict with AD-8 and the boundary-result convention.

**Recommended reconciliation:** Track this as an implementation migration requirement: scope fatal display initialization separately; convert expected network/time failures to explicit results before they reach the top boundary; decide deliberately whether unexpected programmer errors retain the LED-blink diagnostic. No new AD is necessary if AD-8 remains explicit.

### LOW — The current drawing code does not satisfy the recurring-allocation invariant

`main.py:186–193`, `228–254`, and `260–284` allocate command bytes, row buffers, and perform one rectangle transaction per lit glyph block. This is acceptable for the current one-shot splash, but must not be reused unchanged for the one-second clock update because AD-7 prohibits recurring allocation and requires reusable buffers/dirty regions.

**Recommended reconciliation:** Treat the current code as a bring-up/reference adapter only. During extraction, retain hardware initialization behavior while replacing per-update allocation with preallocated command/pixel buffers and measured dirty glyph updates. This is already governed by AD-7; add an implementation acceptance check rather than another spine decision.

## Source conflicts already resolved correctly

- The older handoff says portrait `240×320` and layouts optimized for that orientation (`handoff:84–89`, `115–137`). The newer hardware source records tested landscape `320×240` with `MADCTL 0xA8` (`hardware_configuration.md:15–26`), matching current code (`main.py:13–14`, `203–205`) and the spine. Treat the handoff orientation as superseded.
- The handoff’s suggested 10s/10s view dwell (`handoff:142–160`) is superseded by finalized UX and remains configurable in the spine. No architecture conflict.
- The handoff stages Wi-Fi/NTP as later work and recommends DS3231 eventually (`handoff:209–232`). The active v1 PRD makes NTP part of v1; the spine implements NTP now and defers DS3231 behind the correct time boundary. No architecture conflict.
- The project-structure convention includes `src/device/input/` as a general target, while v1 has no touch/button input. Omitting it from the spine’s v1 seed is correct and avoids implying an unused boundary.

## Load-bearing items that landed

- Exact GPIO ownership and SPI0/40 MHz mapping are preserved by the spine’s hardware-doc ownership rule and diagram.
- Landscape `320×240` and tested `MADCTL 0xA8` are preserved; controller identity remains honestly assumed.
- Hardware imports are confined to `main.py`/device adapters; pure calendar, time, and view-state code remains host-importable.
- Root `main.py`, reusable `src/`, host `tests/`, device adapter separation, and repository-relative deployment layout match the project-structure convention.
- No touch or microSD capability leaked into v1.
- Direct drawing, reduced recurring redraw, configurable dwell periods, UTC+7 conversion, and future DS3231 isolation are covered.

## Gate recommendation

Before finalizing, capture the SPI mode and renderer/display-port semantics, and add the brownfield extraction note. Keep the blanket fatal handler and allocation-heavy glyph path as explicit implementation migration work. No other load-bearing hardware/code divergence was found.
