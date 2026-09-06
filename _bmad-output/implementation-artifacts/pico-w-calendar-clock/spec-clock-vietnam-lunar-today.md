---
title: 'Add Vietnamese lunar date line under Clock today'
type: 'feature'
created: '2026-09-06'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: '0ea4f82b268b6f85ca7edba24e36bb47034d94f6'
context:
  - '{project-root}/_bmad-output/planning-artifacts/pico-w-calendar-clock/architecture/ARCHITECTURE-SPINE.md'
  - '{project-root}/_bmad-output/planning-artifacts/pico-w-calendar-clock/ux-designs/EXPERIENCE.md'
warnings: []
deferred:
  - summary: >-
      CPython vs MicroPython float parity for the Hồ Ngọc Đức lunar converter is unverified on device.
    evidence: |-
      Host golden vectors pass under CPython; no on-device spot-check of the same YMD→lunar triples exists. Settling evidence: flash firmware and compare a few known dates (including a leap-month day) against the host vectors.
    location: >-
      src/calendar/lunar.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Clock shows Gregorian today (`DOW · MON D YYYY`) but not today's Vietnamese lunar (âm lịch) civil date — the product reason for this device — so a glance cannot read both calendars on the primary surface.

**Approach:** Add a pure Gregorian→Vietnamese-lunar converter and a second centered Clock line under the Gregorian date that shows today's lunar day/month (with leap marked), recomputed from `TimeSnapshot.local` whenever the Gregorian date is drawn.

## Boundaries & Constraints

**Always:**
- Lunar conversion lives in pure `src/calendar/lunar.py` (no `machine`/`network`/`ntptime`/`src.device`); host-tested under CPython.
- Clock keeps DisplayPort-only drawing; lunar string is derived from `snapshot.local` Y/M/D inside the Clock full-redraw path (App loop arity unchanged).
- Microcopy is ASCII + existing middot so the 5×7 font can draw it; format `AL · D/M`, leap month `AL · D/M+` (add `/` and `+` glyphs if missing).
- Second line uses `FONT_DATE` + `COLOR_SECONDARY`, gap via a named config constant (same tier as Gregorian date); centered block still fits 320×240 without shrinking HH:MM.
- When `local is None`, omit both date lines (same cold-start rule as today).
- Midnight / day change continues to full-redraw Clock via existing snapshot field cache — lunar line updates with that redraw.

**Never:**
- Calendar-grid annotations, Can Chi, solar terms, holidays, or month-grid lunar digits (clock-only this story).
- Changing hardware pins, SPI, MADCTL, or palette seeds.
- Blocking Wi-Fi/NTP work or allocating on the steady-state seconds-only path.
- Claiming on-device behavior as observed; flash/redeploy is out of this story unless already covered elsewhere.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Synced with local | Valid `local` YMD | Gregorian date line + lunar line `AL · D/M` (or `…+` if leap) under it, both secondary/date font | No error expected |
| Leap lunar month | Local YMD maps to leap month | Lunar line ends with `+` after month | No error expected |
| Seconds-only tick | Same YMD; only `second` changes | SS dirty path only; lunar/date strings not redrawn | No error expected |
| Cold / no local | `local is None` | Placeholder HH:MM; no Gregorian date; no lunar line | No crash |
| Known conversion vectors | Fixed Gregorian YMD fixtures | Converter returns expected lunar day, month, leap flag | Assert exact values in host tests |

</intent-contract>

## Code Map

- `src/ui/clock_view.py:125-137` — `_format_date` Gregorian `DOW · MON D YYYY`; extend with lunar format helper and second draw in `_layout` / `_full_redraw` (today only one date line at `:263-334`).
- `src/ui/clock_view.py:174-226` — `render` / SS-only path; keep SS path free of lunar work; date+lunar refresh only on full redraw / invalidate.
- `src/ui/clock_view.py:249-296` — `_layout` centers time+date; include lunar height+gap so vertical centering stays correct (~69px free below date today).
- `src/config.py:69-72` — Clock metrics; add `CLOCK_LUNAR_GAP_PX` (and reuse `FONT_DATE`).
- `src/calendar/models.py:4-8` — annotation kinds still empty; do not require calendar annotation wiring for this story.
- `src/calendar/gregorian.py` — pure-logic neighbor pattern to mirror for `lunar.py`.
- `src/calendar/lunar.py` — **create** (docs stub only; file absent): `gregorian_to_lunar(y, m, d) -> (lunar_day, lunar_month, is_leap)` or small named tuple.
- `src/device/display/font.py` — `FONT_5X7` lacks `/` and `+`; letters uppercased on draw (`:379-384`); middot preserved.
- `src/app.py:307-315` — Clock render passes snapshot only; no lunar arg needed if view computes from `local`.
- `tests/test_clock_view.py` — FakeDisplayPort ops assert date string; extend for lunar line + layout; purity AST already covers `src/ui`.
- `tests/test_lunar.py` — **create** golden Gregorian↔lunar vectors (include at least one leap-month case and a non-leap neighbor).
- Continuity: `spec-1-2-…` locked Clock layout; `spec-2-1-…` locked empty annotations (leave grid alone).

## Tasks & Acceptance

**Execution:**
- `src/calendar/lunar.py` -- Implement pure Vietnamese lunar civil conversion for the local Gregorian YMD used by Clock; document supported year range in module docstring -- enables host-tested âm lịch without device imports.
- `tests/test_lunar.py` -- Cover I/O matrix conversion vectors (ordinary + leap) and CPython import purity -- locks correctness independent of UI.
- `src/device/display/font.py` -- Add `/` and `+` glyphs -- so lunar microcopy does not fall back to `?`.
- `src/config.py` -- Add `CLOCK_LUNAR_GAP_PX` (and any tiny related metric) -- single ownership of layout spacing.
- `src/ui/clock_view.py` -- Format lunar line; extend layout/full redraw/cache for the second line under Gregorian date; leave SS-only path unchanged -- surface the lunar date on Clock.
- `tests/test_clock_view.py` -- Assert lunar line present/absent per matrix, font/color, centered fit, SS path still skips lunar redraw -- verifies the outermost Clock surface.

**Acceptance Criteria:**
- Given a synced snapshot with local date, when Clock renders, then a second line under the Gregorian date shows `AL · D/M` (or `AL · D/M+` for leap) in date font and secondary color, and the full time+dates block remains horizontally and vertically centered within 320×240 without shrinking HH:MM.
- Given `local is None`, when Clock renders, then neither Gregorian nor lunar date lines are drawn.
- Given only the second changes, when Clock renders, then only the SS dirty region updates (no full redraw, no lunar reformat on that path).
- Given calendar view entry, when Calendar renders, then month cells are unchanged (still Gregorian day digits only; no lunar annotations required).
- Given host tests, when `uv run pytest` runs for lunar + clock suites, then conversion vectors and Clock surface assertions pass under CPython.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 13 findings — high 0, medium 5, low 3, false 4, maybe-false 1
- findings:
  - `[low]` `[reject]` Missing Calendar Gregorian-only regression assert — calendar_view untouched by this diff; intent is clock-only; everyday risk of silent grid lunar injection without a calendar edit is negligible.
  - `[false]` `[reject]` Invalid Gregorian month/day silently wrong in converter — NTP/RTC/clock_port emit calendar-valid YMD; no production path feeds invalid month/day into `gregorian_to_lunar`.
  - `[medium]` `[patch]` Out-of-range year can crash Clock full redraw — `_format_lunar` now catches `ValueError` and returns `None` so the lunar line is omitted.
  - `[low]` `[patch]` Inclusive year bounds 1900/2100 untested for success — added golden vectors `(1900,1,1)` and `(2100,12,31)` in `tests/test_lunar.py`.
  - `[medium]` `[patch]` `/` and `+` glyphs unverified — assert `"/" in FONT_5X7` and `"+" in FONT_5X7` in `tests/test_clock_view.py`.
  - `[low]` `[reject]` Spec Code Map / empty triage logs stale mid-run — fix would edit this build's spec; rejected per review rules.
  - `[maybe-false]` `[defer]` CPython vs MicroPython float parity undocumented — settle with on-device spot-check of host vectors; recorded in frontmatter `deferred`.
  - `[false]` `[reject]` `PURE_CALENDAR_MODULES` omits `lunar.py` — `tests/test_lunar.py` already AST-purity-checks `lunar.py` separately.
  - `[false]` `[reject]` `_layout` omits lunar when `date is None` while draw could show lunar — call sites always pass date and lunar from the same `local` (both None or both set).
  - `[false]` `[reject]` Edge: invalid month/day — same as above; unreachable from time sources.
  - `[medium]` `[patch]` Edge: year outside 1900–2100 crashes redraw — same fix as out-of-range year guard in `_format_lunar`.
  - `[medium]` `[patch]` Verification gap: `/`/`+` glyphs — same glyph membership asserts applied.
  - `[medium]` `[patch]` Verification gap: day-change does not assert lunar refresh — added Clock day-rollover test expecting `AL · 25/7` → `AL · 26/7`.

## Auto Run Result

Status: done

Summary: Clock view now shows today's Vietnamese lunar civil date as a second line under the Gregorian date (`AL · D/M` / leap `AL · D/M+`), backed by a pure Hồ Ngọc Đức converter in `src/calendar/lunar.py` (1900–2100) and host tests.

Files changed:
- `src/calendar/lunar.py` — new pure Gregorian→lunar converter
- `src/ui/clock_view.py` — lunar format, layout, draw; ValueError-safe omit
- `src/config.py` — `CLOCK_LUNAR_GAP_PX`
- `src/device/display/font.py` — `/` and `+` glyphs
- `tests/test_lunar.py` — conversion vectors, bounds, purity
- `tests/test_clock_view.py` — Clock surface, glyphs, day-change lunar
- `spec-clock-vietnam-lunar-today.md` — this spec / review trail

Review findings: patched medium×3 groups (year-range guard; glyph asserts; day-change lunar assert) plus low bounds vectors; deferred float-parity (unverified medium); rejected false/low/spec-edit findings as logged above.

Follow-up review recommendation: true — three medium patches on first pass. Unverified residual risk: MicroPython float results for the lunar converter vs host golden vectors have not been spot-checked on device after flash.

Verification:
- `uv run pytest tests/test_lunar.py tests/test_clock_view.py -q` → 30 passed
- `uv run pytest -q` → 161 passed

Residual risks: on-device flash still required for visual confirm; leap-boundary days can differ by one from some popular almanacs vs HND reference.

## Design Notes

User intent pulls âm lịch onto Clock ahead of deferred v2 calendar enrichment. Architecture already reserved `lunar.py`; annotation kinds stay empty so Epic 2's grid contract is untouched.

**Display format (locked by UX terse voice + font ASCII path):**
- Gregorian (unchanged): `Sat · Sep 6 2026`
- Lunar: `AL · 15/8` or leap `AL · 15/8+`
- `AL` = âm lịch marker (uppercase glyphs); middot matches Gregorian separator.

**Conversion:** Prefer a compact ported algorithm over a large precomputed table (Pico flash). Module docstring states the supported Gregorian year range; inputs outside that range raise `ValueError` (host-tested).

**Layout:** `block_h = time_h + DATE_GAP + date_h + LUNAR_GAP + lunar_h`; center as today. Do not reduce `FONT_SCALE_TIME`.

## Verification

**Commands:**
- `uv run pytest tests/test_lunar.py tests/test_clock_view.py -q` -- expected: all pass
- `uv run pytest -q` -- expected: full host suite still green

**Manual checks (if no CLI):**
- After flash (user-run): Clock shows Gregorian date with an `AL · …` line directly under it for today's Vietnam local date.
