---
title: 'Generate a correct Gregorian month model'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: '1edae54aafb39924836f17c1d7d1183dbcb6169d'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-2-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The device has no pure Gregorian month model yet, so Calendar cannot place days, today, or future annotations without hardware-tied date math.

**Approach:** Add a host-testable `src/calendar/` package that builds a Monday-first `MonthGrid` of `DayCell` records (date, `in_month`, `is_today`, empty ordered annotations) from a local Gregorian date, with annotation kind ownership centralized in `models.py`.

## Boundaries & Constraints

**Always:**
- Pure calendar modules must import under CPython with no `machine`, `network`, `ntptime`, or `src.device` imports (same AST purity bar as `src/time/`).
- Weekday index `0` is Monday; every week has exactly seven `DayCell`s; grids include adjacent-month overflow with `in_month=False`.
- Leap years use the Gregorian rule already used in time helpers (`%4` / `%100` / `%400`).
- `DayCell` exposes Gregorian date fields, `in_month`, `is_today`, and an ordered annotation collection; v1 always emits an empty collection.
- Allowed annotation kinds are lowercase kebab-case and owned only by `src/calendar/models.py` (registry + ordering), even when the registry is empty in v1; renderers own formatting later.
- Compute first-of-month weekday from `(year, month, day)` arithmetic — do not trust `DateTime.weekday` from RTC (Story 1.1 deferred Monday=0 documentation on RTC passthrough).
- Domain types use `__slots__` and MicroPython-friendly style matching `src/time/model.py` (no dataclasses / heavy typing runtime).

**Never:**
- Do not implement Calendar rendering (`ui/calendar_view.py`), view rotation, midnight/month-rollover App policy (2.2–2.3), lunar providers, or non-empty annotations.
- Do not implement network/NTP (1.5) or change hardware pins / display adapters.
- Do not put UI strings (month names, weekday labels) in the calendar model.
- Do not import calendar code into device adapters; do not claim on-device behavior from host runs.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Ordinary month | Local today mid-month (e.g. 2026-09-06) | Grid for Sept 2026; Mon-first weeks of 7; today cell `is_today=True`, `in_month=True`; annotations `()`/`[]` empty | No error expected |
| Leap February | Today in Feb 2024 (leap) | 29 in-month days; Mar overflow after 29; weekday alignment correct | No error expected |
| Non-leap February | Today in Feb 2025 | 28 in-month days; no day 29 | No error expected |
| Month starts Monday | First of month is Monday | Week 0 day 0 is the 1st with `in_month=True`; no prior-month lead-in | No error expected |
| Month starts Sunday | First of month is Sunday | Six prior-month lead-in cells (`in_month=False`) then the 1st | No error expected |
| Adjacent overflow | Any month needing trailing cells | Weeks continue into next month with `in_month=False` until last week length 7 | No error expected |
| Today identification | Today = in-month day D | Exactly one cell with matching y/m/d has `is_today=True`; overflow cells never today unless date matches (should not for current-month build) | No error expected |
| Annotation contract | Any generated cell | `annotations` ordered empty collection; kinds registry exists on models module | No error expected |
| Pure import surface | Import `src.calendar.models` / `gregorian` under CPython | Succeeds; no forbidden hardware imports | Import failure = test fail |

</intent-contract>

## Code Map

- `src/calendar/` -- Does not exist; create package for pure month model (architecture AD-6 / project-structure).
- `src/calendar/__init__.py` -- Empty package marker (match `src/time/__init__.py`).
- `src/calendar/models.py` -- Create: `CalendarAnnotation(kind, value)`, `DayCell` (Gregorian date + `in_month` + `is_today` + ordered annotations), `MonthGrid` (year/month + weeks), plus `ALLOWED_ANNOTATION_KINDS` / ordering ownership surface (empty for v1).
- `src/calendar/gregorian.py` -- Create: `days_in_month`, Monday=0 weekday-from-ymd, `build_month_grid(local_year, local_month, today_year, today_month, today_day)` (or equivalent local-date input) returning `MonthGrid`.
- `src/time/model.py` -- Reuse `DateTime` for cell Gregorian date if natural; otherwise store y/m/d ints with weekday filled via calendar math. Read-only for this story except optional shared type use.
- `src/time/service.py` -- `_days_in_month` at lines 7–13 is the leap algorithm to mirror (do not import private helper; calendar owns its copy or a shared pure export only if already public — prefer local copy in `gregorian.py` to avoid coupling).
- `src/device/clock_port.py` -- Read-only; RTC weekday passthrough is untrusted for Monday=0 — calendar must compute weekday itself.
- `src/ui/clock_view.py` -- Read-only evidence Monday=0 Dow labels; do not put strings in calendar.
- `tests/test_time_snapshot.py` -- Reuse AST purity helpers pattern (`PURE_*_MODULES`, `FORBIDDEN_IMPORT_ROOTS`, `_imported_roots`).
- `tests/test_gregorian_month.py` -- Create: I/O matrix coverage + purity asserts for `src/calendar/*`.
- `_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-2-context.md` -- Epic constraints; do not expand into 2.2/2.3.
- `_bmad-output/implementation-artifacts/pico-w-calendar-clock/sprint-status.yaml` -- Set `2-1-…` through workflow statuses; set `epic-2` to `in-progress` when story completes; leave 1.4/1.5 alone.

## Tasks & Acceptance

**Execution:**
- `src/calendar/__init__.py` -- Add empty package marker -- enables `src.calendar` imports on host and device.
- `src/calendar/models.py` -- Define `CalendarAnnotation`, `DayCell`, `MonthGrid`, and annotation-kind ownership constants -- AD-6 cell contract.
- `src/calendar/gregorian.py` -- Implement Monday-first `build_month_grid` with leap/month-length, overflow, and today flags -- FR5/FR7 model surface.
- `tests/test_gregorian_month.py` -- Cover I/O matrix (ordinary, leap/non-leap Feb, Mon/Sun starts, overflow, today, empty annotations) and AST purity -- NFR4/NFR5.
- `_bmad-output/implementation-artifacts/pico-w-calendar-clock/sprint-status.yaml` -- Reflect story/epic progress per workflow -- tracking only.

**Acceptance Criteria:**
- Given any valid Gregorian local date, when the month grid is generated, then it returns Monday-first weeks with exactly seven `DayCell` entries per week and correct month boundaries, weekday alignment, and leap-year behavior.
- Given a `DayCell`, when Calendar consumes it, then the cell exposes its Gregorian date, `in_month`, `is_today`, and an ordered collection of `CalendarAnnotation(kind, value)` records; v1 emits an empty annotation collection.
- Given calendar model code, when host tests run under CPython, then they cover ordinary months, leap-year February, Monday/Sunday boundaries, adjacent-month overflow, and today identification without hardware imports.
- Given future enrichment providers, when they are added later, then allowed lowercase-kebab-case annotation kinds and ordering remain owned by `src/calendar/models.py`, while renderers retain formatting ownership.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 22 findings — high 0, medium 6, low 4, false 9, maybe-false 0
- findings:
  - `[false]` `[reject]` Invalid months not rejected by `days_in_month` — intent only requires valid Gregorian local dates; no demonstrated invalid producer from App/snapshots.
  - `[false]` `[reject]` Annotation-kind ownership not enforced at `CalendarAnnotation` construction — intent owns the registry/ordering constants in `models.py`, not runtime rejection; v1 grid always emits empty annotations.
  - `[medium]` `[patch]` Year-boundary overflow dating untested — added `test_january_prior_year_december_lead_in` and `test_december_next_year_january_trail`.
  - `[medium]` `[patch]` Century leap `days_in_month` unpinned — added `test_century_leap_rule_in_days_in_month` for 1900/2000.
  - `[medium]` `[patch]` Cross-month today-on-overflow path untested — added `test_overflow_cell_is_today` with `build_month_grid(2026, 9, 2026, 8, 31)`.
  - `[false]` `[reject]` Impossible `today_day` yields zero today cells — same valid-input contract; no demonstrated bad producer.
  - `[low]` `[reject]` Spec Code Map still says package does not exist — rejected because the fix is editing this build's spec.
  - `[low]` `[patch]` `PURE_CALENDAR_MODULES` omitted `__init__.py` — included empty package marker in AST purity list.
  - `[low]` `[reject]` No assert that `ALLOWED_ANNOTATION_KINDS` and `ANNOTATION_KIND_ORDER` stay parallel when extended — no everyday harm until providers exist; empty v1 tuples already match.
  - `[low]` `[reject]` Variable week-row count unspecified for 2.2 renderers — out of this story's intent (rendering is 2.2).
  - `[false]` `[reject]` Edge: invalid month silently length 31 — same valid-date contract as blind-hunter invalid-month finding.
  - `[false]` `[reject]` Edge: month < 1 wrong weekday via Sakamoto wrap — same valid-date contract.
  - `[false]` `[reject]` Edge: month > 12 IndexError — same valid-date contract; not a demonstrated call path.
  - `[false]` `[reject]` Edge: `today_day` outside month length — same valid-date contract.
  - `[false]` `[reject]` Edge: `CalendarAnnotation` accepts kinds outside registry — same ownership-vs-enforcement reading as above.
  - `[medium]` `[patch]` Verification-gap: year-wrap adjacent-month dating — same patch as year-boundary tests.
  - `[medium]` `[patch]` Verification-gap: century leap in `days_in_month` — same patch as century leap asserts.
  - `[medium]` `[patch]` Verification-gap: overflow-cell `is_today` never asserted true — same patch as overflow-today test.
  - `[false]` `[reject]` Intent-alignment: FR5 Calendar-view surface unmet — NOTE/ACs exclude rendering (2.2); model substrate is the intended reading.
  - `[false]` `[reject]` Intent-alignment: FR7 midnight/rollover surface unmet — excluded by NOTE (2.3); `is_today` from caller ints is the model contract.
  - `[false]` `[reject]` Intent-alignment: AD-4 timezone conversion unmet — calendar API correctly assumes already-local civil ints.
  - `[low]` `[reject]` Intent-alignment: “Calendar consumes” / highlight narrative vs producer-only tests — consumer is future 2.2; shape contract is verified at the model surface the ACs name.

## Design Notes

`build_month_grid` takes discrete local civil-date integers (or a local `DateTime` whose time fields are ignored) so App/later stories can pass `snapshot.local` without calendar importing device time.

Golden shape (illustrative): for a month whose 1st is Wednesday, week 0 is `[Mon_prev, Tue_prev, Wed_1, Thu_2, Fri_3, Sat_4, Sun_5]` with the first two `in_month=False`.

Weekday-from-ymd must be a self-contained Monday=0 algorithm (e.g. known civil formula); do not call `DateTime.weekday` from an RTC-sourced value as the alignment source of truth.

## Verification

**Commands:**
- `uv run pytest tests/test_gregorian_month.py -q` -- expected: all new calendar tests pass
- `uv run pytest -q` -- expected: full host suite still green

## Auto Run Result

Status: done

Summary: Pure `src/calendar/` package builds Monday-first `MonthGrid`/`DayCell` models with empty annotations; host tests cover the I/O matrix plus review-added year-wrap, century leap, and overflow-today cases.

Files changed:
- `src/calendar/__init__.py` — empty package marker
- `src/calendar/models.py` — `CalendarAnnotation`, `DayCell`, `MonthGrid`, empty kind registry/order
- `src/calendar/gregorian.py` — `days_in_month`, Monday=0 `weekday_from_ymd`, `build_month_grid`
- `tests/test_gregorian_month.py` — matrix + purity + review patches (16 tests)
- `epic-2-context.md` — compiled Epic 2 planning context
- `spec-2-1-generate-a-correct-gregorian-month-model.md` — this story spec
- `sprint-status.yaml` — `epic-2: in-progress`, `2-1-…: done`

Review findings: patched 4 entries (3 medium verification gaps + 1 low purity list); deferred 0; rejected 18 (invalid-input guards, annotation runtime enforcement, FR/AD surface mismatches out of story scope, spec-edit-only notes).

Follow-up review recommendation: true — three medium patched entries on first pass (year-wrap dating, century leap length, overflow `is_today`). Residual risk: those paths were only added as tests; no production callers yet to re-exercise them.

Verification: `uv run pytest tests/test_gregorian_month.py -q` → 16 passed; `uv run pytest -q` → 86 passed.

Residual risks: no on-device flash (host-only by design); annotation kinds are declared not enforced until providers land; App still does not call `build_month_grid` (2.2/2.3).

Blocking condition: none

Note: git commit skipped per orchestrator instruction; working tree left dirty for parent commit.
