---
title: 'Keep the Clock running through time-source failures'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: 'd813b98e66d6d8cc4da04c777ebda848730f2a2a'
baseline_commit: 'd813b98e66d6d8cc4da04c777ebda848730f2a2a'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-1-context.md'
warnings:
  - oversized
deferred: []
---

<intent-contract>

## Intent

**Problem:** Stories 1.1–1.2 left a pure time model and Clock renderer, but no App loop, ClockPort, or tick-safe scheduling—so the desk clock cannot advance, disclose trust loss, or survive reported time-source / credential failures without freezing or crashing.

**Approach:** Add a single-writer App that owns `AppState`, reads advancing UTC only through `ClockPort`, derives snapshots via pure time logic, refreshes Clock ≥1 Hz using wrap-safe tick deadlines, and treats expected sync/credential failures as unsynced + serial diagnostics without blocking.

## Boundaries & Constraints

**Always:**
- App is the sole writer of `AppState` (time trust/validity, active view, deadlines). Renderers and adapters consume immutable `TimeSnapshot`s and keep only draw caches; they must not mutate view or trust.
- Boot with Clock as the active view; stay on Clock (no Calendar rotation).
- Read advancing UTC only through `ClockPort.read_utc()`; convert with existing pure `make_snapshot` / `utc_to_local`; never call `ntptime.settime()`.
- Schedule redraw / retry / freshness / view work with `ticks_ms`, `ticks_add`, `ticks_diff` and config durations — never wall-clock deadlines or raw tick compares.
- On expected time-source failure or invalid/missing credentials reported to App: mark trust unsynced, keep rendering any valid RTC time, emit concise serial diagnostics, do not crash or block the loop.
- Pure modules (`src/time/`, tick arithmetic helpers, App scheduling logic under test) must import under CPython without `machine`/`network`/`ntptime`/`src.device`. RTC adapter lives under `src/device/`.

**Never:**
- Do not implement the network worker, mailbox, WLAN, DNS, or NTP client (Stories 1.4 / 1.5). Inject failure/credential reports into App instead.
- Do not enter Calendar, change pins/SPI/MADCTL, allocate a full framebuffer, or put secrets in `src/config.py`.
- Do not claim on-device loop behavior from host runs; flash QA remains user-run.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Boot | App starts with display + clock ports | Active view = Clock; App owns AppState; renderer cannot change trust/view | No error expected |
| Valid RTC tick | `read_utc()` returns advancing DateTime; trust any | Snapshot via pure conversion; Clock refreshed ≥1/s through DisplayPort | No error expected |
| Cold / invalid RTC | `read_utc()` returns None | Snapshot cold (`local=None`, unsynced); Clock shows `--:--` + badge | No crash |
| Sync failure report | App receives expected time-source failure | Trust → unsynced; continue valid RTC snapshots; concise serial print; loop keeps running | Non-blocking |
| Invalid/missing credentials | Missing `secrets.py` or empty SSID/password at composition | Same as sync failure (unsynced + diagnostics); no boot crash | Soft fail |
| Deadline schedule | redraw/retry/freshness deadlines | Set/check only via ticks_ms/add/diff + config ms constants | No wall-clock schedule |

</intent-contract>

## Code Map

- `src/ticks.py` -- **Create:** wrap-safe `ticks_ms`, `ticks_add`, `ticks_diff` (PERIOD `2**32`). Host: monotonic ms masked; device: prefer MicroPython `time.ticks_*` when present. Pure add/diff must be host-testable without `machine`.
- `src/app.py` -- **Create:** `AppState` (time trust/utc_valid, `VIEW_CLOCK`, deadline fields), `App` sole writer. Dependencies: ClockPort, ClockView (or DisplayPort+view), ticks, optional log sink. Methods: boot → Clock active; loop/step that reads UTC via port, `make_snapshot`, `view.render`; `report_time_source_failure(reason)` / credential soft-fail → unsynced + diagnostic; schedule next redraw with `ticks_add(ticks_ms(), 1000)` (or config `CLOCK_REDRAW_MS`); never mutate state from renderer.
- `src/device/clock_port.py` (or `src/device/rtc.py`) -- **Create:** RTC-backed `ClockPort` with `read_utc()` / `set_utc(DateTime)` using `machine.RTC`; map None/invalid → None. Only App calls it. Device-only imports.
- `src/time/model.py` / `src/time/service.py` -- **Read-only reuse:** `DateTime`, `TRUST_*`, `TimeSnapshot`, `make_snapshot`, `utc_to_local` (lines in service: `make_snapshot` ~58–78).
- `src/ui/clock_view.py` / `src/ui/display_port.py` -- **Reuse:** `ClockView.render(snapshot)`, `FakeDisplayPort` for host composition tests. Do not rework dirty-region logic unless App wiring requires `invalidate()` on view entry.
- `src/config.py` -- **Extend:** `CLOCK_REDRAW_MS = 1000` (and reuse `NTP_RETRY_MS` for retry deadline fields even if NTP unused). Keep secrets out.
- `main.py` -- **Compose:** SPI → ILI9341 → `Ili9341DisplayPort` → `ClockView` → RTC ClockPort → `App`; soft-check credentials before/at App start; replace splash-idle with App loop. Keep fatal LED blink on unexpected exceptions.
- `secrets.example.py` / `.gitignore` `/secrets.py` -- **Read-only:** empty-template contract; loader treats missing/empty as invalid credentials.
- `tests/test_app_loop.py` (and/or `test_ticks.py`) -- **Create:** FakeClockPort (advancing UTC), FakeDisplayPort, injectable ticks; cover I/O matrix; AST purity for `src/ticks.py` + App logic modules excluding device; assert ticks_* used for deadlines; assert failure/credential paths set unsynced without raising.
- Continuity: `spec-1-2-...md` delivered Clock/DisplayPort/badge; `spec-1-1-...md` delivered pure time + config timings. Deferred ILI9341 per-fill buffer remains out of scope.

## Tasks & Acceptance

**Execution:**
- [x] `src/ticks.py` -- Implement wrap-safe tick helpers -- AD-5 host+device scheduling.
- [x] `src/app.py` -- Implement AppState + single-writer App loop/step -- AD-2/AD-3 sole authority.
- [x] `src/device/clock_port.py` -- Implement RTC ClockPort adapter -- AD-3 hardware UTC source.
- [x] `src/config.py` -- Add `CLOCK_REDRAW_MS` (reuse retry constant) -- named durations only.
- [x] `main.py` -- Compose App over DisplayPort Clock + ClockPort; soft credential check -- FR2–4 boot path.
- [x] `tests/test_app_loop.py` (+ ticks tests) -- Cover I/O matrix, ≥1 Hz snapshot refresh, failure/credential unsynced, ticks-only deadlines, purity -- host verification.

**Acceptance Criteria:**
- Given App boot, when the loop starts, then Clock is the active view, App is the sole writer of AppState, and renderers/adapters cannot mutate the active view or time-trust state.
- Given a valid RTC value, when the App derives recurring snapshots, then it reads the advancing UTC only through ClockPort, converts it locally through pure time logic, and refreshes the Clock at least once per second.
- Given an expected time-source failure or an invalid credential file, when it is reported to App, then App marks trust unsynced, continues rendering any valid RTC time, emits concise serial diagnostics, and does not crash or block.
- Given App deadlines, when it schedules redraw, retry, freshness, or view work, then it uses ticks_ms, ticks_add, and ticks_diff rather than wall-clock values or raw tick comparisons.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 19 findings — high 0, medium 11, low 3, false 5, maybe-false 0
- findings:
  - `[false]` `[reject]` App never consults `utc_valid` before snapshotting RTC — design notes defer NTP validity marking to 1.5; AC requires continuing any valid RTC time; cold path is ClockPort→None.
  - `[medium]` `[patch]` RTC year floor 2020 accepts MicroPython power-on (~2021) as wall time — raised `_MIN_VALID_YEAR` to 2024 so unset defaults map to None.
  - `[medium]` `[patch]` Credential soft-check untested / report-before-boot composition path — extracted host-safe `src/credentials.py`; boot also sets unsynced so trust overwrite is harmless; added credential tests.
  - `[medium]` `[patch]` No host tests for `RtcClockPort` invalid→None — added `tests/test_clock_port.py` with stubbed `machine` + injectable fake RTC.
  - `[low]` `[reject]` `FakeClockPort.advance_second` skips day rollover — test helper only; suite never crosses midnight; fix would be test-only complexity without AC failure.
  - `[false]` `[reject]` Failure leaves `utc_valid`/`sync_age_ms` untouched — `utc_valid` never becomes True in this story; sync_age stays None by design until 1.5.
  - `[false]` `[reject]` In-place AppState mutation vs “explicit replacements” design note — sole-writer App mutating its own state meets AC; no demonstrated renderer write-through.
  - `[medium]` `[patch]` retry/freshness/view deadline expiry re-arm unasserted — extended `test_deadlines_use_ticks_helpers_not_wall_clock` past dwell/retry with wrap-safe asserts.
  - `[medium]` `[patch]` RTC accepts impossible civil days (e.g. Feb 31) — reject days outside `_days_in_month`; set_utc write errors rejected separately (no 1.3 caller).
  - `[false]` `[reject]` Tasks `[x]` while status in-progress / empty triage mid-review — expected until finalize; status now done after this pass.
  - `[medium]` `[patch]` `secrets` import non-ImportError crashes soft-fail — `credentials_valid()` now catches `Exception`.
  - `[medium]` `[patch]` Duplicate edge finding: secrets present but import fails non-ImportError — same `credentials_valid()` Exception guard.
  - `[medium]` `[patch]` RTC day outside real month length — same `_days_in_month` gate as blind impossible-date finding.
  - `[false]` `[reject]` `set_utc` RTC write can raise into App — App never calls `set_utc` in 1.3; NTP write path is 1.5.
  - `[low]` `[patch]` Injected `now_ticks` not masked to PERIOD — `App.step` now masks with `PERIOD - 1`.
  - `[low]` `[reject]` FakeClockPort midnight (edge duplicate) — same as blind FakeClockPort day-roll reject.
  - `[medium]` `[patch]` Credential soft-fail never runs composition soft-check (verification-gap) — host tests cover `credentials_valid()` missing/empty/broken-import; main calls helper.
  - `[medium]` `[patch]` Retry/freshness/view deadline re-arm unasserted (verification-gap) — same deadline test extension as above.
  - `[medium]` `[patch]` RtcClockPort invalid/cold→None untested (verification-gap) — same `tests/test_clock_port.py` coverage.

## Design Notes

- Prefer a host-driven `App.step(now_ticks=None)` (or inject ticks module) so tests advance fake time and FakeClockPort without sleeping; `run_forever` can loop `step` + short sleep on device.
- Credential check is composition-time soft fail calling the same `report_time_source_failure` path as injected sync failures — no WLAN attempt in this story.
- `utc_valid` / first successful NTP marking stays App-owned; without NTP (1.5), treat FakeClockPort-provided UTC as valid for host “valid RTC” cases; device RTC may return None until set — cold path already covered by ClockView.
- Keep `AppState` replacements explicit (assign new fields / replace time sub-state) so tests can assert renderers never hold a writable trust reference they mutate.

## Verification

**Commands:**
- `uv run pytest` -- expected: all existing + new App/ticks tests pass
- `uv run python -c "from src import app, ticks; from src.time import service"` -- expected: host import without device deps

**Manual checks (if no CLI):**
- Flash/device App loop + RTC advancement is user-run after deploy; not claimed from host.

## Auto Run Result

Status: done

Summary: Story 1.3 delivers a single-writer App loop over ClockPort + pure snapshots + wrap-safe tick deadlines, with soft credential/time-source failure → unsynced + serial diagnostics, host-verified composition, and main.py wiring Clock on boot. Review patches tightened RTC cold/invalid gating, credential soft-check testability, deadline expiry assertions, and tick masking.

Files changed:
- `src/ticks.py` — wrap-safe ticks_ms/add/diff
- `src/app.py` — AppState + App boot/step/report/run_forever; PERIOD-masked now_ticks
- `src/device/clock_port.py` — RtcClockPort with year≥2024 and month-length checks
- `src/credentials.py` — host-safe credentials_valid soft-check
- `src/config.py` — CLOCK_REDRAW_MS
- `main.py` — SPI → DisplayPort → ClockView → ClockPort → App loop
- `tests/test_app_loop.py` — matrix, purity, deadline re-arm
- `tests/test_ticks.py` — tick arithmetic + purity
- `tests/test_credentials.py` — missing/empty/broken secrets
- `tests/test_clock_port.py` — stubbed machine RTC validity
- this spec + sprint-status for 1.3

Review findings: patches applied (medium×3 groups: credentials soft-check, deadline re-arm, RTC validity/tests; low×1 now_ticks mask). Rejected: utc_valid gating before NTP, FakeClockPort midnight helper, in-place AppState vs design note, set_utc raise without caller, mid-review tracking noise. Deferred: none new.

Follow-up review recommendation: true — three medium patch groups landed. Unverified residual risk: confirm on-device MicroPython RTC weekday mapping and that power-on defaults remain below year 2024 on the flashed firmware; re-check credentials_valid still soft-fails if secrets layout changes.

Verification:
- `uv run pytest` — 48 passed
- `uv run python -c "from src import app, ticks; from src.time import service"` — succeeded (also imports credentials)

Residual risks: on-device App loop / RTC advance not run here (flash QA); NTP/worker still stories 1.4–1.5; ILI9341 per-fill buffer deferral from 1.2 unchanged.

Blocking condition: none

Note: git commit skipped by orchestrator policy for this unattended pass; working tree remains dirty for the parent orchestrator to commit.
