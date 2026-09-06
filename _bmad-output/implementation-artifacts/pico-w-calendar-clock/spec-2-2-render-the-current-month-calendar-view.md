---
title: 'Render the current-month Calendar view'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: '8af6852160869d2e8d04d614d9e69e034b48e9f0'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-2-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Story 2.1 delivered `MonthGrid`/`DayCell`, but there is no Calendar renderer or shared status compositor, so the device cannot show the glanceable month grid with today marked and the identical UNSYNCED badge.

**Approach:** Add a DisplayPort-only `CalendarView` that draws the uppercase month/year, Monday-first weekday header, and seven-column day grid from a supplied `MonthGrid`, plus a `UiCompositor` that owns badge visibility (invalidate base on change, draw `UNSYNCED` last); verify on host FakeDisplayPort without App rotation.

## Boundaries & Constraints

**Always:**
- Draw only through `DisplayPort`; palette/fonts/layout metrics from `src/config.py` (frame pad 10×12, gap 2px; month ~16px primary; weekday header ~11px secondary single letters `M T W T F S S`; day cells ~14px).
- In-month day text primary; adjacent overflow secondary; today: primary fill + background-colored text (bitmap fill may be rectangular approximating 3px round, same as badge).
- Month label format `SEPTEMBER 2026` (full English uppercase month + year); UI strings live only in the renderer.
- `UiCompositor` owns previous badge visibility; on change invalidate the active base view then draw badge last via `draw_unsynced_badge`; base renderers do not draw the badge.
- Each renderer invalidates prior-value cache on view entry / compositor-driven invalidate; full-view redraw allowed on entry; no full 320×240×16 framebuffer; no `machine`/`network`/`ntptime`/`src.device` in pure UI.
- `CalendarView.render(snapshot, grid)` consumes an already-built `MonthGrid` (caller builds via `build_month_grid`); do not embed App rotation/midnight policy.

**Never:**
- Do not implement Clock↔Calendar dwell rotation, midnight/month-rollover App policy (Story 2.3), lunar annotations, or NTP (1.5).
- Do not allocate a full framebuffer; do not change pin/SPI/MADCTL; do not claim on-device legibility from host runs.
- Do not put month/weekday strings in `src/calendar/`; do not start Story 2.3 work.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Synced Calendar entry | Valid local + MonthGrid for that month | Full bg; centered uppercase month/year; Mon-first `M…S` header; 7-col day grid with pad/gap; no badge | No error expected |
| Today + overflow | Grid with `is_today` + `in_month` False cells | Today cell primary fill + bg text; in-month primary text; overflow secondary text | No error expected |
| Unsynced Calendar | Same grid, `trust=unsynced` | Identical grid layout + compositor draws top-right orange `UNSYNCED` last | No crash |
| Badge hide after show | Badge was visible; now synced | Compositor invalidates base once, base restores pixels, no badge / no reserved slot | No error expected |
| Re-enter Calendar | `invalidate()` then render | Prior cache cleared; full redraw allowed; Fake ops only (no framebuffer) | No error expected |
| Pure UI import | Import `src.ui.calendar_view` / `compositor` under CPython | Succeeds; no forbidden hardware imports | Import failure = test fail |

</intent-contract>

## Code Map

- `src/ui/calendar_view.py` -- Create: `CalendarView(display)` with prior-value cache, `invalidate()`, `render(snapshot, grid)`; formats month label + weekday header + cells; DisplayPort only; no badge draw.
- `src/ui/compositor.py` -- Create: `UiCompositor(display)` owning `_prev_badge`; `render(base_view, snapshot, *args)` invalidates base on badge visibility change, calls `base_view.render(...)`, then `draw_unsynced_badge` last (AD-12).
- `src/ui/clock_view.py` -- Remove badge draw and badge-driven self-invalidate (lines ~5, ~182–184, ~348); leave dirty SS path; badge ownership moves to compositor. Keep `invalidate()`.
- `src/ui/components.py` -- Read-only reuse: `draw_unsynced_badge` / `badge_rect` remain the single badge geometry helper.
- `src/config.py` -- Add `FONT_MONTH` / `FONT_WEEKDAY` / `FONT_DAY` (or reuse DATE/BADGE scales if sizes match), `FONT_SCALES` entries, Calendar pad/gap/label-gap constants (`CALENDAR_PAD_Y=10`, `CALENDAR_PAD_X=12`, `CALENDAR_GAP=2`, etc.).
- `src/calendar/gregorian.py` -- Read-only: tests call `build_month_grid` to supply grids; renderer does not import device time.
- `src/app.py` -- Wire Clock refresh through `UiCompositor` so live Clock path also draws badge last; do not add Calendar rotation (2.3). Inject or construct compositor beside `clock_view`.
- `tests/test_clock_view.py` / `tests/test_app_loop.py` -- Update badge assertions to go through `UiCompositor` (Clock base no longer paints badge).
- `tests/test_calendar_view.py` -- Create: I/O matrix (layout, colors, today fill, overflow, compositor badge last, invalidate/re-entry, no framebuffer, UI purity including new modules).
- `_bmad-output/.../sprint-status.yaml` -- Set `2-2-…` through workflow statuses; leave `1-4`/`1-5` and keep `epic-2: in-progress`.

## Tasks & Acceptance

**Execution:**
- `src/config.py` -- Add Calendar layout/font constants -- single ownership of pad/gap/scales.
- `src/ui/compositor.py` -- Implement badge-owning `UiCompositor` -- AD-12 / FR4 shared status layer.
- `src/ui/calendar_view.py` -- Implement MonthGrid Calendar renderer -- FR5 / UX calendar chrome.
- `src/ui/clock_view.py` -- Stop drawing badge; rely on compositor -- identical badge on both views.
- `src/app.py` -- Route Clock paints through compositor -- live path matches AD-12 order (base then status).
- `tests/test_calendar_view.py` -- Cover I/O matrix + purity -- NFR3/NFR5 host proof.
- `tests/test_clock_view.py` + `tests/test_app_loop.py` -- Retarget badge tests to compositor -- keep suite green.
- `sprint-status.yaml` -- Reflect story progress per workflow -- tracking only.

**Acceptance Criteria:**
- Given a valid local snapshot and its MonthGrid, when Calendar is entered, then it renders the current uppercase month/year label, Monday-first weekday header, and seven-column day grid using 10px/12px frame padding and 2px gaps.
- Given Calendar cells, when they render, then in-month days use primary green, adjacent-month overflow uses secondary green, and today's cell has the specified 3px rounded primary fill with background-colored text.
- Given a Calendar view, when trust is unsynced, then the shared compositor draws the same fixed top-right UNSYNCED badge last; a badge visibility change invalidates the active base view so underlying pixels are restored.
- Given a display transition, when Calendar is re-entered, then its renderer invalidates its prior-value cache and may redraw the full view, while no full framebuffer is introduced.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 27 findings — high 0, medium 4, low 5, false 18, maybe-false 0
- findings:
  - `[false]` `[reject]` `CalendarView` weeks identity cache only short-circuits same object — intentional; content-equal new grids must redraw; invalidate-on-entry is the dwell contract.
  - `[low]` `[reject]` App fallback `UiCompositor(clock_view._display)` private coupling — `main` always injects compositor; everyday path does not hit the fallback.
  - `[low]` `[reject]` Weekday/day bitmap scales 8/16 vs UX ~11/~14 — nearest integer scale, same class of compromise as Story 1.2 badge/time metrics.
  - `[medium]` `[patch]` No 6-week month coverage — added May 2021 case asserting 42 day glyphs and positive `cell_h`.
  - `[medium]` `[patch]` Layout gap test only used `>= cell_w // 2` — tightened to exact `cell_w + CALENDAR_GAP` column slots (same root as verification-gap gap finding).
  - `[false]` `[reject]` AC “3px rounded” vs rectangular fill — Design Notes already accept rectangular Fake `fill_rect` (Story 1.2 badge precedent); fixing AC would edit this build's intent wording.
  - `[low]` `[reject]` Integer-division leftover width left-biases the grid — ~4px cosmetic under centered label; not everyday desk harm.
  - `[false]` `[reject]` `hasattr(..., "invalidate")` soft-skip — Clock and Calendar both implement `invalidate`; no demonstrated base without it.
  - `[false]` `[reject]` App never enters Calendar / empty deferred — Intent Never excludes rotation (Story 2.3); host-only Calendar entry is the intended slice.
  - `[low]` `[reject]` Clock/App path does not assert badge-last op order — same `UiCompositor.render` as Calendar tests that pin last-text badge.
  - `[false]` `[reject]` Unused `snapshot` / no grid-vs-local guard — Design Notes: duck-typing; grid is caller-owned until 2.3.
  - `[low]` `[reject]` Empty warnings/deferred for known bitmap limits — residuals belong in Design Notes / Auto Run Result; not everyday defects.
  - `[false]` `[reject]` Edge: month outside 1..12 for label — valid `MonthGrid` producers only; same valid-input stance as Story 2.1.
  - `[false]` `[reject]` Edge: `grid is None` — not a demonstrated call path.
  - `[false]` `[reject]` Edge: `cell_w`/`cell_h` <= 0 on 320×240 with fixed pads — not reachable with current constants.
  - `[false]` `[reject]` Edge: week length ≠ 7 — `build_month_grid` always emits weeks of seven.
  - `[false]` `[reject]` Edge: `snapshot is None` in compositor — render contract requires a snapshot; None not demonstrated.
  - `[false]` `[reject]` Edge: badge flip without `invalidate` — same as hasattr finding; both bases implement it.
  - `[false]` `[reject]` Edge: compositor None and missing `_display` — `ClockView` always has `_display`; `main` injects compositor.
  - `[medium]` `[patch]` Today-cell fill extent not pinned — strengthened test to assert full recomputed cell `fill_rect`.
  - `[medium]` `[patch]` 2px `CALENDAR_GAP` not actually asserted — same patch as layout gap tightening above.
  - `[false]` `[reject]` Intent-alignment: App “Calendar entered” Reading B unmet — Never excludes rotation; renderer API is the verifying surface.
  - `[false]` `[reject]` Intent-alignment: live dual-view FR4 unmet — shared compositor exists; live Calendar dwell is Story 2.3.
  - `[false]` `[reject]` Intent-alignment: desk-legibility Reading D unmet — host Fake only by design; no on-device claim.
  - `[false]` `[reject]` Intent-alignment: exact UX scale / soft-corner Reading E unmet — Design Notes accept nearest scales and rectangular today fill.
  - `[false]` `[reject]` Intent-alignment: FR5 “current month” App selection unmet — paint-from-supplied-grid is this story; App builds grid in 2.3.
  - `[false]` `[reject]` Intent-alignment: MonthGrid+snapshot App composition unmet — test/caller convention until rotation wires builders.

## Design Notes

Weekday header letters match UX mockup: `M T W T F S S` (not three-letter DOW). Variable week-row count from `MonthGrid.weeks` (4–6); lay out rows with equal cell height from remaining content box after label + header.

Compositor `render(view, snapshot, *args)` keeps Clock as `render(snapshot)` and Calendar as `render(snapshot, grid)` without forcing a shared render signature beyond duck-typing.

Today/badge “3px rounded”: rectangular `fill_rect` on FakeDisplayPort is acceptable (Story 1.2 precedent); do not invent soft-corner blitting.

## Verification

**Commands:**
- `uv run pytest tests/test_calendar_view.py -q` -- expected: new Calendar/compositor tests pass
- `uv run pytest -q` -- expected: full host suite green (Clock/App badge path updated)

## Auto Run Result

Status: done

Summary: Host-verifiable Calendar chrome via `CalendarView` + shared `UiCompositor` (badge last / invalidate on trust flip); Clock badge ownership moved out of the base view; App Clock paints route through the compositor. No App Calendar rotation (Story 2.3).

Files changed:
- `src/config.py` — Calendar font IDs/scales and pad/gap/label constants
- `src/ui/compositor.py` — `UiCompositor` badge visibility + draw-last
- `src/ui/calendar_view.py` — MonthGrid renderer (label, `M T W T F S S`, today/overflow colors)
- `src/ui/clock_view.py` — badge draw / badge self-invalidate removed
- `src/app.py` / `main.py` — Clock refresh via compositor
- `tests/test_calendar_view.py` — I/O matrix + review patches (14 tests)
- `tests/test_clock_view.py` / `tests/test_app_loop.py` — badge path retargeted to compositor
- `spec-2-2-render-the-current-month-calendar-view.md` — this story spec
- `sprint-status.yaml` — `2-2-…: done`; `epic-2` stays `in-progress`; `1-4`/`1-5` untouched

Review findings: patched 3 medium entries (today full-cell fill assert, exact `CALENDAR_GAP` column spacing, 6-week row budget); deferred 0; rejected 24 (invalid-input guards, App Calendar entry/2.3 surfaces, scale/rounding chrome, private `_display` fallback, identity cache design, intent Reading B/D/E mismatches).

Follow-up review recommendation: true — three medium verification patches on first pass. Residual risk: re-confirm today fill and gap asserts still match `_full_redraw` if pad/gap/font scales change; 6-week `cell_h` headroom only proven for May 2021 metrics.

Verification: `uv run pytest tests/test_calendar_view.py -q` → 14 passed; `uv run pytest -q` → 101 passed.

Residual risks: no on-device flash/legibility check; App still Clock-only until 2.3; weekday ~8px / day ~16px vs UX ~11/~14; today/badge “3px round” remains rectangular `fill_rect`.

Blocking condition: none

Note: git commit skipped per orchestrator instruction; working tree left dirty for parent commit.
