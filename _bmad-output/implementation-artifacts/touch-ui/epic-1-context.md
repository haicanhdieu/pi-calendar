# Epic 1 Context: Remove Always-On Status, Stand Up Touch Hardware Ports

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Remove network information from the ambient Clock and Calendar rotation so the display is glanceable by default, while establishing minimal, testable touch and reboot hardware boundaries. This leaves a shippable cleanup and the substrate later touch surfaces need, without exposing a touch interaction yet.

## Stories

- Story 1.1: Remove always-on network status overlay from Rotation
- Story 1.2: Add TouchPort and RebootPort hardware adapters

## Requirements & Constraints

- Rotation must never render Setup AP SSID/gateway text or a station IP in either Clock or Calendar view. Preserve the existing UNSYNCED badge and the App-held reduced network status (`kind`/`ssid`/`ip`); only remove its normal-rotation rendering.
- Add a synchronous, polled `TouchPort.read()` called once per `App.step()`. It returns `(edge_down, x, y)` only for a new contact edge; held contact produces no further edge until release. It performs bounded multi-sample outlier/noise rejection internally, with no interrupt handling, queue, mailbox, or asynchronous machinery. `TOUCH_IRQ` remains named but unused.
- Every touch read must safely hand SPI0 from TFT to XPT2046-compatible touch and back: deselect TFT CS, select touch CS, use at most 2 MHz, transfer, restore the configured TFT baudrate, deselect touch CS, and reselect TFT CS. TouchPort exclusively owns this sequence; the display port must not know touch exists.
- Coordinates reported by the port are raw pixel coordinates. The port neither knows UI targets nor decides surface transitions; later pure UI logic will hit-test those coordinates against the named target rectangles.
- Add `RebootPort.reset()` as the reboot boundary. Its production implementation invokes `machine.reset()` through `main.py`; host fakes record reset calls.
- AppState must gain `active_surface` (`rotation`, `bar`, or `settings`), `surface_deadline`, and `settings_status_snapshot`; only App may commit replacements. These fields are substrate only in this epic.
- Add one `TOUCH_IDLE_TIMEOUT_MS = 15000` shared by future Bar and Settings surfaces, plus named bar-animation/frame-pacing, tap-target-size, and press-flash-duration constants. Touch-related modules must not embed literal durations or pixel rectangles. Tap targets must be generous enough for a fingertip and larger than their visible controls.
- Do not change the Clock/Calendar rotation cadence, their content, physical pin assignments, or the existing display-port boundary. No Bar, Settings screen, touch-triggered state transition, or reboot UI is exposed in this epic.
- Keep pure logic importable under CPython: no `machine`, `network`, or other device imports outside device/main boundaries. Host tests prove logic and fakes only; physical SPI handoff, touch behavior, and display behavior require flashed-device evidence.

## Technical Decisions

- Maintain the functional-core/imperative-shell boundary: App is the single product-state writer and caller of ports; device adapters contain hardware access. Follow existing minimal Port conventions.
- Keep `Ili9341DisplayPort` untouched with respect to touch chip select and protocol ownership. This avoids independent chip-select toggles on the shared bus and protects TFT transfers from touch-read corruption.
- `NetworkCoordinator` remains the sole WLAN/HTTP owner and emits events; App continues reducing those events into the single network-status state. The wifi-config display requirement is superseded: Settings will later render an entry-time snapshot, not a continuously drawn overlay.
- Keep the existing cooperative loop ordering intact while preparing state for the later touch insertion. Future touch polling belongs at step 0, before sync-result consumption; rotation dwell will later be gated by `active_surface`.
- Display work remains through `DisplayPort` primitives (`fill_rect`, `draw_text`, `measure_text`) with RGB565 and stable font IDs. Do not introduce a full framebuffer or let a hardware adapter mutate display/App state.
- Locate named bar, gear, and reboot hit-target geometry helpers alongside the existing badge geometry helper in UI components; hit-testing belongs to future pure touch state, not TouchPort.
- Use MicroPython tick helpers and configured durations for future deadlines rather than wall time. Preserve the adapter's bounded, synchronous behavior so it fits the cooperative App loop.

## UX & Interaction Patterns

- Ambient Rotation remains visually unchanged except for removal of network status: Clock/Calendar content and the UNSYNCED badge continue as before.
- The future Bar and Settings controls need fingertip-sized targets. The only intended gesture is a single tap; debounce/palm-rejection across calls is explicitly deferred, beyond per-read sample rejection.
- Retain the forthcoming UI's flat instrument-panel constraints: no fullscreen framebuffer, scrim, or newly introduced persistent status treatment is implied by the hardware groundwork.
- The absence of the status overlay is intentional, not a failure-state signal: network details remain available as retained App state for the later explicit, on-demand Settings surface.

## Cross-Story Dependencies

- Story 1.2 supplies the ports, state fields, timeout and geometry constants consumed by Epic 2's pure surface transitions and Bar rendering, and Epic 3's Settings/Reboot flow.
- Story 1.1 preserves the App-held network status that Epic 3 snapshots when Settings opens, while removing the obsolete rotation overlay path.
