# Epic 2 Context: Automatic Gregorian Calendar Companion

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Deliver a correct, glanceable Gregorian month grid that appears automatically beside the primary Clock: Minh sees today's month with weekday alignment and a clear today highlight, without any input, while Clock remains the dominant view through predictable timed rotation and clean handling of midnight and month boundaries.

## Stories

- Story 2.1: Generate a correct Gregorian month model
- Story 2.2: Render the current-month Calendar view
- Story 2.3: Rotate views and handle local-date transitions

## Requirements & Constraints

- Calendar shows the current Gregorian month as a Monday-first seven-column grid with correct weekday placement, leap-year and month-length rules, adjacent-month overflow days, and today's date highlighted.
- With no user input in v1, the device boots to Clock and plain-cuts between Clock and Calendar using configurable, clock-dominant dwells (defaults: 30s Clock, 8s Calendar). Do not enter Calendar until a valid local time exists; if Clock dwell expires while time is still invalid, stay on Clock.
- Local date line and today highlight must update at local midnight. If the month changes during Calendar dwell, cut back to Clock, reset Clock dwell, and build the new grid only on the next Calendar entry—never mid-dwell.
- Both views show the all-caps text `UNSYNCED` whenever time trust is unsynced; when synced, show no badge and reserve no placeholder space. Badge presence must not reflow other content; communicate degraded trust with the text, not color alone.
- All user-facing local dates/times derive from stored UTC via fixed Asia/Ho_Chi_Minh (UTC+07:00, no DST). Wall-clock values must not schedule elapsed work; use wrap-safe tick deadlines for dwells and related scheduling.
- Pure calendar, time, and view-state logic must run under CPython and MicroPython without hardware imports; host tests use `uv run pytest`. Continuous render path stays memory-bounded: dirty-region redraws, no full 320×240×16-bit framebuffer, no per-second allocation on the steady-state path.
- v1 has no buttons, touch, remote control, settings UI, alarm, lunar display, or other input affordance. Lunar enrichment is deferred but the month-cell contract must leave room for later annotations without rewriting callers.

## Technical Decisions

- Functional core / imperative shell: calendar math and view-state decisions are pure; a single-threaded App loop is the sole writer of app state, active view, and deadlines. Renderers consume snapshots and keep draw caches only.
- Calendar core returns a `MonthGrid` of Monday-first weeks. Each `DayCell` carries Gregorian date, `in_month`, `is_today`, and an ordered collection of semantic `CalendarAnnotation(kind, value)` records. Annotation kinds are lowercase kebab-case and owned centrally; v1 emits an empty collection. Renderers own display formatting.
- Gregorian weekday index `0` is Monday. UI string formatting stays in renderers, not in the calendar model.
- Drawing goes through one `DisplayPort` (clipped half-open pixel rects, RGB565, stable font IDs). Each renderer invalidates its prior-value cache on view entry; full-view redraw is allowed on entry/invalidation, not as a continuous framebuffer.
- `UiCompositor` owns shared badge visibility: on change, invalidate the active base view so pixels restore, then draw `UNSYNCED` last at the fixed top-right.
- App loop event order: consume adapter results → derive snapshot → handle date/month rollover → handle view deadline → render base view → render status layer.
- Dwell durations and palette/layout constants live as named config values, not magic numbers in behavior modules. Diagnostics may log view transitions concisely; no telemetry or persistent log in v1.

## UX & Interaction Patterns

- Instrument-panel palette on 320×240 landscape: background `#031406`, primary `#3dff7a`, secondary `#1c6b38`; orange `#ff6b3d` reserved exclusively for the unsynced badge.
- Calendar layout: 16px uppercase month/year label; Monday-first weekday header; seven-column day grid; 10px/12px frame padding; 2px gaps; 14px day cells (header ~11px secondary). Today: 3px rounded primary fill with background-colored text. Adjacent-month overflow: secondary green.
- Badge: 10px all-caps `UNSYNCED`, 3px rounded, fixed top-right, identical on Clock and Calendar.
- Only transition is a plain cut Clock → Calendar → Clock; no animation, icons, gradients, cards, seven-segment font, themes, or extra chrome that would shrink type sizes. Preserve desk-distance legibility (~0.5–1 m) under normal lighting.

## Cross-Story Dependencies

- Depends on Epic 1 delivering a trusted local `TimeSnapshot`, Clock as boot/default view, shared unsynced badge/compositor behavior, and tick-based App scheduling—Calendar rotation and midnight/month rules consume that foundation.
- Within this epic: month model (2.1) feeds Calendar rendering (2.2); view rotation and rollover policy (2.3) gate when the grid is built and when today/month updates apply. Annotation-ready cell shape in 2.1 is the forward hook for deferred lunar work, not a v1 display feature.
