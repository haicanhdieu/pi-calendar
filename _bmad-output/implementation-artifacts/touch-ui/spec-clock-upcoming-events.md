---
title: 'Clock Screen Upcoming Events'
type: 'feature'
created: '2026-09-14'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
baseline_revision: 'a4622ce86e333ef23986c0602b2cbe1f09d170d0'
---

<intent-contract>

## Intent

**Problem:** The Clock screen's bottom 56px band (`config.CLOCK_EVENTS_BAND_H_PX`, y=184..240) is reserved but empty; users can't see upcoming events without leaving the clock.

**Approach:** Extend `ClockView.render()` to accept an optional pre-selected, pre-sorted `events` list (up to 3, soonest-first) and draw each as one `HH:MM  Title` row in the reserved band, participating in the existing dirty-region cache-and-compare in `_full_redraw`. Sourcing/syncing real event data is out of scope (see Assumptions below); callers not yet passing events simply omit the argument.

## Boundaries & Constraints

**Always:**
- Each row: `HH:MM  Title`, `config.FONT_SETTINGS_STATUS` (16px), `config.COLOR_SECONDARY`, left-aligned at `x = config.CLOCK_CORNER_PAD_X_PX`.
- Row count == `len(events[:3])`: 0 events draws nothing in the band (no heading, no placeholder); 1–3 draw exactly that many rows.
- Rows stay inside the reserved band (`display.height - config.CLOCK_EVENTS_BAND_H_PX` .. `display.height`) and never shift the clock/corner-row geometry computed in `_layout()`.
- A row whose text would extend past `x=310` is truncated (char-by-char, via `display.measure_text`) and suffixed with `...` so it never overflows or wraps.
- `events` participates in the existing `_cache` compare: a change to `events` (including `None`↔`[]`↔non-empty transitions) must trigger `_full_redraw`, matching how `hhmm`/`date`/`lunar` already invalidate. `events` unchanged must NOT block the existing seconds-only fast path (`_redraw_ss`) or the identical-rerender no-op.
- `events` items are pre-formatted `(hhmm_str, title_str)` tuples, already sorted soonest-first and pre-filtered to upcoming — `ClockView` does no sorting, filtering, or date math on them.

**Never:**
- No `Event` model, ICS/API sync, or any real event data source — `events` stays an explicit, caller-supplied argument (defaulting to `None`/empty) until a real source exists.
- No per-row fill/badge box (that styling is reserved for the unsynced-clock alert).
- No tap/select handling, no details view, no multi-day/all-day handling.
- No change to `_layout()`'s clock/corner-row math.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| No events | `events=None` or `[]` | Band renders nothing; no ops in y=184..240 | No error expected |
| 1 event | `[("09:00", "Standup")]` | Exactly 1 row drawn at the band's first row slot | No error expected |
| 3 events | 3 tuples | Exactly 3 rows, in list order (soonest-first) | No error expected |
| >3 events supplied | 4+ tuples | Only the first 3 are drawn (defensive slice) | No error expected |
| Long title | Title whose `"HH:MM  " + title` width > `310 - CLOCK_CORNER_PAD_X_PX` | Title truncated + `...`, row stays within x=310, single line | No error expected |
| Events unchanged, seconds tick | Same `events` object/value across two `render()` calls, only `second` changed | `_redraw_ss` fast path still taken; band untouched | No error expected |
| Events changed, time unchanged | New `events` value, same `hhmm`/date | Full redraw triggered (not skipped as identical) | No error expected |

</intent-contract>

## Code Map

- `src/ui/clock_view.py` -- `ClockView.render()` (L117), `_full_redraw()` (L267), `_layout()` (L194), `_cache` init (L83) -- add `events` param/cache field, band draw, and cache-compare wiring here; `_layout()` band geometry (`available_bottom`, L237) is already reserved, do not touch clock/corner math.
- `src/config.py` -- clock layout constants block (L118-134): `CLOCK_CORNER_PAD_X_PX`, `CLOCK_EVENTS_BAND_H_PX` exist; add new row-spacing constants here.
- `src/ui/display_port.py` -- `FakeDisplayPort` (L7): `measure_text`/`draw_text`/`fill_rect` contract used for truncation and row drawing; no changes needed.
- `src/ui/settings_view.py` -- `_draw_status_lines()` (L16-30): reference pattern for measuring line height via `measure_text("Ag", font_id)` and stepping `y` per row.
- `tests/test_clock_view.py` -- existing `FakeDisplayPort`-based tests (e.g. `test_synced_valid_local_draws_time_date_no_badge` L113, `test_seconds_only_tick_dirties_ss_without_shifting_hhmm` L174, `test_identical_rerender_is_noop` L240) -- extend with events-band cases; assert via `display.ops`.

## Tasks & Acceptance

**Execution:**
- `src/config.py` -- add `CLOCK_EVENTS_ROW_TOP_PAD_PX`, `CLOCK_EVENTS_ROW_GAP_PX`, `CLOCK_EVENTS_ROW_RIGHT_PX = 310` -- give the band geometry named constants instead of magic numbers.
- `src/ui/clock_view.py` -- add `events=None` param to `render()`; add `"events"` to `_cache` init; extend the identical-content and steady-state-seconds compares to require `events` unchanged; extend `_full_redraw()` and `_layout()` to compute and draw up to 3 rows in the reserved band; add a small truncate-to-width helper using `display.measure_text` -- implements CAP-1.
- `tests/test_clock_view.py` -- add tests for each I/O Matrix row -- proves CAP-1's success criterion and the no-regression constraint.

**Acceptance Criteria:**
- Given 3+ upcoming events passed to `render(snapshot, events=...)`, when rendered, then exactly 3 rows appear in the band, each `HH:MM  Title`, `FONT_SETTINGS_STATUS`, `COLOR_SECONDARY`, left-aligned at `CLOCK_CORNER_PAD_X_PX`.
- Given 0 events, when rendered, then no ops touch the band region and no heading/placeholder appears.
- Given a title long enough to exceed `x=310`, when rendered, then the row is truncated with `...` and no op's x + width exceeds 310.
- Given `events` unchanged and only the clock second advancing, when rendered, then only the `_redraw_ss` op fires (no full redraw, no band re-draw).
- Given `events` changes (any transition, including `None`→`[]`), when rendered, then a full redraw fires even if `hhmm`/`date`/`lunar` are unchanged.

## Review Triage Log

### 2026-09-15 — Review pass
- verdicts: 14 findings — high 0, medium 1, low 7, false 6, maybe-false 0
- findings:
  - `low` `patch` Event rows compute to exactly 56px with zero bottom margin (4 top pad + 3×16px rows + 2×2px gaps == CLOCK_EVENTS_BAND_H_PX) and no test asserts the vertical bound the way x=310 is checked horizontally — a future constant/font change could silently overflow the reserved band. — Verified: math confirms 240px band bottom exactly; add an assertion to the 3-events test that each row's `y + row_h <= display.height`.
  - `low` `reject` Spec's "Tasks & Acceptance" says to extend `_full_redraw()` **and** `_layout()`, but the diff never touches `_layout()` — a real spec/code text mismatch. — Verified real, but its only fix is editing this build's spec, which is an excluded route.
  - `low` `patch` `cache["events"] = events` stores a live reference; if a caller reuses and mutates the same list object between `render()` calls, `cache["events"] == events` trivially holds and the required full-redraw-on-change guarantee is silently bypassed. — Verified: no current caller triggers this (grep confirms no production `events=` call site yet), but the fix is a one-line direct correction (`cache["events"] = list(events) if events else events`) so it is not auto-rejected as low-effort-exempt.
  - `false` `reject` No test exercises the `local is None` branch combined with a non-trivial `events` value. — Refuted: that branch's `events` check is the same plain `==` comparison already exercised on the synced-clock paths; verification-gap layer independently inspected the analogous identical-rerender case and found no distinct logic risk.
  - `medium` `patch` `_events_row_text` re-measures the full string via `display.measure_text` on every character dropped from `title`, with no upstream cap on title length — an unbounded number of measure calls per row per full redraw on a resource-constrained embedded display. — Verified: loop is uncapped; harm magnitude on real Pico hardware is uncertain so graded at the higher severity. Fix: cap `title` to a bounded max length before the truncation loop.
  - `low` `reject` Empty `title` or `hhmm` (e.g. `("09:00", "")`) is undocumented and untested; would draw a row with trailing whitespace and no visible content. — Real but unlikely: spec's Assumptions state `events` items are already pre-formatted, valid tuples from the caller; the fix (skip/guard empty entries) adds a branch beyond a direct correction, so rejected per the low-severity rule.
  - `low` `reject` The final fallback line in `_events_row_text` (`return hhmm + "  " + "..."`) duplicates a string already tested and rejected as non-fitting by the last loop iteration — dead-code smell, not a behavioral defect. — Real but cosmetic and unlikely anyone meets it in practice; the fix is more than a trivial deletion (would need restructuring to keep intent clear), so rejected.
  - `false` `reject` (edge-case-hunter) The `_events_row_text` fallback (`hhmm + "  " + "..."`) could still exceed `CLOCK_EVENTS_ROW_RIGHT_PX=310`. — Refuted by measurement: at `FONT_SETTINGS_STATUS` (cell width 6px, scale 2), the fixed 10-character fallback measures `(10*6-1)*2=118px`; at `x=CLOCK_CORNER_PAD_X_PX=10` that's `128px`, far under 310px, so this can never happen with current constants.
  - `low` `patch` (edge-case-hunter, same root cause as the cache-aliasing finding above) Caller reusing/mutating the same `events` list object bypasses the invalidation compare. — Same defect as the earlier cache-aliasing row; same fix (store a copy in `_full_redraw`).
  - `false` `reject` (edge-case-hunter) An `events` entry that is not exactly a 2-tuple `(hhmm, title)` raises `ValueError` on unpack in `_draw_events`, crashing `render()`. — Refuted as reachable today: no production caller passes `events` yet (grep confirms), and `events` is documented in the spec's Assumptions as a caller-supplied, pre-formatted contract — consistent with this codebase's convention of trusting internal-API callers rather than validating at non-boundary internal calls.
  - `false` `reject` (edge-case-hunter) `hhmm` or `title` being `None` or non-`str` raises `TypeError` on string concatenation. — Same refutation as the previous row: unreached today, and validating caller-supplied internal tuples contradicts this codebase's internal-trust convention.
  - `false` `reject` (edge-case-hunter, acceptance-criteria-claim variant, low confidence) The spec's acceptance criterion "no op's x + width exceeds 310" could be violated by the same fallback-width edge case. — Refuted by the same measurement as the earlier fallback-width row: 128px is well under 310px, so the acceptance criterion holds for all reachable inputs.
  - `false` `reject` (intent-alignment) The diff implements only a renderer capability (Reading A) and not the end-to-end user-visible feature (Reading B) implied by the SPEC's "Why"/CAP-1 prose. — Refuted: the original intent document (`_bmad-output/specs/spec-clock-upcoming-events/SPEC.md`) itself excludes data sourcing/syncing in its own Non-goals and Assumptions sections, explicitly deferring a "real (non-simulated) demonstration" — the diff matches the reading the intent itself selects.
  - `low` `reject` (intent-alignment) Two spec artifacts now exist with overlapping content: the planning `_bmad-output/specs/.../SPEC.md` and the derived `_bmad-output/implementation-artifacts/touch-ui/spec-clock-upcoming-events.md`. — Real duplication, but this is the build-auto workflow's standard artifact structure (a story spec is always derived from its planning-artifact source), not a defect caused by this story; unlikely to cause confusion in practice and not directly fixable without redesigning the workflow's artifact model.

## Design Notes

Row geometry (mirrors `_draw_status_lines`'s line-height pattern): `row_h = display.measure_text("Ag", config.FONT_SETTINGS_STATUS)[1]`. First row `y = (display.height - config.CLOCK_EVENTS_BAND_H_PX) + config.CLOCK_EVENTS_ROW_TOP_PAD_PX`; each subsequent row adds `row_h + config.CLOCK_EVENTS_ROW_GAP_PX`. Row text is one `draw_text` call of `hhmm + "  " + title` (or the truncated form) at `x = config.CLOCK_CORNER_PAD_X_PX`.

Truncation loop: measure `hhmm + "  " + title`; while `x + width > config.CLOCK_EVENTS_ROW_RIGHT_PX`, drop the last character of `title` and re-measure `hhmm + "  " + title + "..."`, until it fits or `title` is empty.

`events` equality check in `render()`: compare against `cache["events"]` with `!=` (works for `None`, `[]`, and lists of plain tuples/strings — no custom `__eq__` needed).

## Verification

**Commands:**
- `python3 -m pytest tests/test_clock_view.py -q` -- expected: all tests pass, including new events-band cases.
- `python3 -m pytest -q` -- expected: full suite green, no regression elsewhere (e.g. app-loop tests that call `ClockView.render()` without `events`).

## Auto Run Result

**Summary:** Extended `ClockView.render()` with an optional `events` param (up to 3 pre-formatted `(hhmm, title)` tuples), drawing them as left-aligned rows in the reserved 56px band, wired into the existing dirty-region cache-and-compare so `events` changes force a full redraw and `events`-unchanged ticks still take the seconds-only fast path.

**Files changed:**
- `src/config.py` -- added `CLOCK_EVENTS_ROW_TOP_PAD_PX`, `CLOCK_EVENTS_ROW_GAP_PX`, `CLOCK_EVENTS_ROW_RIGHT_PX`.
- `src/ui/clock_view.py` -- `render()`/`_cache`/`_full_redraw()` extended for `events`; new `_draw_events()` and `_events_row_text()` (char-truncation with `...`, capped title length, defensive-copy cache storage).
- `tests/test_clock_view.py` -- 8 new tests covering every I/O Matrix row, plus a vertical-bound assertion added during the patch pass.

**Review findings breakdown (14 findings, 1 review pass):**
- Patched (3 entries: 2 low, 1 medium): zero-margin band geometry now asserted in test; `cache["events"]` now stores a defensive copy instead of a live reference; truncation loop now bounded by a 60-char title cap.
- Deferred: none.
- Rejected (10 entries, with reason): spec/code mismatch citing `_layout()` (fix would require editing this spec, an excluded route); untested `local is None` + events branch (same plain `==` compare already covered elsewhere, no distinct risk); empty title/hhmm producing a blank row (unlikely given the caller-contract in Assumptions, fix is more than a direct correction); dead-code fallback line (cosmetic, no behavioral effect); fallback-width possibly exceeding x=310, both as a code-level claim and as an acceptance-criteria-claim variant (refuted by measurement: max 128px width, well under 310px); malformed `events` tuple shape and `None`/non-str `hhmm`/`title` causing crashes, both (unreached today, no production caller passes `events`, and validating internal-contract-only inputs contradicts this codebase's trust-internal-callers convention); Reading-A-vs-Reading-B intent divergence (refuted by the original SPEC.md's own Non-goals/Assumptions, which already scope out data sourcing); duplicate spec artifacts (expected build-auto workflow structure, not a defect from this story).

**Follow-up review recommendation:** `false`. Only one `medium`-verdict entry was patched (the truncation-loop cap) and no `high` entries existed — below the two-or-more-medium threshold for a first pass.

**Verification performed:** `python3 -m pytest tests/test_clock_view.py -q` -- 33 passed. `python3 -m pytest -q` (full suite) -- 555 passed, no regressions, both before and after the patch pass.

**Residual risks:** None identified beyond the rejected/deferred findings above -- the events data source itself remains unbuilt by design (out of scope per the originating SPEC.md), so no production caller passes `events` yet; wiring a real provider is a separate future story.
