---
title: 'Recover Wi-Fi automatically and show the Device address'
type: 'feature'
created: '2026-09-06'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: '843137d67566a2688841f4557d5180c73746a1ba'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/wifi-config/epic-1-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** After stories 1.1–1.2, unconfigured Setup works and phone join persists, but a configured Device never retries home Wi-Fi, never falls back to Setup after repeated failures, and never shows how to reach it on the TFT—so router changes leave it silently unreachable.

**Approach:** Drive store-owned station connect/reconnect with a consecutive terminal-failure counter that enters `SETUP_AP` at exactly three; have `App` alone reduce network events into continuous Setup overlays and ≥10s station-IP overlays; ship a flash proof checklist (not host-as-device-proof) that records STA/AP coexistence before claiming browser terminal responses.

## Boundaries & Constraints

**Always:**
- `NetworkCoordinator` sole WLAN/socket owner; emit typed events only—never call display/`App` mutators.
- `App` sole product-state and TFT status-layer writer via compositor after base render.
- Exactly three consecutive terminal station failures (boot attempts or post-drop reconnects) → `SETUP_AP`; reset the counter only after a successful persist path that emits station online.
- Setup overlay continuously shows `PiCalendar-Setup` and `192.168.4.1`; each successful station connect/reconnect shows assigned IPv4 ≥10s (wrap-safe deadline).
- Pure policy/event reduction host-testable without `machine`/`network`/`ntptime`; cooperative bounded ticks (NFR1).
- Preserve SettingsStore AD-3 protocol, setup join-then-persist order (AD-2), HTTP allowlist, GPIO/SPI/TFT pins and display lifecycle.

**Never:**
- Claim flashed STA/AP coexistence, gateway, scan-during-AP, socket fairness, browser terminal response, or TFT legibility from host pytest alone.
- Silently redesign around unsupported coexistence—unsupported device result blocks the browser-result claim for redesign.
- Log or return Wi-Fi/Admin plaintext; delete invalid settings on boot; add Config/login routes; change physical reset/GPIO.
- Let web or coordinator draw TFT; regress SETUP_AP open-AP + candidate handshake from 1.1/1.2.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Boot configured | Valid settings load | Bounded STA attempts; emit connecting then online+IP on success | Terminal fail increments count |
| Three boot fails | Three consecutive terminal STA fails | Enter `SETUP_AP`, emit setup_status | Stay recoverable; no crash |
| Drop then recover | Was online; `isconnected` false | Reconnect attempts; online+IP on success | Terminal fails accumulate |
| Three post-drop fails | Three consecutive terminal fails after drop | Enter `SETUP_AP` | Same Setup AP as unconfigured path |
| Persist-gated reset | Setup candidate commit succeeds | Failure count resets; station online emitted | Persist fail: no online, count not reset |
| Setup overlay | `setup_status` event | TFT continuous `PiCalendar-Setup` + `192.168.4.1` | No display call from coordinator |
| Station IP overlay | `station_status` online with IP | Show IPv4 ≥10s then clear overlay dwell | Missing IP: no false address |
| Coexistence proof | Flashed Pico W 1.29 checklist run | Recorded observations in proof artifact | Unsupported → block browser claim |

</intent-contract>

## Code Map

- `src/device/network/coordinator.py:78–166,285–354` -- Replace STATION_ONLINE stub with store-credential STA connect/reconnect; add consecutive terminal-failure counter → SETUP_AP at 3; keep candidate join/persist/`_emit` unchanged; never call App/TFT.
- `src/device/network/models.py:9–122` -- Reuse `boot_mode_for_settings`, `setup_ap_status_event`, `station_status_event`/`station_error_event`; add pure failure-count helpers if needed (no device imports).
- `src/device/settings_store.py` -- Read-only load of Wi-Fi fields for STA attempts; reuse `commit` only on setup-candidate success path already wired.
- `src/config.py:97–116` -- Add `STATION_FAILURE_LIMIT=3`, `STATION_IP_DISPLAY_MS` (≥10000), optional reconnect backoff; leave TFT pin/SPI constants untouched.
- `src/app.py:30–80,307–315` -- Drain network events each step; own overlay state + wrap-safe IP dwell; pass status into compositor; sole TFT writer.
- `src/ui/compositor.py` + `src/ui/components.py` -- Extend status layer: Setup banner + station IP text draw-last after base; keep UNSYNCED badge behavior.
- `main.py:56–90` -- Wire event list into App; preserve `tick` then `app.step`; stop treating configured boot as secrets-only NTP without store STA.
- `src/device/network/proof.py` pattern + new checklist under `_bmad-output/implementation-artifacts/wifi-config/` -- Flashable coexistence/gateway/scan/fairness/browser/TFT recording (human-filled rows).
- Continuity 1.2: join-then-persist order, HTTP server injection, deferred blocking-scan fairness → device proof here.
- Read-only: `docs/hardware_configuration.md` pins; epic-1-context; do not mutate display lifecycle ownership.

## Tasks & Acceptance

**Execution:**
- `src/config.py` -- Add failure-limit and ≥10s IP-display constants (and any reconnect cadence) without touching pin/SPI/orientation -- checked-in budgets for recovery and overlay dwell.
- `src/device/network/models.py` (+ pure helpers if split) -- Failure-count increment/reset/threshold policy host-testable -- three-failure rule without device imports.
- `src/device/network/coordinator.py` -- Store-owned STA connect at configured boot; watch drop while online; bounded reconnect; after exactly three consecutive terminal failures enter SETUP_AP and emit setup_status; reset counter only when persist-success path emits online; keep candidate HTTP path intact -- FR4 recovery.
- `src/app.py` + `src/ui/compositor.py` + `src/ui/components.py` -- Consume network events; continuous Setup overlay; station IP overlay ≥10s wrap-safe; draw via status layer only -- FR5 address visibility.
- `main.py` -- Inject event sink into App; keep cooperative loop -- close unread-list gap from 1.2.
- `tests/test_station_recover*.py`, `tests/test_app_network_overlay*.py` (names flexible) + extend coordinator/app suites -- Cover I/O matrix with FakeWlan/FakeTicks; AST hygiene for pure modules.
- `_bmad-output/implementation-artifacts/wifi-config/proof-1-3-sta-ap-coexistence.md` (+ optional harness hooks) -- Checklist for flashed Pico W 1.29 observations; host tests must not fill device rows -- gate browser-result claim.

**Acceptance Criteria:**
- Given a complete saved settings record, when the Device starts or loses a formerly-working station connection, then it makes bounded station attempts and enters `SETUP_AP` after exactly three consecutive terminal failures.
- Given a successful setup join, when the online station event is processed, then the coordinator resets its failure count only after persistence succeeds and `App` remains the sole writer of product state.
- Given `SETUP_AP`, when `App` receives the setup status event, then the TFT overlay continuously shows `PiCalendar-Setup` and `192.168.4.1` without web/network code calling display APIs.
- Given each successful station connection or reconnection, when its assigned IPv4 address is received, then `App` directs the overlay to show that address for at least 10 seconds while preserving the clock/calendar rendering lifecycle.
- Given this story is ready to close, when the Pico W 1.29 proof checklist is available for flash, then it records fields for STA/AP coexistence, `192.168.4.1` gateway, scan-during-AP, bounded socket fairness, browser terminal responses, flash commits, and TFT legibility separately from host-test results; an unsupported coexistence result blocks the browser-result claim rather than silently changing design.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 21 findings — high 0, medium 10, low 2, false 6, maybe-false 0, reject 3
- findings:
  - `[false]` `[reject]` Spec Always “persist-only” reset vs store reconnect reset — evidence: epic/matrix require consecutive-failure streaks; store online correctly resets; Always targets setup join (no reset before persist), not forbidding reconnect reset.
  - `[medium]` `[patch]` sprint-status still backlog — set `1-3-…` to review then done on finalize.
  - `[low]` `[reject]` Code Map line ranges stale — fix would edit this build’s spec; rejected.
  - `[false]` `[reject]` Spec Change Log / Review Triage empty pre-review — expected until this pass; now populated.
  - `[medium]` `[patch]` Post-drop SETUP_AP test under-proven — now ticks AP activation and asserts `setup_status`.
  - `[medium]` `[patch]` NTP armed while STATION_CONNECTING — main holds sync False for connecting/setup; App enables on station online.
  - `[low]` `[reject]` Overlay kind strings duplicated in app/components — unlikely everyday defect; shared-constant refactor not worth complexity.
  - `[low]` `[reject]` Long SSID not truncated on TFT — everyday short Setup SSID; truncation adds layout complexity.
  - `[false]` `[reject]` Open networks blocked by empty password — AD-3 Wi-Fi password length rules require non-empty; intentional.
  - `[false]` `[reject]` TFT silent during connecting retries — ACs require Setup continuous + online IP ≥10s, not connecting affordance.
  - `[medium]` `[patch]` Proof host count stale (229) — updated to 232 collected.
  - `[medium]` `[patch]` Compositor network-key invalidate untested — added clear→full invalidate/redraw coverage.
  - `[false]` `[reject]` Badge+overlay same-frame `elif` skips network invalidate — badge invalidate already restores base when both change.
  - `[low]` `[reject]` Design Notes omit reconnect gap — fix would edit this build’s spec; rejected.
  - `[medium]` `[patch]` IP-less online left prior station IP — App clears overlay before optional IP apply.
  - `[medium]` `[patch]` NTP SyncCommand expires mid-associate — same sync-gating fix as connecting find.
  - `[medium]` `[patch]` SETUP_AP enter deferred setup_status — `_enter_setup_ap_from_failures` now calls `_activate_setup_ap()`.
  - `[false]` `[reject]` Persist-only claim vs store reset (edge claim) — same as first finding; reconnect reset is correct.
  - `[medium]` `[patch]` (vg) main wiring only source-text — composition test shares events list coordinator→App→draw; sync enablement covered.
  - `[medium]` `[patch]` (vg) Calendar overlays unasserted — Calendar active-view overlay assertions added.
  - `[medium]` `[patch]` (vg) Network invalidate ghost path — same invalidate/redraw test as compositor finding.

## Design Notes

**Failure counting:** Count only terminal station outcomes (join fail/timeout/disconnect-without-recovery as defined in coordinator). Do not increment on transient “still connecting” ticks. Setup-candidate join failures while already in SETUP_AP do not re-enter SETUP_AP; counter reset is tied to persist-success → online emit (including first setup success).

**Overlay precedence:** While mode is SETUP_AP, show Setup SSID+gateway continuously (no 10s timeout). While station online with a dwell deadline, show IPv4; after dwell, clear address overlay but keep clock/calendar + UNSYNCED badge rules. Coordinator never draws.

**Coexistence gate:** Deliver checklist (+ optional serial markers). Leave observation cells empty until a human flashes; do not mark browser terminal response “proven” in Auto Run Result from host alone.

## Verification

**Commands:**
- `uv run pytest --ignore=.agents --ignore=.claude` -- expected: all tests pass including recovery + overlay coverage; prior 1.1/1.2 suites green

**Manual checks (if no CLI):**
- Flash Pico W 1.29 with proof checklist; fill observation rows for coexistence/gateway/scan/fairness/browser/TFT; if coexistence unsupported, stop and redesign—do not claim 1.2 browser terminal success.

## Auto Run Result

Status: done

**Summary:** Story 1.3 adds store-owned STA connect/reconnect with a three consecutive terminal-failure → `SETUP_AP` fallback, App-owned continuous Setup and ≥10s station-IP TFT overlays, NTP gated until station online, and a flash proof checklist with empty device rows for Pico W 1.29 coexistence (host must not claim device proof).

**Files changed:**
- `src/config.py` — failure limit, IP display ms, reconnect gap
- `src/device/network/models.py` — configured boot → STATION_CONNECTING; pure failure-count helpers
- `src/device/network/coordinator.py` — store STA connect/reconnect/drop watch; 3-fail → SETUP_AP; immediate setup_status on fallback
- `src/app.py` / `src/ui/compositor.py` / `src/ui/components.py` — event drain, overlays, sync gating, status-layer draw
- `main.py` — shared `network_events`; hold NTP until online
- `tests/test_station_recover.py`, `tests/test_app_network_overlay.py` (+ suite updates) — matrix + review patches
- `proof-1-3-sta-ap-coexistence.md` — host vs device observation gate
- Spec + `sprint-status.yaml` — story tracking

**Review:** Patched medium items (sync gating, stale IP clear, immediate setup_status, post-drop assert, composition/Calendar/invalidate tests, proof count, sprint status). Rejected: Always/persist wording-as-defect, open-network empty password, connecting TFT silence, badge/elif same-frame, overlay string share, SSID truncate, spec self-edits. Deferred: none.

**Follow-up review recommended:** true — risk: post-review patches to sync enablement, `_enter_setup_ap_from_failures` activation, and overlay clear/invalidate paths were not re-hunted by a second pass. Patched medium count ≥2 on first pass.

**Verification:** `uv run pytest --ignore=.agents --ignore=.claude` → 232 passed after patches. Device coexistence rows remain PENDING for human flash.
