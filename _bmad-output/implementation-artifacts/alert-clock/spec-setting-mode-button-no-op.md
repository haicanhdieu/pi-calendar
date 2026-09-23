---
title: 'Make Setting Mode control enter device config mode'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: '03d64126e3ebf2d000bb8de47a8d752c7b46a1f1'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - _bmad-output/planning-artifacts/touch-ui/architecture/ARCHITECTURE-SPINE.md
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Settings screen now renders a SETTING MODE control, but touch handling recognizes only REBOOT; touching SETTING MODE dismisses Settings without changing device mode.

**Approach:** Make SETTING MODE a separate Settings tap target. On touch, show Press Flash, write the existing config-mode handoff flag, then reset so `main.py` boots `src/device/config_mode.py`. Treat “setting mode” as the existing config mode: `src/device/knock.py` already describes that boot as “settings mode.”

## Boundaries & Constraints

**Always:** Keep mode-flag filesystem work in `src/device/`; retain `App` as owner of touch decisions; preserve current REBOOT behavior and outside-tap dismissal; reboot only after handoff flag write succeeds.

**Never:** Import device modules or perform filesystem/network work in `src/ui/`; clear saved Wi-Fi settings; change boot-mode selection or config-mode lifecycle.

</intent-contract>

## Code Map

- `src/ui/settings_view.py` -- owns Settings drawing and reboot hit/flash helpers; SETTING MODE label was added here but has no target helper.
- `src/ui/components.py` -- defines `settings_reboot_rect()` and `settings_reboot_item_rect()`; add adjacent mode target geometry without overlap.
- `src/ui/compositor.py` -- owns Settings hit tests; route both Settings targets before deciding outside-edge dismissal.
- `src/ui/touch_state.py` -- pure `next_surface()` preserves Settings for the REBOOT target; mode taps are consumed before general surface transitions.
- `src/app.py` -- `_poll_touch()` recognizes the mode control before outside-dismiss handling; press flash and the injected device port preserve flag-before-reset ordering.
- `src/device/mode_flag.py` -- existing `request_config_mode()` writes handoff flag; reuse it through a device-side port.
- `src/device/clock_mode.py` -- composition root creates device ports and injects them into `App`.
- `main.py` and `src/device/config_mode.py` -- existing flag consumer and destination runtime; no boot-flow changes expected.
- `tests/test_app_loop.py`, `tests/test_touch_state.py`, `tests/test_settings_view.py` -- existing host coverage points for routing, geometry, and visual flash.

## Tasks & Acceptance

**Execution:**
- `src/ui/components.py`, `src/ui/settings_view.py`, `src/ui/compositor.py`, `src/ui/touch_state.py`, `src/app.py` -- define, draw, hit-test, and route distinct mode target -- prevent mode taps from falling through to outside-dismiss behavior.
- `src/device/reboot_port.py`, `src/device/clock_mode.py` -- reuse reset boundary to write existing flag then reset; preserve pure UI/core boundaries and existing boot split.

**Acceptance Criteria:**
- Given Settings is open, when user touches within SETTING MODE target, then Device writes config-mode handoff flag and requests reset only after successful write.
- Given mode-flag write fails, when user touches SETTING MODE, then Device does not reset and Settings remains available for retry.
- Given user touches REBOOT or outside both button targets, when touch registers, then existing reboot and dismissal behavior remains unchanged.
- Given flag is written and boot proceeds, when `main.py` consumes flag, then existing config-mode runtime starts and flag is cleared on entry.

## Spec Change Log

### 2026-09-23 — Memory-gate reimplementation
- Removed standalone ConfigModePort and mode target from the generic touch state machine; App consumes mode tap directly before dismissal routing.
- Reused RebootPort for flag-before-reset handoff. Deploy and memory-size checks now use `mpy-cross -O3` for modules deployed as `.mpy`; simulator stages those same artifacts.
- Verification: 687 host tests and artifact-aligned memory gate pass.

### 2026-09-23 — Pico deployment
- Deployed commit `d16c458` to `/dev/cu.usbmodem1101` with MicroPython 1.20.0-compatible `mpy-cross`; deployment memory gate passed and device reset completed.
- Read-only checks confirmed RP2040/MicroPython 1.20.0, deployed `app.mpy` and touch UI modules, plus preserved `.settings-v1` and `.settings-v1.bak` files.
- Physical SETTING MODE touch and resulting config-mode screen were not observed; retain as manual verification.

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 14 findings — high 0, medium 4, low 6, false 4, maybe-false 0
- findings:
  - `[medium]` `[patch]` Setting Mode tap had no App-level handoff coverage — Added tests for touch routing, Press Flash, flag-before-reset ordering, and failed-flag retry behavior; targeted modules passed.
  - `[low]` `[reject]` ConfigModePort does not catch reset callback exceptions — Production callback is `machine.reset()`, which terminates execution; if it unexpectedly raises, clock loop already catches and logs the exception, and persisted flag remains for the next reset. Extra guards add complexity for an exceptional hardware failure.
  - `[low]` `[reject]` Flag-write log omits underlying filesystem reason — Failure emits bounded `config_mode request failed`; exposing the underlying exception would require changing the existing flag API and is not needed to distinguish this handoff phase.
  - `[false]` `[reject]` Short flag write or close failure can falsely report success — `consume_config_mode()` treats file existence as the flag and does not inspect its contents; successful creation/write still requests the established boot path.
  - `[low]` `[reject]` Failed request lacks separate visible error feedback — Press Flash acknowledges the touch and failure restores the normal control for retry; no additional error state is required by the captured intent.
  - `[medium]` `[patch]` New mode target lacked geometry and transition assertions — Added separation/bounds checks and Settings-surface/deadline coverage; targeted modules passed.
  - `[false]` `[reject]` Implementation artifact uses wrong slug — Current `_bmad/custom/config.toml` and rendered freeform workflow both bind implementation artifacts to `alert-clock`, matching this output path.
  - `[low]` `[reject]` Manual verification combines several outcomes — Acceptance criteria separately name handoff write, config-mode startup, and flag clearing; splitting one manual-check bullet would not change what is observed, and review rules reject fixes that only edit this build's spec.
  - `[false]` `[reject]` Generated Graphify files are unrelated noise — Project instructions require `graphify update .` after code changes and keep one root graph; these are its generated outputs.
  - `[low]` `[reject]` ConfigModePort discards request exception details — The caller records the failed config-mode request phase; preserving exception details would require widening the existing flag API for a rare local filesystem failure.
  - `[false]` `[reject]` Setting Mode hit target overlaps guideline — Guideline target ends at y=94 and mode target starts at y=94 under current config, so hit areas are adjacent and do not overlap.
  - `[medium]` `[patch]` Existing tests did not cover mode tap success or failure — Added App-level and port-order coverage; targeted modules passed.
  - `[false]` `[reject]` Intent leaves mode ambiguous — `src/device/knock.py` describes its existing flag-and-reset config runtime as “settings mode”; the Settings screen is already open, so “switch Pi to the setting mode” selects the existing device mode.
  - `[medium]` `[patch]` Diff lacked test coverage at the Settings touch boundary — Added focused routing, failure, geometry, and state-transition checks; 70 tests passed across the three affected modules.

## Auto Run Result

Status: done

Summary: SETTING MODE is now a separate touch target. It shows Press Flash, writes the existing config-mode handoff flag, then resets; failed flag requests keep Settings open and restore the control.

Files changed:
- `src/ui/components.py`, `src/ui/settings_view.py`, `src/ui/compositor.py`, `src/ui/touch_state.py` — add and route distinct mode target.
- `src/app.py`, `src/device/reboot_port.py`, `src/device/clock_mode.py` — perform bounded flag-before-reset handoff from clock mode.
- `tools/deploy.py`, `tools/hostsim/sizes.py`, `docs/heap_budget.md` — compile deployed `.mpy` modules with size optimization and make gate match deployed artifacts.
- `tests/test_app_loop.py`, `tests/test_settings_view.py`, `tests/test_touch_state.py` — cover mode tap, request failure, target geometry, and surface retention.
- `graphify-out/GRAPH_REPORT.md`, `graphify-out/graph.html`, `graphify-out/graph.json`, `graphify-out/manifest.json` — refresh required root Graphify outputs.

Review findings: 4 medium findings were resolved in one grouped patch entry; 0 deferred; 10 rejected findings with evidence recorded in the dated Review Triage Log. Patched entries by verdict: medium 1, high 0. Follow-up review recommended: false.

Verification: 687 host tests passed; `git diff --check` passed; artifact-aligned `tools.hostsim` gate passed (clock resident 48,647/50,500 bytes; simulated boot allocation 114,080/115,000 bytes; 88,128 bytes free); `graphify update .` completed. Commit `d16c458` deployed successfully. Device touch behavior still requires visual confirmation.

Residual risk: the actual touchscreen-to-reboot-to-config-mode transition still needs confirmation on the Pico W after flashing.

## Design Notes

SETTINGS screen surface (`active_surface == "settings"`) differs from firmware config mode (`src/device/config_mode.py`). Keep that distinction: button requests the established flag-and-reset handoff; it does not turn the active clock-mode network coordinator into a second owner.

## Verification

**Manual checks:**
- On Pico W, tap SETTING MODE from Settings and confirm reboot followed by config-mode screen/admin setup behavior; confirm clock mode returns after the existing config-mode exit path. Host execution cannot prove this device transition.
