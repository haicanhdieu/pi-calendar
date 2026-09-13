# Epic 2 Context: Touch-Reveal Bar

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Make the ambient Clock/Calendar display touch-responsive without making controls permanent: a touch reveals a bottom Bar with the Settings gear, pauses Rotation, and reliably returns to the chrome-free Rotation surface after inactivity or an outside tap. The Bar must provide immediate acknowledgement and animate smoothly within the display constraints of the Pico W.

## Stories

- Story 2.1: Pure touch_state transitions for rotation ⇄ bar
- Story 2.2: Wire touch polling into App.step() and render the Bar overlay
- Story 2.3: Auto-retract Bar on idle timeout or outside tap

## Requirements & Constraints

- A touch-down anywhere during `rotation` reveals the Bar and starts the shared 15-second idle timeout. While the Bar is active, Clock/Calendar dwell switching does not run.
- With no new touch through `TOUCH_IDLE_TIMEOUT_MS`, return to `rotation`; an edge-down touch outside the Bar or outside its gear target also retracts immediately. Tapping the gear advances to Settings rather than retracting.
- Returning to Rotation preserves the Clock or Calendar view that was shown before interruption, but gives that view a freshly armed dwell deadline.
- The Bar is a full-width, bottom-docked 36px strip that slides up in roughly 200–300ms. It is an icon-list container, with the one v1 gear item centered; adding icons later must not require state-machine restructuring.
- Keep the underlying base view unresized and undimmed. Do not add a scrim, shadow, back/close affordance, or any gesture beyond a single tap.
- Every tap on the gear needs a brief Press Flash before its ensuing transition. Its hit target must be generous enough for a fingertip and larger than the rendered glyph.
- The animation must use bounded dirty-region/incremental rendering, without full-framebuffer redraw, visible blanking, or stutter. Exact pacing needs on-device profiling.
- Touch debouncing/palm rejection beyond the port's per-read outlier filtering is deliberately out of scope.

## Technical Decisions

- Keep `src/ui/touch_state.py` pure and device-import-free, shaped like the existing view-state logic. It receives explicit surface, time, touch, and hit-target inputs, and returns surface decisions for `rotation`, `bar`, and `settings`.
- `App` is the only writer of `AppState`. It owns `active_surface` and `surface_deadline`; the deadline is set only on entering `bar` or `settings` and never renewed while that surface remains active.
- Insert touch processing as step 0 of `App.step()`, before sync-result consumption or sync enqueueing: call `TouchPort.read()` once, route an edge-down touch through pure hit testing/state transition logic, then commit the result before later steps.
- Gate the existing view-dwell transition on `active_surface == "rotation"`; skip it entirely for Bar and Settings rather than accumulating or deferring elapsed dwell time.
- `TouchPort` remains the sole SPI0 touch/display handoff owner and exposes only raw edge coordinates. It knows no UI target rectangles; hit tests use named component helpers.
- Keep every timeout, animation duration/frame cadence, geometry, tap-target size, and press-flash duration as named `config.py` constants. Use tick-safe time arithmetic (`ticks_ms`, `ticks_add`, `ticks_diff`) for deadlines.
- Render the Bar only in `UiCompositor.render()` as a draw-last overlay after the frozen base view, analogous to the UNSYNCED badge; it is not an `active_view`. Maintain one Bar draw call site and invalidate its prior region when visibility changes.
- Draw solely through `DisplayPort` primitives (`fill_rect`, `draw_text`, `measure_text`) with RGB565/stable font IDs and reusable bounded buffers.

## UX & Interaction Patterns

- The Bar is a flat `#141414` panel over the existing `#0a0a0a` screen, not elevation. It carries the only permitted icon: a hard-edged, filled eight-tooth gear with a punched center hole.
- The gear rests in amber (`digit-secondary`); Press Flash is `#ffe9b8` and is transient only. Red remains reserved for the UNSYNCED badge.
- The Bar docks over the bottom edge while leaving the visible Clock/Calendar content otherwise unchanged. Its reverse transition is the only delay on an outside-tap dismissal.

## Cross-Story Dependencies

- Epic 1 provides `TouchPort`, `AppState` surface fields, the shared timeout/configuration constants, and named Bar/gear tap-target helpers.
- Story 2.3 must leave the gear transition available for Epic 3's Settings entry; Epic 3 supplies the Settings renderer and reboot flow.
