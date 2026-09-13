---
title: 'Story 1.2: Add TouchPort and RebootPort hardware adapters'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_revision: '42d7ad28634ad55bc7080526f382604356634d2c'
baseline_commit: '42d7ad28634ad55bc7080526f382604356634d2c'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The touch overlay and device reset capability lack minimal hardware boundaries, so future UI code would need to know SPI chip-select details or import `machine` directly. The shared SPI0 bus must be safely handed between the TFT and XPT2046-compatible controller on every bounded touch poll.

**Approach:** Add device-layer `TouchPort` and `RebootPort` adapters, wire only their construction into `main.py`, and prepare AppState/configuration substrate without exposing touch-driven UI behavior.

## Boundaries & Constraints

**Always:** `TouchPort.read()` is a synchronous, bounded polling call that returns `(edge_down, x, y)` only for a fresh contact after release, uses bounded multi-sample rejection, and owns the complete TFT/touch SPI0 handoff. It restores the configured TFT baudrate and selects TFT again even when sampling fails. AppState remains App-owned; all new surface fields are initialized but not transitioned in this story. `RebootPort.reset()` is a device boundary whose production callback is `machine.reset()`.

**Never:** Do not change physical pin assignments, touch `TOUCH_IRQ` use, `Ili9341DisplayPort`, Clock/Calendar cadence, compositor behavior, or add touch polling to `App.step()`, hit-testing, Bar, Settings, or reboot UI. Do not introduce a touch queue, mailbox, interrupt handler, or device imports into App/UI/pure logic.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Fresh valid contact | Stable raw samples after a released state | First `read()` returns `(True, x, y)` in raw screen-pixel coordinates; held reads return `(False, None, None)` | No error expected |
| Release then contact | No-contact read followed by stable contact samples | A later contact is again reported as one fresh edge | No error expected |
| Noisy or unavailable samples | Outlier samples, invalid pressure, or SPI sample exception | Return no edge and retain a recoverable released/contact state as appropriate; bus is restored to TFT ownership | Transfer/sample failure must not leave touch selected or TFT at touch baudrate |
| Reset boundary | Host callback fake or production `machine.reset` callback | `reset()` invokes exactly its injected callback once | Host fake records call without resetting test process |

</intent-contract>

## Code Map

- `src/config.py` -- existing, hardware-documentation-aligned SPI0/pin constants (`TOUCH_CS`, `TOUCH_IRQ`, `SPI_BAUDRATE`, polarity, phase); add named touch-safe SPI, sampling, timeout, animation/frame, target-size, and flash constants without changing pins.
- `main.py` -- the only application composition root importing `machine`; currently constructs SPI0, TFT and `App`; instantiate the two device adapters using the existing SPI and TFT CS after display initialization, and pass only the reboot callback/boundary needed for later injection without polling them yet.
- `src/device/display/ili9341.py` -- owns the live TFT `cs` Pin on its display object; use its existing TFT CS rather than creating a competing pin. `src/device/display/adapter.py` is explicitly read-only and must stay touch-unaware.
- `src/device/clock_port.py` -- precedent for a minimal device-layer, duck-typed port with injected hardware dependency for host testing.
- `src/app.py` -- `AppState.__slots__` and initializer are the sole product-state substrate; add `active_surface`, `surface_deadline`, and `settings_status_snapshot` with Rotation defaults, but do not add a port import or change `step()` ordering.
- `tests/test_app_loop.py` -- existing host purity/AppState tests and fake-port conventions; extend for new state defaults and no device import regression.
- `tests/test_config_hardware_defaults.py` and `tests/test_display_boot_checkpoint.py` -- hardware/main AST regressions; preserve pin/SPI boot behavior while proving adapter composition.
- `docs/hardware_configuration.md` -- source of truth confirming shared SPI0 and GP22/GP26 wiring; read-only because no physical wiring changes occur.

## Tasks & Acceptance

**Execution:**
- [x] `src/config.py` -- add named touch transfer, sampling, shared idle-timeout, bar pacing/geometry, tap-target, and press-flash constants -- give future touch UI a single non-literal configuration source.
- [x] `src/device/touch_port.py` -- implement the injectable synchronous XPT2046-compatible poll adapter with multi-sample rejection, edge-only reporting, and exception-safe SPI0/CS restoration -- isolate shared-bus ownership in one device boundary.
- [x] `src/device/reboot_port.py` -- implement a minimal callback-backed `reset()` port -- keep reset hardware outside App and allow host fakes.
- [x] `src/app.py` and `main.py` -- initialize AppState touch-surface substrate and compose production port adapters/callback without polling or exposing any surface -- establish later dependencies while preserving current loop behavior.
- [x] `tests/test_touch_port.py`, `tests/test_reboot_port.py`, `tests/test_app_loop.py`, and focused existing configuration/main tests -- add host fakes and assertions for edges, noisy samples, handoff ordering/restoration, reset callback, AppState defaults, and device-import boundaries -- prove the public boundaries without claiming Pico hardware observation.

**Acceptance Criteria:**
- Given stable contact samples after release, when `TouchPort.read()` runs, then it reports one edge with raw coordinates; repeated held reads emit no additional edge until a no-contact read and a new contact.
- Given every touch poll, when the adapter accesses SPI0, then TFT is deselected, touch is selected at no more than 2 MHz, sampling occurs, the configured TFT baudrate is restored, touch is deselected, and TFT is selected again, including after a sample failure.
- Given noisy/outlier or invalid touch samples, when `read()` evaluates them, then it returns no false touch edge and remains usable on the next poll.
- Given an App instance boots, when its state is inspected, then it has App-owned `active_surface == "rotation"`, a neutral `surface_deadline`, and a neutral `settings_status_snapshot`, with no change to rotation behavior.
- Given production composition, when a future caller invokes the reboot port, then its callback is `machine.reset`; given a host fake callback, it records exactly one reset invocation.
- Given the new substrate, when host modules import under CPython, then App/UI logic still imports without `machine`, `network`, or `ntptime`; `Ili9341DisplayPort` contains no touch-CS reference.

## Spec Change Log

## Review Triage Log

## Design Notes

The port accepts injected SPI, chip-select, and sampler-facing dependencies so host tests can observe bus order without importing MicroPython. XPT2046 protocol details remain contained in the device adapter; this story intentionally does not calibrate or hit-test coordinates because later pure UI logic owns that policy.

## Verification

**Commands:**
- `uv run pytest tests/test_touch_port.py tests/test_reboot_port.py tests/test_app_loop.py tests/test_config_hardware_defaults.py tests/test_display_boot_checkpoint.py` -- expected: focused adapter, state, composition, and purity coverage passes.
- `uv run pytest` -- expected: complete host suite passes.

**Manual checks:**
- Flash the board and capture serial/device evidence separately: verify an actual touch read leaves TFT rendering usable and never changes the documented pin assignments. Host tests cannot prove SPI electrical behavior or calibrated touch coordinates.

## Auto Run Result

Status: done

Implementation and host verification completed. The mandatory four-layer review could not be launched concurrently because the collaboration agent limit was already reached; per operator direction, a focused independent review was used instead. Its Pico heap/recovery findings were fixed and covered by a restore-failure test. The focused suite passed (28 tests) and the full host suite passed (309 tests). On-device SPI handoff behavior still needs flashed-device evidence.
