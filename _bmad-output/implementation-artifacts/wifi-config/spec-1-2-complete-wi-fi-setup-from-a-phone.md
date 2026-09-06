---
title: '1.2 Complete Wi-Fi setup from a phone'
type: 'feature'
created: '2026-09-06'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: '8db6254dce899b1a94d3199fb90719ef1b0cfd10'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/wifi-config/epic-1-context.md'
warnings:
  - oversized
deferred:
  - summary: >-
      SettingsStore.commit still runs full 20_000-iteration PBKDF2 in one
      coordinator tick on setup success (AD-3 KdfJob budget not implemented).
    evidence: |-
      Pre-existing sync commit API from story 1.1; Connect success path newly
      invokes it in the render loop. Settle with chunked KdfJob (≤200 rounds/tick)
      or measured on-device tick budget evidence.
    location: >-
      src/device/settings_store.py / src/device/network/coordinator.py
    severity: medium
  - summary: >-
      wlan.scan() runs synchronously inside a coordinator tick on GET /scan and
      can stall the clock loop for an unbounded duration on device.
    evidence: |-
      Host fakes return instantly; flash fairness / scan-during-AP behavior is a
      story 1.3 proof concern. Settle with bounded/deferred scan or on-device timing.
    location: >-
      src/device/network/coordinator.py:_scan_ssids
    severity: medium
  - summary: >-
      Short LF-only or stalled partial HTTP requests may occupy a client slot
      until the peer disconnects (no request idle deadline).
    evidence: |-
      Parser waits for more bytes under size caps with no idle timer. Would be
      medium if true on Pico sockets; settle by injecting a stalled partial client
      and confirming slot exhaustion, then add REQUEST_IDLE_MS if needed.
    location: >-
      src/device/web/http_parse.py / server.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** In `SETUP_AP` the Device activates open `PiCalendar-Setup` but serves no phone Setup page, so Minh cannot scan SSIDs, submit Wi-Fi + Admin passwords, or join home Wi-Fi from the Device itself.

**Approach:** Add a bounded allowlisted setup HTTP surface under `src/device/web/`, wire it through `NetworkCoordinator` ticks, and run a single pending setup-candidate join (15s wrap-safe) that persists only after successful association, then returns the terminal browser result before dropping the AP.

## Boundaries & Constraints

**Always:** Setup routes only in `SETUP_AP`; allowlisted `GET` + `application/x-www-form-urlencoded` `POST`; one pending candidate; hold AP + requesting connection through the terminal browser response; persist via `SettingsStore.commit` only after join success; emit station online only after commit succeeds; 15s wrap-safe join deadline (`ticks_*`); pure HTTP parse/route/page policy and scan decode import no `machine`/`network`/socket; cooperative per-tick work so the clock loop never blocks; never log or return Admin/Wi-Fi plaintext; reuse SettingsStore + provisioning validators from 1.1.

**Never:** TFT overlays or App display mutation (story 1.3); three-failure STA→setup recovery (1.3); Config login/sessions/password-change/theme UI (Epic 2); claim on-device STA/AP coexistence or live browser proof from host tests (1.3 flash gate); persist-then-join (ignore older FR3/UJ-1 wording — AD-2 + Story 1.2 ACs win); delete invalid settings; change GPIO/SPI/TFT pins.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Setup GET | Mode `SETUP_AP`, allowlisted path | Serves fixed Setup HTML (two-screen flow, dark tokens, 44px targets, labeled show/hide) | Unknown path → fixed 404 close |
| Scan | GET `/scan` while AP up | Deduped safely decoded SSIDs; no BSSID/password in payload; empty → empty list for Rescan UI | Scan fail → empty list + usable Rescan |
| Next only | Screen1 Next with SSID+Wi-Fi pw | Client-only advance; no candidate, no persist, no STA join | N/A |
| Connect | Valid POST `{ssid,wifi_password,admin_password}` | One candidate; `Connecting…` path; STA join ≤15s; AP held | Concurrent POST → fixed `503 Busy` |
| Join+commit OK | STA associates; commit succeeds | Browser success before close; then deactivate AP; emit station online event | Named codes if emit fails (no crash) |
| Join fail | Bad password / timeout | No commit; AP/form retry; failure UI clears Wi-Fi pw only; keep SSID+Admin | Named join failure |
| Persist fail | Join OK, commit raises | Disconnect candidate STA; no online/IP event; AP/retry usable; named persist failure | Do not reset failure count |
| Bad HTTP | Malformed / oversized / wrong method / unsafe | Fixed error + close; no secret logging; tick returns promptly | Close client |

</intent-contract>

## Code Map

- `src/device/network/coordinator.py:33–293` -- Extend `_tick_setup_ap` / `tick` for HTTP poll + candidate join; inject `web` router + STA scan/connect; transition `SETUP_AP` → `STATION_CONNECTING` → `STATION_ONLINE` on success; keep `_emit` / WLAN injection; do not call App/TFT.
- `src/device/network/models.py:9–96` -- Wire `EVENT_STATION_*` factories; add setup-candidate / named join-persist error codes beside existing setup events; keep pure (no device imports).
- `src/device/settings_store.py:190–262` -- Reuse `commit(...)` only after successful join; leave load/AD-3 protocol unchanged.
- `src/provisioning/validation.py` + `verifier.py` -- Reuse SSID/password length rules + Admin PBKDF2 derive; add pure scan SSID decode/dedupe helpers here or under `src/provisioning/` (no device imports).
- `src/config.py:97–106` -- Reuse `SETUP_AP_*`, `SETTINGS_BASENAME`, `SYNC_COMMAND_DEADLINE_MS` (15s); add HTTP limit constants (request line/headers/body/clients/per-tick bytes).
- `main.py:56–87` -- Construct web router; pass into coordinator; preserve `tick` then `app.step` cadence; leave event→TFT unread (1.3).
- `src/app.py` -- Read-only for this story (no overlay wiring).
- `src/device/network/mailbox.py` -- Leave NTP mailbox path; after successful setup, STA may still use transitional secrets NTP until 1.3 owns reconnect — do not regress SETUP_AP gate.
- **Create:** `src/device/web/` -- Allowlisted router + incremental HTTP/1.0–1.1 parser + fixed Setup templates/assets (inline CSS OK) + form→candidate mapping; setup routes only when mode is `SETUP_AP`.
- **Create:** tests under `tests/` for pure HTTP parse/route, scan decode, candidate policy, join/persist ordering with FakeWlan/FakeApWlan/FakeTicks/FakeFS (patterns from `tests/test_setup_ap_coordinator.py`, `tests/test_network_coordinator.py`, `tests/test_settings_store.py`).
- Continuity from 1.1: SettingsStore + open AP + event sink already boot unconfigured devices; extend, do not reimplement.
- Read-only distillate: `_bmad-output/implementation-artifacts/wifi-config/epic-1-context.md`; UX mocks `ux-designs/mockups/key-setup-ssid.html` + `key-setup-admin.html`.

## Tasks & Acceptance

**Execution:**
- `src/device/web/` (+ package) -- Implement bounded incremental HTTP server/router with allowlisted setup GET/POST, fixed Setup two-screen assets (tokens from DESIGN.md), HTML escaping, form parse of `{ssid,wifi_password,admin_password}`, and fixed errors for malformed/oversized/unsupported requests -- phone can open Setup on the AP.
- `src/provisioning/` (scan helpers) -- Pure SSID decode + dedupe for scan results; reject/omit undecodable entries; never surface BSSID or passwords -- host-testable list policy.
- `src/device/network/models.py` -- Add station status/error event helpers and named join/persist/busy codes -- typed events for success/failure without App mutation.
- `src/device/network/coordinator.py` -- In SETUP_AP ticks: serve HTTP; on Connect create one candidate, run STA join with 15s deadline while AP held; on success commit then emit online then flush browser success then drop AP; on join/persist failure keep AP/retry and map failure UI state; reject concurrent candidate with 503 -- story join handshake.
- `src/config.py` + `main.py` -- HTTP limits + wire web into coordinator composition without blocking sleep_ms(10) loop.
- `tests/test_setup_http*.py`, `tests/test_setup_candidate*.py` (names flexible) -- Cover I/O matrix with fakes; AST hygiene for pure modules; existing 1.1 suites stay green.

**Acceptance Criteria:**
- Given `SETUP_AP`, when a phone requests the Setup page, then only allowlisted setup routes are served and the page is a semantic mobile-only two-screen flow with approved dark tokens, ≥44px targets, and accessible labeled password show/hide.
- Given the first Setup screen, when scan results arrive, then it lists deduplicated safely decoded SSIDs with selection and Wi-Fi-password entry; empty results show manual Rescan with no auto-retry; no password or BSSID is displayed.
- Given SSID + required fields, when Next then Connect are used, then no network action or persistence occurs before the final Connect POST containing `ssid`, `wifi_password`, and `admin_password`.
- Given a valid final submission, when join begins, then the page announces `Connecting…` via `aria-live`, disables the primary button, keeps AP + request connection through the terminal result, and enforces the 15s wrap-safe deadline.
- Given join success and a successful candidate commit, when the terminal response is sent, then the browser receives success before its connection closes, the AP deactivates only afterward, and a station online event is emitted; given join or persistence failure, then nothing is committed, AP/form retry remains usable, and failure UI clears Wi-Fi password only while retaining SSID and Admin password.
- Given a malformed, unsupported, unsafely escaped, or over-limit HTTP request, when it is parsed, then the server emits a fixed error and closes it without blocking the render loop or logging secrets.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 34 findings — high 0, medium 25, low 2, false 6, maybe-false 1
- findings:
  - `[medium]` `[defer]` Success-path commit runs full PBKDF2 in one tick — deferred; pre-existing SettingsStore.commit contract from 1.1; needs KdfJob later.
  - `[medium]` `[patch]` GET /scan during candidate join called wlan.scan mid-connect — mid-join now passes `scan_fn=lambda: []`.
  - `[medium]` `[patch]` `_fail_candidate` did not disconnect STA on join timeout/fail — `_disconnect_station()` now runs in `_fail_candidate`.
  - `[medium]` `[patch]` Connect fetch `document.write` wiped UI on 400/503 plain text — only write when body looks like HTML; else failure banner.
  - `[low]` `[reject]` Client Next/Connect only gated on non-empty fields — server enforces 8–63; extra client rules not worth everyday complexity.
  - `[medium]` `[patch]` Failure SSID/Admin restore used fixed `setTimeout(300)` — prefill now chains after scan promise.
  - `[medium]` `[patch]` Failure HTML forced Screen 1 — failure now activates Screen 2 with banner + retained Admin.
  - `[false]` `[reject]` Spec I/O matrix vs Design Notes emit/AP order wording — rejected; must not edit this build's spec for its own sake; AD-2 Design Notes + code emit→flush→drop AP.
  - `[medium]` `[patch]` `test_next_is_client_only` never drove HTTP — strengthened to GET-only path with no candidate.
  - `[medium]` `[patch]` No host coverage for `ERROR_JOIN_FAIL` / thin matrix paths — added join-fail + related verification patches below.
  - `[low]` `[reject]` Unused `ERROR_*` / `ACTION_HOLD` placeholders — unused constants are not everyday defects.
  - `[false]` `[reject]` Open Wi-Fi passwords blocked by 8–63 rule — intentional AD-3 password length; not a defect.
  - `[medium]` `[patch]` (edge) Scan during candidate join — same fix as empty `scan_fn` mid-join.
  - `[medium]` `[patch]` (edge) Join timeout/fail left STA associated — same `_disconnect_station` in `_fail_candidate`.
  - `[medium]` `[patch]` (edge) `settings_store is None` after associate left STA up — covered by disconnect-in-`_fail_candidate`.
  - `[medium]` `[patch]` (edge) `ensure_listening()` False silent with AP up — emit-once `listen_fail` setup error.
  - `[medium]` `[patch]` (edge) Held Connect peer close invisible until join ends — `_poll_held_peer` releases held slot.
  - `[maybe-false]` `[defer]` (edge) LF-only/stalled partial request occupies client slot — deferred unverified; needs stalled-client evidence + idle deadline if true.
  - `[medium]` `[defer]` (edge) Blocking `wlan.scan` in tick — deferred to on-device fairness / 1.3.
  - `[medium]` `[patch]` (edge) `showBanner` dropped `aria-live` — `showBanner` sets `aria-live="polite"`.
  - `[medium]` `[patch]` (edge) Failure SSID prefill raced scan — same scan-promise prefill fix.
  - `[false]` `[reject]` (edge/claim) Failure HTML returns Admin plaintext — AC requires retaining Admin for retry; not logging; intentional embed.
  - `[medium]` `[patch]` (edge/claim) Connecting… lost aria-live via `showBanner` — same aria-live restore.
  - `[medium]` `[patch]` (vg) `ERROR_JOIN_FAIL` path untested — added `fail_connect=True` candidate test.
  - `[medium]` `[patch]` (vg) Timeout test did not assert Wi-Fi password cleared — assert wifi secret absent from failure body.
  - `[medium]` `[patch]` (vg) `main.py` SetupHttpServer wiring untested — composition asserts `SetupHttpServer` injection.
  - `[medium]` `[patch]` (vg) Parse errors not through SetupHttpServer — server-path oversized/malformed tests added.
  - `[medium]` `[patch]` (vg) Form validation only checked short Wi-Fi password — Admin/SSID rejection coverage added.
  - `[medium]` `[patch]` (vg) Success path did not pin browser-before-AP-drop — order-sensitive assert added.
  - `[medium]` `[patch]` (vg) 15s deadline wrap-safety untested — wrap-start FakeTicks timeout test added.
  - `[medium]` `[patch]` (vg other) Next client-only test thin — same GET-only strengthening.
  - `[false]` `[reject]` (intent) Slug implies finished phone journey vs host handshake — reading 2 is the epic story; flash/phone proof gated to 1.3.
  - `[false]` `[reject]` (intent) TFT/App status not wired — excluded by invocation epic boundaries / Never list for 1.3.
  - `[false]` `[reject]` (intent) Live STA/AP browser proof absent — explicitly deferred to 1.3 flash gate.

## Design Notes

**Authoritative join order (AD-2):** Join STA → `SettingsStore.commit` → emit station online → flush browser success → close clients → deactivate AP. Persistence failure after association: disconnect candidate, named failure, keep AP/retry, no online event. Do not follow FR3/UJ-1 “save then drop AP then join.”

**Allowlisted route table (binds unbound AD-4 paths for this story):**
- `GET /` — Setup page (both screens; client Next; server Connect).
- `GET /scan` — SSID list payload for Screen 1 / Rescan.
- `POST /connect` — sole candidate creator; fields `ssid`, `wifi_password`, `admin_password`.
- Concurrent Connect while candidate active → `503` fixed Busy body.
- No Config/login routes in this story.

**Copy:** Connecting banner = `Connecting…` (Story AC). Success banner may use `Connected!` / `Connected to {ssid}.` per DESIGN/mocks. Failure = EXPERIENCE join-failed copy (Wi-Fi pw cleared; Admin retained).

**Coexistence:** Implement and host-test the handshake; do not claim flashed STA/AP browser proof here — that closes under 1.3.

## Verification

**Commands:**
- `uv run pytest --ignore=.agents --ignore=.claude` -- expected: all tests pass including new setup HTTP/candidate coverage and existing 1.1 suites
- Focused new setup HTTP/candidate tests `-q` -- expected: I/O matrix green

**Manual checks (if no CLI):**
- After flash in SETUP_AP, phone on `PiCalendar-Setup` opening `http://192.168.4.1/` should show Setup (user-observed; do not claim from host).

## Auto Run Result

Status: done

**Summary:** Story 1.2 adds allowlisted Setup HTTP (`GET /`, `GET /scan`, `POST /connect`) under `src/device/web/`, wires it through `NetworkCoordinator` SETUP_AP ticks, and runs join-then-persist with AP + held Connect client through the terminal browser response. Review patches hardened mid-join scan isolation, STA disconnect on failure, listen-fail emit, held-peer close, aria-live Connecting…, Screen 2 failure retention, HTML-only document.write, and verification gaps.

**Files changed:**
- `src/device/web/` — incremental HTTP parse/route/pages/server + Setup UI
- `src/provisioning/scan.py` + `validation.py` — scan decode/dedupe + setup form field rules
- `src/device/network/models.py` — station events + named join/persist codes
- `src/device/network/coordinator.py` — HTTP poll + candidate join/persist/AP drop order
- `src/config.py` / `main.py` — HTTP limits + SetupHttpServer composition
- `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, `tests/test_network_coordinator.py` — matrix + composition coverage
- Spec + `sprint-status.yaml` — story tracking

**Review:** Patched many medium items (scan isolation, disconnect-on-fail, listen_fail, held peer, aria-live, failure Screen 2, prefill, document.write, join_fail/wifi-clear/main wiring/parse/form/order/wrap/Next tests). Deferred: sync PBKDF2 in commit tick; blocking `wlan.scan`; stalled HTTP idle (unverified). Rejected: open-network password rule, unused placeholders, Admin retention-as-return, spec self-edit, client-only length gates, intent phone/TFT/flash divergences.

**Follow-up review recommended:** true — risk: post-review patches to held-peer polling, failure Screen 2/prefill, and join disconnect ordering were not re-reviewed by a second hunter pass. Patched medium count ≥2 on first pass.

**Verification:** `uv run pytest --ignore=.agents --ignore=.claude` → 214 passed after patches.

**Residual risks:** On-device STA/AP coexistence and live phone browser proof remain for story 1.3; cooperative KdfJob and scan fairness still deferred; legacy `secrets.py` NTP path may still apply until 1.3 owns reconnect.
