---
title: 'Render an immediately legible Clock view'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: '8610c5546398a0d08e71308a6e263a47a35490ea'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-1-context.md'
warnings:
  - oversized
deferred:
  - summary: >-
      Ili9341DisplayPort / ILI9341.fill_rect still allocate a fresh row bytes buffer
      per fill instead of owning a reusable transfer buffer (AD-7 / NFR3 / AC).
    evidence: |-
      Device adapter maps DisplayPort fills to existing ILI9341.fill_rect which builds
      `bytes((hi, lo)) * width` each call. Fixing reusable buffers requires an ILI9341
      (or adapter-owned) scratch buffer upgrade beyond this story's thin optional adapter.
    location: >-
      src/device/display/ili9341.py
    severity: medium
---

<intent-contract>

## Intent

**Problem:** Story 1.1 left a pure `TimeSnapshot` model and a hardware-bound TFT splash, but no Clock view or `DisplayPort`—so glanceable time/date and trust cannot be drawn or host-verified.

**Approach:** Add the UI drawing contract (`DisplayPort` + host fake), shared top-right `UNSYNCED` badge helper, and a dirty-region Clock renderer that formats local snapshots into the specified 320×240 layout using only that contract; verify with host tests (no App loop / NTP).

## Boundaries & Constraints

**Always:**
- Draw only through `DisplayPort`: `width`/`height`, `fill_rect(x,y,w,h,color)`, `measure_text(text, font_id)`, `draw_text(text,x,y,font_id,color)`; half-open clipped rects; RGB565 ints; stable font IDs as config names.
- Clock layout: centered 24-hour `HH:MM` (~88px primary), secondary `SS` trailer (~30px) that must not shift HH:MM, date `DOW · MON D YYYY` (~14px secondary) below; palette from `src/config.py` RGB888 converted to RGB565 at the boundary; bg `#031406`, primary `#3dff7a`, secondary `#1c6b38`, unsynced orange `#ff6b3d`.
- Badge: all-caps `UNSYNCED` (~10px), fixed top-right, orange fill / background text, no reflow and no reserved space when absent; draw when `trust == unsynced`.
- Cold / no local: show `--:--` (and date omitted or placeholder-free) with badge; unsynced-with-local: advancing best-known local time + badge; synced: time/date only, no badge.
- Steady-state one-second path: dirty-region redraws only; no recurring allocation; invalidate/full redraw on view entry or badge-driven base invalidation.
- Pure UI modules (`src/ui/` except any thin device adapter) must import under CPython without `machine`/`network`/`ntptime`/`src.device`.

**Never:**
- Do not implement App loop, `ClockPort`/RTC, network worker/NTP, Calendar view, or view rotation (stories 1.3–1.5 / Epic 2).
- Do not allocate a full 320×240×16 framebuffer or change pin/SPI/MADCTL assignments.
- Do not claim on-device legibility from host runs; do not put secrets in config.
- Do not replace splash with an App-driven clock in `main.py` beyond optional composition that still compiles (prefer leave splash; Clock is exercised via FakeDisplayPort tests).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Synced valid local | `local` set, `trust=synced` | Full-bleed bg; centered `HH:MM`+`SS`+date; no badge draw | No error expected |
| Seconds-only tick | Prior cache for HH:MM/date; new `second` | Only SS (and any truly dirty glyph) regions redrawn; HH:MM origin unchanged; no new heap alloc on steady path | No error expected |
| Cold / no local | `local is None`, `trust=unsynced` | `--:--` (no usable date line content required); orange `UNSYNCED` top-right | No crash |
| Unsynced with local | Valid `local`, `trust=unsynced` | Same time/date layout as synced + badge; content positions unchanged vs synced | No error expected |
| Synced after unsynced | Badge was visible; now `synced` | No badge; base view may full-invalidate once so pixels under badge restore | No reserved empty badge slot |
| DisplayPort-only | Clock/badge call sites | Only port methods used; FakeDisplayPort records half-open rects + font IDs + RGB565 | Adapter (if present) owns SPI/windows/buffers |

</intent-contract>

## Code Map

- `src/ui/display_port.py` -- Create: `DisplayPort` Protocol/duck contract + `FakeDisplayPort` for host tests (records fills/texts; clips half-open; `measure_text`/`draw_text` by font_id).
- `src/ui/components.py` -- Create: shared `draw_unsynced_badge(display, visible)` (or equivalent) fixed top-right; no layout reservation when hidden.
- `src/ui/clock_view.py` -- Create: `ClockView` with prior-value cache, `invalidate()`, `render(snapshot)`; formats `HH:MM`/`SS`/`DOW · MON D YYYY`; dirty SS path; uses only DisplayPort + config colors/font IDs.
- `src/ui/__init__.py` -- Package marker.
- `src/config.py` -- Extend: RGB565 palette constants (or converters), stable `FONT_*` IDs, Clock layout metrics (glyph scales / badge box) as named constants — do not hardcode magic numbers in the renderer.
- `src/device/display/font.py` -- Extend glyph set for digits `0-9`, `:`, `-`, `.`, weekday/month letters needed by date/badge (`U`,`N`,`S`,`C`,`Y`,`M`,`A`,`J`, etc.) so a future ILI9341 adapter can draw; keep splash glyphs working.
- `src/device/display/ili9341.py` / new thin adapter under `src/device/display/` -- Optional but preferred: `DisplayPort`-shaped wrapper that maps half-open `fill_rect`/`draw_text` to existing `ILI9341` inclusive windows + scaled glyphs; adapter alone owns SPI/buffers. Not required for host AC proof if FakeDisplayPort covers contract.
- `src/time/model.py` -- Read-only: consume `TimeSnapshot` / `TRUST_*` / `DateTime` fields (weekday Mon=0 assumed for DOW labels, consistent with calendar epic).
- `main.py` -- Read-only / leave splash composition; do not introduce App loop.
- `tests/test_clock_view.py` (and/or `test_display_port.py`) -- Host: I/O matrix via FakeDisplayPort; dirty-region call counts; no badge when synced; purity AST for `src/ui/*` excluding device.
- `_bmad-output/.../epic-1-context.md`, `spec-1-1-...md` -- Continuity: substrate already present; ClockPort/App still out of scope.

## Tasks & Acceptance

**Execution:**
- `src/config.py` -- Add RGB565 colors, font IDs, and Clock/badge layout constants -- single ownership of metrics/palette.
- `src/ui/display_port.py` -- Define DisplayPort contract + FakeDisplayPort -- AD-11 host surface.
- `src/ui/components.py` -- Implement fixed top-right UNSYNCED badge draw/hide semantics -- AD-12 shared layer seed.
- `src/ui/clock_view.py` -- Implement dirty-region Clock renderer from TimeSnapshot -- FR3/UX-DR1–3/9.
- `src/device/display/font.py` -- Add glyphs required for clock/date/badge text -- enables device adapter text later.
- `src/device/display/` adapter (optional) -- Map DisplayPort to ILI9341 without changing pins/MADCTL -- keeps SPI ownership in device layer.
- `tests/test_clock_view.py` -- Cover I/O matrix, dirty SS path, badge presence/absence, DisplayPort-only usage, UI import purity -- host verification.

**Acceptance Criteria:**
- Given a valid local TimeSnapshot, when Clock renders, then it displays centered 24-hour HH:MM, a secondary SS trailer, and DOW · MON D YYYY using the specified 320×240 landscape layout and RGB565 palette.
- Given sequential one-second snapshots, when only seconds change, then only changed/dirty clock regions are redrawn, the HH:MM block does not shift, and the steady-state render path makes no recurring allocation.
- Given an invalid or unsynced snapshot, when Clock renders, then it shows --:-- before any usable time exists or the advancing best-known time thereafter, and draws the top-right orange UNSYNCED text badge without reflowing content.
- Given a synced snapshot, when Clock renders, then no success badge or reserved badge space appears.
- Given renderer code, when it draws the display, then it uses only the DisplayPort contract with clipped half-open rectangles, stable font IDs, and RGB565 colors; the display adapter alone owns controller windows, SPI handles, and reusable transfer buffers.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 33 findings — high 3, medium 10, low 12, false 8, maybe-false 0
- findings:
  - `[high]` `[patch]` HH:MM+SS row ~371px overflows 320 — lowered `FONT_SCALE_TIME` to 9 (with SS scale 4 → ~313px) and added fit/centering asserts.
  - `[medium]` `[reject]` Non-second field changes still full-screen redraw — AC2 mandates dirty path for seconds-only; once-per-minute full redraw is acceptable flicker; identical-snapshot case patched separately.
  - `[low]` `[reject]` No explicit DisplayPort Protocol type — duck contract + FakeDisplayPort satisfy AD-11; adding typing Protocol is cosmetic on MicroPython.
  - `[medium]` `[defer]` Adapter/ILI9341 allocates per-fill row bytes — deferred (see frontmatter); reusable buffer needs driver upgrade.
  - `[low]` `[reject]` Badge not 3px-rounded / scale ~8 vs ~10 — bitmap fill is rectangular; exact chrome deferred to panel QA, not host Fake surface.
  - `[medium]` `[patch]` Host tests missed fit/no-op/date styling/multi-tick/badge fill — strengthened `tests/test_clock_view.py`.
  - `[medium]` `[patch]` Device adapter imported `src.ui.display_port` — moved `clip_half_open`/`measure_font_text` to `src/gfx.py`.
  - `[false]` `[reject]` Empty Spec/Review logs mid-review — expected until this triage pass writes them.
  - `[low]` `[reject]` `rgb888_to_rgb565` duplicates `ili9341.color565` — intentional boundary conversion in config; tests now pin expected ints.
  - `[low]` `[reject]` `_format_hhmm`/`_format_date` allocate on full redraw — allowed outside steady-state SS path; design notes already scope no-alloc to SS.
  - `[low]` `[reject]` `display/__init__.py` does not export adapter — optional on-device import path is documented; splash `__all__` unchanged by intent.
  - `[low]` `[reject]` FakeDisplayPort records unclipped draw_text coords — tests need absolute origins; fills already clip.
  - `[false]` `[reject]` Unguarded hour IndexError — RTC/NTP producers must emit 0..23; validation not demonstrated for this story (same stance as 1.1).
  - `[false]` `[reject]` Unguarded minute IndexError — same as hour.
  - `[false]` `[reject]` Unguarded second IndexError — same as hour.
  - `[false]` `[reject]` Unguarded weekday IndexError — same as hour; Monday=0 convention deferred from 1.1.
  - `[false]` `[reject]` Unguarded month IndexError — same as hour.
  - `[medium]` `[patch]` Identical snapshot forced full redraw — added early no-op when fields+badge unchanged.
  - `[high]` `[patch]` Negative origin clips HH:MM — same scale fit fix as first high finding.
  - `[low]` `[reject]` Unknown font_id KeyError — only config FONT_* IDs are used; no demonstrated bad caller.
  - `[false]` `[reject]` `snapshot is None` AttributeError — render contract requires a TimeSnapshot; None not a demonstrated input.
  - `[high]` `[patch]` Claimed 320×240 centered layout falsified by metrics — same scale fit fix + centering asserts.
  - `[medium]` `[patch]` Seconds-only gate lacked minute-rollover regression test — added `:59`→`:00` full-redraw assert.
  - `[medium]` `[patch]` Badge invalidate test did not require second change — extended trust-flip with second tick.
  - `[medium]` `[patch]` Centering unasserted — added centered origin asserts (also locks 320 fit).
  - `[low]` `[patch]` Date font/color only checked as string — assert `FONT_DATE`/`COLOR_SECONDARY` on date op.
  - `[medium]` `[patch]` RGB565 palette test was tautological — pin independent expected RGB565 integers.
  - `[medium]` `[patch]` UNSYNCED orange fill never asserted — assert `COLOR_UNSYNCED` fill at `badge_rect`.
  - `[false]` `[reject]` On-device Clock not wired in main — intent Never leaves splash; host Fake is the verification surface.
  - `[low]` `[reject]` No-alloc not proven via GC hooks — design notes prefer call-pattern/precomputed SS strings.
  - `[low]` `[reject]` Badge missing 3px round (intent UX-DR6) — same bitmap limitation as blind chrome finding.
  - `[low]` `[reject]` Date letter-spacing absent — 5×7 scaled glyphs have no letter-spacing API; not on Fake surface.
  - `[low]` `[reject]` Ili9341DisplayPort untested on host — optional adapter; DisplayPort contract covered by Fake + purity tests.

## Design Notes

- Prefer FakeDisplayPort recording `(op, ...)` tuples over pixel buffers so tests assert regions/strings/colors without a framebuffer.
- Fix HH:MM block origin from measured `HH:MM` width alone; place `SS` to the right with a fixed gap so second changes never reflow hours/minutes.
- DOW/MON abbreviations: English three-letter (`Mon`…`Sun`, `Jan`…`Dec`); treat `DateTime.weekday` as Monday=0 (calendar epic convention; deferred doc from 1.1 still applies).
- Steady-state no-alloc: reuse format buffers / avoid building new strings when cached second-only path can blit from precomputed digit strings, or document MicroPython-friendly reuse of a single mutable draw cache object without per-tick `list`/`str` growth. Host tests may approximate by asserting no growth of FakeDisplayPort-side structures beyond dirty ops—prefer asserting call patterns over GC hooks.
- Badge helper is shared-compositor-ready: Clock may call it after base render in this story; full `UiCompositor` App loop arrives in 1.3+.

## Verification

**Commands:**
- `uv run pytest` -- expected: all host tests pass (time + config + new clock/DisplayPort)
- `uv run python -c "from src.ui import clock_view, display_port, components"` -- expected: imports succeed on host without device deps

**Manual checks (if no CLI):**
- Flash/device Clock rendering is out of scope here; user verifies panel legibility after deploy.

## Auto Run Result

Status: done

Summary: Story 1.2 delivers a host-verifiable Clock over DisplayPort — FakeDisplayPort, dirty-region `ClockView`, shared top-right UNSYNCED badge, config RGB565/font/layout metrics, extended glyphs, optional `Ili9341DisplayPort`, and `src/gfx` clip/measure helpers. Review patched the 320px layout overflow (time scale 9), identical-render no-op, device↔UI decoupling, and stronger matrix/regression tests.

Files changed:
- `src/config.py` — RGB565 palette, FONT_* IDs/scales (time=9 fits 320), Clock/badge layout constants
- `src/gfx.py` — shared `clip_half_open` / `measure_font_text` (UI + device)
- `src/ui/display_port.py` — FakeDisplayPort recording clipped fills
- `src/ui/components.py` — fixed top-right `draw_unsynced_badge`
- `src/ui/clock_view.py` — dirty SS path, identical no-op, full redraw + badge
- `src/ui/__init__.py` — package marker
- `src/device/display/font.py` — digits/punctuation/letters for clock/date/badge
- `src/device/display/adapter.py` — optional ILI9341 DisplayPort wrapper
- `tests/test_clock_view.py` — I/O matrix, fit/centering, dirty/rollover/badge/purity
- this spec — planning/review artifact

Review findings: patches applied (high×1 layout overflow group; medium×3: identical no-op, verification gaps, gfx decoupling); 1 deferred (ILI9341 reusable transfer buffer); rejected: Protocol type, badge rounding/letter-spacing, minute full-redraw vs SS-only AC, color565 dual helper, format alloc outside SS path, adapter package export, Fake draw_text clipping, DateTime bounds guards, None snapshot, unknown font_id, empty mid-review logs, on-device main wiring, GC no-alloc hooks, untested optional adapter.

Follow-up review recommendation: true — one high patch (layout scale fit) and three medium patches landed. Unverified residual risk: re-confirm HH:MM+SS still fits after any future scale/metric tweak, and that trust-flip+second-tick still forces base invalidate.

Verification:
- `uv run pytest` — 25 passed
- `uv run python -c "from src.ui import clock_view, display_port, components"` — succeeded
- Measured row width after patch: 313px on 320 panel

Residual risks: on-device Clock not composed in `main.py` (splash remains); panel legibility and 3px badge chrome need flash QA; ILI9341 per-fill allocation deferred; HH:MM height ~72px vs UX ~88 after fit compromise.

Blocking condition: none

Note: git commit skipped by orchestrator policy for this unattended pass; working tree remains dirty for the parent orchestrator to commit.
