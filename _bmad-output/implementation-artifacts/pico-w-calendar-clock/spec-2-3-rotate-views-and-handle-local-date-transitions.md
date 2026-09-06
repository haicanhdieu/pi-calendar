---
title: 'Rotate views and handle local-date transitions'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: '5bd738d0ab513661bc11ed82e9c8a1d6de543baa'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-2-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** App stays on Clock forever: view deadline only re-arms Clock dwell, Calendar is never entered, and local midnight / month boundaries are not handled, so FR6/FR7 rotation and date lifecycle are missing.

**Approach:** Add pure view-state helpers and restructure App.step to AD-12 event order so Clock↔Calendar plain-cuts on configurable dwells, gates Calendar on valid local time, refreshes today/date at midnight, and defers month-grid rebuild when month rolls during Calendar.

## Boundaries & Constraints

**Always:**
- Boot and default to Clock; dwells from `config.CLOCK_DWELL_MS` / `CALENDAR_DWELL_MS` (30s/8s); schedule only via `ticks_ms` / `ticks_add` / `ticks_diff`.
- Loop order: consume adapter results → derive snapshot → handle date/month rollover → handle view deadline → render base → render status (compositor). Adapter consume may be a no-op until Story 1.5.
- Enter Calendar only when `calendar_entry_allowed(snapshot)` (`local is not None`); otherwise re-arm Clock dwell and stay on Clock.
- Same-month local day change: refresh Clock date line and Calendar today highlight immediately (rebuild grid if Calendar is active).
- Month change during Calendar: plain-cut to Clock, reset Clock dwell, drop cached grid; build new `MonthGrid` only on next Calendar entry via `build_month_grid`.
- View entry: invalidate the entered base view; render through `UiCompositor` (badge last). No animation or input.
- Pure modules (`app`, `view_state`, calendar/time) must not import `machine` / `network` / `ntptime` / `src.device`.

**Never:**
- Do not implement NTP/mailbox (1.5), lunar annotations, input, animation, or pin/SPI changes.
- Do not rebuild the month grid mid-Calendar-dwell on month change; do not enter Calendar without valid local.
- Do not claim on-device rotation as observed from host tests; do not allocate a full framebuffer.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Boot + valid local | RTC UTC present | Active=Clock; `view_deadline` = now+CLOCK_DWELL; first paint Clock via compositor | No error expected |
| Clock dwell expires, valid | `local` set, Clock active, deadline due | Cut to Calendar; arm CALENDAR_DWELL; build grid; invalidate+render Calendar | No error expected |
| Calendar dwell expires | Calendar active, deadline due | Cut to Clock; arm CLOCK_DWELL; invalidate+render Clock | No error expected |
| Clock dwell, invalid time | `local` None, deadline due | Stay Clock; re-arm CLOCK_DWELL; no Calendar entry | No crash |
| Same-month midnight | Local day++ same month, either view | Clock date updates; if Calendar, rebuild grid with new `is_today`; event order preserved | No error expected |
| Month rollover on Calendar | Local month changes while Calendar active | Cut to Clock; reset Clock dwell; clear grid; next Calendar entry builds new month | No mid-dwell grid swap |
| Wrap-safe deadlines | `now` near `PERIOD` | Dwell/redraw re-arms via `ticks_add`/`ticks_diff` only | No wall-clock compare |
| Purity | Import app/view_state under CPython | Succeeds; AST forbids device imports | Import/AST fail = test fail |

</intent-contract>

## Code Map

- `src/ui/view_state.py` -- **Create:** pure helpers — `VIEW_CLOCK`/`VIEW_CALENDAR` constants (or re-export); `classify_local_rollover(prev_ymd, local) -> None|"day"|"month"`; `next_view_after_dwell(active, snapshot)` using `calendar_entry_allowed` (Clock→Calendar only if allowed, else stay Clock; Calendar→Clock). No display/device imports. Architecture spine names this module for rotation.
- `src/app.py` -- **Extend:** inject `calendar_view`; AppState tracks `active_view`, deadlines, `_last_local_ymd` (or equivalent), cached `_month_grid`. Restructure `step` to AD-12 order (adapter no-op OK). On Calendar entry call `build_month_grid(local.y, local.m, today…)`; compositor.render Clock as `(view, snap)` and Calendar as `(view, snap, grid)`. Replace stub that forces Clock on view deadline (~lines 119–122). Export `VIEW_CALENDAR`.
- `src/time/model.py` -- **Reuse:** `calendar_entry_allowed` (~72–74) is the Calendar gate.
- `src/calendar/gregorian.py` -- **Reuse:** `build_month_grid` on Calendar entry and same-month today refresh while Calendar active.
- `src/ui/calendar_view.py` / `src/ui/clock_view.py` / `src/ui/compositor.py` -- **Reuse:** `invalidate()` on view entry / forced restore; do not change badge ownership.
- `src/config.py` -- **Reuse:** `CLOCK_DWELL_MS`/`CALENDAR_DWELL_MS`/`CLOCK_REDRAW_MS` already present (~89–91); no magic numbers in App.
- `main.py` -- **Wire:** construct `CalendarView(display_port)` and pass into `App` beside Clock + compositor.
- `tests/test_app_loop.py` and/or `tests/test_view_state.py` -- **Extend/create:** FakeTicks + FakeClockPort advancing across dwells and local midnight/month; assert rotation, invalid-time gate, midnight today refresh, deferred month-grid rebuild, wrap-safe deadlines, purity AST including `view_state`.
- Continuity: Story 2.2 delivered CalendarView+UiCompositor (Clock already compositor-routed); Story 1.3 delivered App/ticks/soft-fail — this story owns rotation + rollover only.

## Tasks & Acceptance

**Execution:**
- `src/ui/view_state.py` -- Add pure rollover + dwell transition helpers -- NFR4 / AD-12 policy outside App I/O.
- `src/app.py` -- AD-12 ordered step; Calendar injection; grid cache; dwell + rollover handling -- FR6/FR7.
- `main.py` -- Construct and inject CalendarView -- device composition path.
- `tests/test_view_state.py` and/or `tests/test_app_loop.py` -- Cover I/O matrix + purity -- NFR1/NFR5 host proof.
- `sprint-status.yaml` -- Reflect story progress per workflow -- tracking only.

**Acceptance Criteria:**
- Given a valid local time at boot, when App starts view scheduling, then it begins on Clock, holds it for the configurable 30-second default, cuts to Calendar for the configurable 8-second default, and repeats with no animation or input affordance.
- Given a local midnight while either view is active, when App processes its loop events, then it updates the Clock date line and Calendar today highlight immediately using its one defined event order: consume adapter results, derive snapshot, handle date/month rollover, handle view deadline, render base view, render status layer.
- Given a local month rollover during Calendar dwell, when App detects it, then it cuts to Clock, resets Clock dwell, and builds the new month grid only on the next Calendar entry.
- Given no valid local time yet, when the Clock dwell expires, then App remains in Clock and does not enter Calendar.
- Given view-state and lifecycle rules, when host tests run, then they prove wrap-safe deadlines, dwell rotation, invalid-time gating, midnight today refresh, and deferred month-grid refresh without device imports.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 15 findings — high 0, medium 3, low 1, false 11, maybe-false 0
- findings:
  - `[medium]` `[patch]` Same-month midnight while Clock active untested (Clock date line) — added `test_same_month_midnight_updates_clock_date_via_force_redraw` asserting force_redraw paints `Mon · Sep 7 2026` before redraw_deadline.
  - `[false]` `[reject]` No combined day-change + due view_deadline step proving rollover-before-deadline — step control flow already runs rollover then deadline; month cut re-arms dwell so deadline does not re-fire incorrectly.
  - `[low]` `[reject]` Month change while already on Clock has no dedicated grid-clear test — critical AC path is Calendar-during-month; Clock-path clear is trivial and unused until next entry.
  - `[false]` `[reject]` Calendar + None local leaves view active and can crash — month clear always pairs with Clock cut; Calendar entry always builds grid; crash state unreachable.
  - `[false]` `[reject]` Code Map says AppState owns `_last_local_ymd`/`_month_grid` but they live on App — fix would edit this build's spec; App-owned caches match sole-writer design.
  - `[false]` `[reject]` Spec missing Auto Run Result mid-review — expected until finalize; written in this pass.
  - `[false]` `[reject]` Snapshot derived every `step` raises RTC read rate — AD-12 requires derive-snapshot in loop order; Design Notes accept it.
  - `[false]` `[reject]` Retry/freshness between rollover and view deadline breaks AD-12 — named Always sequence still in order; retry re-arm is orthogonal scheduling.
  - `[false]` `[reject]` `_render` Calendar with None grid and None local crashes — same unreachable state as blind crash finding; production paths always cut or rebuild.
  - `[medium]` `[patch]` Verification gap: Clock-active midnight date line unverified — same patch as Clock force_redraw midnight test above.
  - `[medium]` `[patch]` Intent Reading B: Clock date-line midnight surface vs Calendar-only tests — same patch; Clock paint now host-proven.
  - `[false]` `[reject]` Intent Reading C: on-device glance not claimed — host-only by design; manual flash deferred.
  - `[false]` `[reject]` Intent Reading D: full Implements line as new delivery — continuity/reuse; 2.3 owns rotation + date lifecycle only.
  - `[false]` `[reject]` Event order not asserted as sequenced observations — outcomes + code order satisfy AC; no demonstrated wrong order.
  - `[false]` `[reject]` Adapter-results step is comment-only no-op — Story 1.5 mailbox/NTP; intentional until then.

## Design Notes

Same-month vs month rollover: compare previous `(year, month, day)` to current `snapshot.local`. Day change with same `(year, month)` → refresh today (rebuild grid only if already on Calendar). `(year, month)` change while on Calendar → cut to Clock + clear grid; while on Clock → clear grid only so next entry rebuilds.

Force redraw after view switch or rollover that changes painted content; otherwise keep 1 Hz `CLOCK_REDRAW_MS` cadence. Adapter-results step stays empty until mailbox/NTP exists.

## Verification

**Commands:**
- `uv run pytest tests/test_view_state.py tests/test_app_loop.py -q` -- expected: rotation/rollover/purity tests pass
- `uv run pytest -q` -- expected: full host suite green

**Manual checks (if no CLI):**
- Flash and observe Clock→Calendar plain-cuts and midnight/month behavior on device; not claimed from host.

## Auto Run Result

Status: done

Summary: App-owned Clock↔Calendar dwell rotation with AD-12 event order, invalid-local Calendar gating, same-month midnight refresh (Clock date line + Calendar today), and month-during-Calendar cut-to-Clock with deferred grid rebuild. Pure `view_state` helpers; host suite green. No on-device claim.

Files changed:
- `src/ui/view_state.py` — pure VIEW_* / rollover classify / next-view-after-dwell
- `src/app.py` — AD-12 step order; Calendar injection; dwell + rollover; grid cache
- `main.py` — construct/inject CalendarView
- `tests/test_view_state.py` — purity + helper matrix
- `tests/test_app_loop.py` — rotation, gating, midnight (Clock+Calendar), deferred month rebuild, wrap-safe
- `spec-2-3-rotate-views-and-handle-local-date-transitions.md` — this story spec
- `sprint-status.yaml` — `2-3-…: done`; `epic-2: done`; `1-4`/`1-5`/`epic-1` untouched

Review findings: patched 1 medium entry (3 member rows: Clock midnight force_redraw test); deferred 0; rejected 12 (unreachable Calendar crash, AD-12/retry ordering, every-step snapshot, Code Map wording, mid-review Auto Run, low month-on-Clock test gap, intent Readings C/D, event-order observation, adapter no-op).

Follow-up review recommendation: false — one medium patched entry on first pass (not ≥2 medium, no high).

Verification: `uv run pytest tests/test_view_state.py tests/test_app_loop.py -q` → 20 passed; `uv run pytest -q` → 111 passed.

Residual risks: on-device plain-cut/midnight still needs flash; adapter consume remains no-op until 1.5; snapshot derived every step (AD-12) until a future bounded-read optimization is scoped.

Note: Working tree left uncommitted per orchestrator policy (build-auto pass does not commit).
