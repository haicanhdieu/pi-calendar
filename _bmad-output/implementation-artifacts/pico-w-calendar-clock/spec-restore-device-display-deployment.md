---
title: 'Restore the flashed device display through a complete firmware deployment'
type: 'bugfix'
created: '2026-09-06'
status: 'done'
route: 'dispatch'
baseline_commit: '6f9dce5c3d33cd27a7ea01235cfb6d19ed5f6842'
review_loop_iteration: 0
context:
  - '{project-root}/docs/hardware_configuration.md'
  - '{project-root}/_bmad-output/planning-artifacts/pico-w-calendar-clock/architecture/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The connected Pico W's TFT is backlit white instead of showing the Clock. Inspection shows its filesystem contains an older `main.py` and `src/` tree, while the repository now contains later stories, and the recorded deployment shortcut copies only `main.py`. That can leave incompatible application files on-device and provides no visible screen checkpoint between controller initialization and the complete App composition.

**Approach:** Make deployment preserve the repository's `main.py` plus complete `src/` package layout, add a deliberately small boot-screen checkpoint immediately after successful TFT initialization, and update the supported deployment instructions. Flash the connected device without deleting unrelated files, reset it, and capture the observable serial/display result.

## Boundaries & Constraints

**Always:** Preserve documented SPI0 GPIO assignments, 40 MHz mode 0, logical 320×240 geometry, and MADCTL `0xA8`. Keep device imports at the hardware/composition boundary. The display checkpoint must run after `ILI9341` construction and before RTC, network-worker, or App setup; it must use the existing adapter/driver and have a finite, short dwell before the Clock loop. Deploy `main.py` and `src/` recursively with repository-relative paths, then reset; do not remove files from the Pico as part of this repair. Treat device behavior as observed only when serial output or the user confirms it.

**Never:** Do not alter panel pins, controller type, SPI mode, MADCTL, fonts, calendar behavior, Wi-Fi credentials, or the current NTP worker as a speculative white-screen fix. Do not claim host tests prove the physical TFT.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Complete matching deployment | Local `main.py` and recursive `src/` copied to Pico | Reset reaches a visible diagnostic checkpoint and then the Clock/App loop | Serial logs identify the boot phase |
| App composition failure after display init | Controller initialized; later construction/import/runtime failure | Checkpoint remains visible and serial/fatal handler reports the error | Onboard LED retains the existing fatal blink signal |
| Panel transport failure | No checkpoint observed after a matching deployment | No hardware settings are changed automatically | Report transport/controller/wiring as an on-device follow-up |
| Stale device files | Existing older package files | Recursive copy overwrites matching firmware paths only | Unrelated device files are preserved |

</frozen-after-approval>

## Code Map

- `main.py` -- Composition root; all current source imports occur before its fatal handler, `ILI9341` initializes around lines 38–43, and the first normal render is deferred to `App.run_forever`. Add the bounded post-init visual checkpoint and ensure its imports remain compatible with the device.
- `src/device/display/splash.py` -- Existing, driver-level splash renderer; reuse or replace its content only as needed for an unmistakable boot checkpoint through the established ILI9341 API.
- `src/device/display/ili9341.py` -- Existing tested reset/init/window/fill implementation. Reuse unchanged; its config matches the hardware source of truth.
- `src/config.py` and `docs/hardware_configuration.md` -- Canonical pin, SPI, geometry, orientation and source reference; do not change hardware values.
- `_bmad-output/planning-artifacts/pico-w-calendar-clock/briefs/addendum.md` -- Contains the obsolete main-only `mpremote` deployment example; update it to recursive package deployment and a reset/observation procedure.
- `tests/` -- Host suite proves app/display-port behavior but cannot run `machine`; add only host-testable coverage for new pure/checkpoint selection logic if one is introduced.
- Connected Pico W `/dev/cu.usbmodem1101` -- Read inspection found MicroPython v1.20 and an older firmware composition; deployment verification target, not a filesystem-cleanup target.

## Tasks & Acceptance

**Execution:**
- [x] `main.py` and, if needed, `src/device/display/splash.py` -- Show a bounded, high-contrast boot checkpoint after TFT initialization and before App dependencies -- distinguishes display transport from later boot failures.
- [x] `_bmad-output/planning-artifacts/pico-w-calendar-clock/briefs/addendum.md` -- Replace the main-only command with recursive `src/` plus `main.py` deployment, reset, and serial/display observation instructions -- prevents another mismatched device tree.
- [x] Connected Pico W -- Copy the current firmware tree without deletion, reset, inspect device file layout and serial boot output -- applies and documents the repair outcome.
- [x] `tests/` -- Run the complete host suite; add focused coverage only if new host-importable behavior is introduced -- protects existing pure logic.

**Acceptance Criteria:**
- Given the specified Pico W and current repository tree, when the supported deployment procedure runs, then the device has the current `main.py` and a recursive `src/` tree with imports resolvable at their repository-relative paths.
- Given a working TFT initialization, when the device starts, then a visible boot checkpoint is sent before the Clock/App composition begins and disappears into the normal Clock loop within its bounded dwell.
- Given a failure after TFT initialization, when the device starts, then the checkpoint and existing serial/LED fatal diagnostics make the boundary observable rather than silently changing display configuration.
- Given the repository's documented hardware wiring, when this repair is implemented, then its pin map, SPI settings, and MADCTL value remain unchanged.

## Implementation Notes

- Host implementation and verification completed: `uv run pytest -q` passed 133 tests and `git diff --cached --check` passed.
- Device deployment completed (2026-09-06 white-screen follow-up on `/dev/cu.usbmodem1101`): removed junk nested `:src/src` (~94 KB from a prior recursive copy nesting), redeployed `.py`-only into `:src` + `:main.py`, hard reset. Serial after reset: `Initializing SPI0 TFT + App loop` → `TFT initialized; showing boot checkpoint` → `App loop starting (Clock view)` with no traceback/MemoryError. `fs tree` shows complete outer `src/` (bootstrap/color/coordinator present); nested junk gone; ~556 KB free. Physical TFT still requires user eyes — if white persists with this serial path, treat as transport/wiring follow-up (no pin/SPI/MADCTL changes).

## Spec Change Log

- 2026-09-06: White-screen incident after Forest & Amber deploy traced to messy recursive flash (space exhaustion / nested `:src/src`), not palette seeds. Clean `.py`-only redeploy + junk nested tree removal; serial proves boot checkpoint + App loop.

## Review Triage Log

- `false` — Device file-content verification: successful `mpremote fs cp` overwrites matching paths, which is the specified deployment action; the spec requires a post-copy layout inspection, not a device-side content-hash protocol. `fs tree` is used only to confirm the required path layout.
- `false` — Retained legacy modules: the frozen matrix requires overwriting matching firmware paths while preserving unrelated device files. Nested `:src/src` is a deploy artifact (not application data); after the white-screen/space incident it was removed as junk. Unrelated files such as `:secrets.py` remain untouched.
- `low` — Serial observation procedure: the deployment text requests an observation but does not give a command for attaching a serial console across reset. A small documentation clarification can make the checkpoint check repeatable.
- `medium` — Splash renderer coverage: changing `TFT READY` output has no host test, so regressions in the checkpoint's high-contrast render are not caught by the host suite.
- `medium` — Startup checkpoint sequence coverage: no host test exercises `main.py`'s new post-init render/sleep ordering, so moving or removing the checkpoint would pass the current suite.

## Design Notes

The evidence points to deployment/version skew, not a panel-protocol regression: the current ILI9341 driver retains the original reset, initialization, RGB565, and window-write path, and its hardware constants match `docs/hardware_configuration.md`. The checkpoint is intentionally downstream of that initialization: seeing it proves transport and local rendering, while not seeing it leaves controller/wiring as a measured follow-up instead of a code guess.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all host tests pass.
- `mpremote connect /dev/cu.usbmodem1101 fs cp -r src :src` and `mpremote connect /dev/cu.usbmodem1101 fs cp main.py :main.py` -- expected: current package paths copied without a delete operation.
- `mpremote connect /dev/cu.usbmodem1101 reset` and `mpremote connect /dev/cu.usbmodem1101 fs tree :` -- expected: rebooted target retains `main.py` and complete `src/` tree.

**Manual checks (if no CLI):**
- Watch the TFT through reset: a short boot screen followed by Clock proves the display boundary; if it remains white, retain serial output and report that hardware/controller investigation is needed.
