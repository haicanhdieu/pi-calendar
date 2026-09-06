---
title: 'Apply Forest & Amber palette and redeploy to the Pico W'
type: 'feature'
created: '2026-09-06'
status: 'in-review'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/planning-artifacts/pico-w-calendar-clock/ux-designs/DESIGN.md'
  - '{project-root}/_bmad-output/planning-artifacts/pico-w-calendar-clock/briefs/addendum.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** DESIGN.md now specifies Forest & Amber (neutral near-black bg `#0a0a0a`, green hero `#3dff7a`, amber secondary `#ffb238`, red unsynced `#ff4d4d`), but firmware still seeds the old Deep Forest mono-green palette in `src/config.py`, so the device and host views do not match the approved design.

**Approach:** Update the RGB888 palette seeds to DESIGN.md, refresh any hard-coded RGB565 expectations in host tests, then deploy `main.py` plus recursive `src/` to the connected Pico W and reset so the physical display shows the new palette.

## Boundaries & Constraints

**Always:** Keep `COLOR_PRIMARY_RGB` as `(0x3D, 0xFF, 0x7A)`. Keep today-cell text and unsynced-badge text derived from `COLOR_BACKGROUND` (no new constants). Keep adjacent-month days on `COLOR_SECONDARY` per DESIGN.md (not the mockup's dimmer `#7f591c`). Preserve pin map, SPI, MADCTL, fonts, layout, and splash diagnostic colors. Deploy with the addendum recursive `mpremote` procedure; do not delete unrelated device files. Treat on-device appearance as observed only after flash/reset (or user confirmation).

**Never:** Do not retint `src/device/display/splash.py` navy/cyan checkpoint to Forest & Amber. Do not invent theme switching, brightness, or extra accent colors. Do not change calendar/clock layout or view rotation. Do not claim host tests prove the physical TFT.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Palette seeds match DESIGN | Updated RGB888 in config | `COLOR_*` RGB565 packs match independent `rgb888_to_rgb565` of the new triples | Host pack test fails if seeds drift |
| Clock secondary tier | Synced clock render | Seconds and date line use amber secondary; HH:MM stays green primary on near-black bg | No error expected |
| Calendar roles | Month grid render | Weekday header + adjacent days amber; today fill green / text bg; in-month green | No error expected |
| Unsynced badge | Trust state unsynced | Badge fill red `#ff4d4d`, text near-black bg | No error expected |
| Device redeploy | Connected Pico at documented port | Recursive `src/` + `main.py` copied, reset; boot checkpoint then Clock/Calendar in new palette | If port missing/unresponsive, stop and report; do not change wiring |

</intent-contract>

## Code Map

- `src/config.py` L19–34 -- Sole palette seeds: change `COLOR_BACKGROUND_RGB` to `(0x0A, 0x0A, 0x0A)`, `COLOR_SECONDARY_RGB` to `(0xFF, 0xB2, 0x38)`, `COLOR_UNSYNCED_RGB` to `(0xFF, 0x4D, 0x4D)`; leave primary unchanged; derived `COLOR_*` RGB565 follow automatically.
- `src/ui/clock_view.py` -- Consumes `config.COLOR_*` for bg/HH:MM/SS/date; no edit expected if seeds update.
- `src/ui/calendar_view.py` -- Consumes primary/secondary/bg for title, weekdays, today, adjacent; no edit expected.
- `src/ui/components.py` -- Unsynced badge uses `COLOR_UNSYNCED` fill and `COLOR_BACKGROUND` text; no edit expected.
- `tests/test_clock_view.py` L295–303 -- `test_palette_rgb565_matches_independent_packing` hard-codes old packs `0x00A0`/`0x1B47`/`0xFB47`; update expected RGB565 for new bg/secondary/unsynced (primary stays `0x3FEF`). Recompute via same packer: bg `0x0841`, secondary `0xFD87`, unsynced `0xFA69`.
- `tests/test_calendar_view.py` -- Asserts symbolic `config.COLOR_*` only; should pass after seed change without literal edits.
- `src/device/display/splash.py` -- Diagnostic BLACK/NAVY/CYAN/WHITE; read-only for this change.
- `_bmad-output/planning-artifacts/pico-w-calendar-clock/briefs/addendum.md` -- Deployment: `mpremote connect /dev/cu.usbmodem1101 fs cp -r src/* :src`, `fs cp main.py :main.py`, `reset`, optional `fs tree` / serial observe.
- Connected Pico W `/dev/cu.usbmodem1101` -- Redeploy target (path may change on reconnect).

## Tasks & Acceptance

**Execution:**
- [x] `src/config.py` -- Set Forest & Amber RGB888 seeds (bg/secondary/unsynced; primary unchanged) -- aligns firmware with DESIGN.md.
- [x] `tests/test_clock_view.py` -- Update hard-coded RGB565 pack expectations for the new seeds -- keeps the independent-packing guard truthful.
- [x] `tests/` -- Run `uv run pytest -q`; fix only regressions caused by this palette change -- host proof before flash.
- [x] Connected Pico W -- Per addendum: recursive `src/` + `main.py` copy, reset, confirm port/tree; note serial/display outcome -- ships the design to the device.

## Implementation Notes

- Host apply complete: Forest & Amber RGB888 seeds in `src/config.py` (bg `#0a0a0a`, secondary `#ffb238`, unsynced `#ff4d4d`, primary unchanged); pack-test expectations updated; `uv run pytest -q` → 146 passed.
- First recursive `mpremote fs cp -r src/* :src` failed with `No space left on device` (host `__pycache__` copied). Cleared on-device `__pycache__`, redeployed `.py` only + `main.py`, then reset.
- User reported white TFT after that deploy. Follow-up (2026-09-06): deleted junk nested `:src/src` (~94 KB), redeployed all `.py` only (no caches), hard reset. Serial: checkpoint log + `App loop starting (Clock view)` with no errors. On-device palette still Forest & Amber. Nested junk no longer retained.
- Physical TFT appearance not observed from the agent host; user should see navy/cyan `TFT READY` then Clock (green HH:MM / amber SS+date). If still pure white despite clean serial, escalate to transport/wiring — do not change pins.

**Acceptance Criteria:**
- Given DESIGN.md Forest & Amber tokens, when `src/config.py` seeds are read, then background is `#0a0a0a`, secondary `#ffb238`, unsynced `#ff4d4d`, and primary remains `#3dff7a`.
- Given the host suite, when `uv run pytest -q` runs after the seed and pack-test updates, then all tests pass including independent RGB565 packing.
- Given views that already bind roles to `COLOR_*`, when clock and calendar render on host fakes, then secondary-tier elements and the unsynced badge use the new amber/red values without layout changes.
- Given a responsive Pico on the documented (or rediscovered) serial port, when the addendum deploy+reset runs, then the device boots through the existing diagnostic splash and into Clock/Calendar using the new palette; if the port is unavailable, the failure is reported without hardware guessing.

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all tests pass
- `git diff --check` -- expected: no whitespace errors on touched files
- Device (when port present): addendum `mpremote` cp/reset sequence -- expected: responsive port, recursive `src/` present, visible boot checkpoint then themed UI

**Manual checks (if no CLI):**
- After reset, confirm Forest & Amber on-device (green HH:MM, amber seconds/date, red UNSYNCED when applicable) or record that observation needs the user if serial/display cannot be captured from the agent host.

## Auto Run Result

Status: in-review

Summary: Forest & Amber applied and redeployed. White-screen report after the first messy flash was followed up: nested junk `:src/src` removed, `.py`-only redeploy, hard reset. Serial now shows full boot through TFT checkpoint and Clock App loop with no ImportError/MemoryError; on-device palette still matches DESIGN. User must confirm the physical TFT; if white with this serial path, treat as hardware/transport.

Files changed:
- `src/config.py` — Forest & Amber RGB888 seeds (bg/secondary/unsynced)
- `tests/test_clock_view.py` — independent RGB565 pack expectations
- this spec / restore-display spec — white-screen incident + recovery notes

Verification:
- `uv run pytest -q` — 146 passed (prior host proof)
- On-device `src.config` — RGB `(10,10,10)/(61,255,122)/(255,178,56)/(255,77,77)`
- Serial after reset — `TFT initialized; showing boot checkpoint` then `App loop starting (Clock view)`
- `fs tree` — complete `:src` layout; no nested `:src/src`; ~556 KB free

Residual risks / caveats:
- Always deploy `.py` only (never host `__pycache__`)
- Do not use `fs cp -r src :src` when `:src` already exists (creates nested junk)
- TFT visual confirmation awaits the user; clean serial does not prove pixels

Blocking condition: none

Note: no commit; no pin/SPI/MADCTL changes.
