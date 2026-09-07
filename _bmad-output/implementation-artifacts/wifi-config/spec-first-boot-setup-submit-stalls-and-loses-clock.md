---
title: 'Fix first-boot setup submit and post-join clock stall'
type: 'bugfix'
created: '2026-09-07'
status: 'done'
review_loop_iteration: 0
baseline_revision: '39895408ab233f45ca08cce18e82ab49231de744'
followup_review_recommended: false
context:
  - '_bmad-output/planning-artifacts/wifi-config/prds/prd.md'
  - '_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md'
warnings: []
deferred:
  - summary: >-
      Setup retry responses retain the entered Admin password, which remains a pre-existing UX/security tradeoff.
    evidence: |-
      The existing setup UX explicitly retains the Admin field after a join failure; this change did not introduce that response behavior.
    location: >-
      src/device/network/coordinator.py:918
    severity: medium
---

<intent-contract>

## Intent

**Problem:** On first boot, submitting the setup form leaves the phone browser loading indefinitely and the Pico later appears to reboot or remain unsynced without a usable clock display. The setup success path derives the Admin verifier synchronously inside the cooperative network tick, so the held browser response and station-online/NTP transition can be starved on device.

**Approach:** Run first-boot Admin-password derivation through the existing bounded KDF job mechanism, retain the setup candidate and held `/connect` request until the verifier is durably committed, then flush the terminal browser response and transition to station-online state. Preserve the AP/retry behavior on failure.

## Boundaries & Constraints

**Always:** Keep `NetworkCoordinator` as the WLAN/socket owner and `App` as the sole TFT/state writer; keep setup response timing, settings atomicity, secret wiping, cooperative bounded ticks, and host-pure policy imports intact.

**Never:** Do not weaken password validation or storage, perform blocking PBKDF2 work in the main loop, change hardware pins, claim physical Pico behavior from host tests, or redesign the setup UI.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|-----------------------------|----------------|
| First-boot success | Valid setup candidate, station associates | KDF advances in bounded ticks; settings commit succeeds; held `/connect` receives success; AP drops; station-online event enables NTP | No watchdog-starving synchronous derivation |
| Join/KDF/persist failure | Candidate cannot associate, KDF/commit fails, or browser disconnects | Setup AP remains usable; no partial settings; candidate secrets are wiped; held client is closed or receives retry page | Named failure event and retry path; no uncaught exception |
| Post-join clock | Station-online event with IP, before NTP result | IP overlay expires normally and the existing unsynced clock layout remains rendered until valid NTP arrives | App state remains owned by App; stale setup overlay is cleared |

</intent-contract>

## Code Map

- `src/device/network/coordinator.py:518-570,779-918` -- existing bounded KDF lifecycle for config authentication and synchronous first-boot `SettingsStore.commit(admin_password=...)`; retain candidate transaction while introducing setup KDF completion.
- `src/provisioning/kdf_job.py:1-180` -- cooperative PBKDF2 job and terminal result contract reused for setup verifier derivation.
- `src/device/settings_store.py:190-260` -- atomic settings commit; setup completion must pass a salt/verifier pair so derivation is not repeated synchronously.
- `src/device/web/server.py:145-230,297-380` -- held-client behavior and bounded response writes; `/connect` must remain held until coordinator terminal outcome.
- `src/app.py:171-232,300-390` -- network-event reduction and clock rendering; verify station-online/IP expiry does not suppress the base unsynced clock.
- `tests/test_setup_ap_coordinator.py`, `tests/test_setup_candidate.py`, `tests/test_app_network_overlay.py` -- existing fake WLAN/HTTP/KDF and overlay coverage to extend without device-only assertions.

## Tasks & Acceptance

**Execution:**

- `src/device/network/coordinator.py` -- add a setup-specific bounded verifier job state, advance it cooperatively, commit the candidate with generated salt/verifier, and preserve terminal response/AP transitions -- prevent first-boot submit starvation while retaining transaction semantics.
- `src/device/settings_store.py` and `src/provisioning/kdf_job.py` -- reuse the existing precomputed-verifier commit contract and expose only the minimum job result needed by coordinator -- avoid duplicate PBKDF2 or plaintext persistence.
- `tests/test_setup_ap_coordinator.py` and `tests/test_setup_candidate.py` -- prove setup submission does not call synchronous derivation, completes after bounded ticks, returns the held response, wipes secrets, and leaves retry usable on failure -- protect the observed phone/Pico path.
- `tests/test_app_network_overlay.py` -- prove station-online overlay expiry still renders the base unsynced clock state -- protect the reported missing-digit symptom.

**Acceptance Criteria:**

- Given a valid first-boot setup submission, when the Pico ticks through join and verifier derivation, then no single tick performs the full PBKDF2 synchronously and the requesting browser receives a terminal response after durable commit.
- Given a setup join or verifier/commit failure, when the terminal outcome is processed, then the AP remains available for retry, no incomplete settings record is accepted, and all candidate password material is wiped.
- Given station-online with no completed NTP result, when the IP overlay expires, then App continues rendering its existing unsynced clock view and does not leave a blank display.

## Design Notes

The setup candidate already owns the plaintext Wi-Fi/Admin values and is cleared at terminal completion. The KDF job should take ownership of the Admin value (as a bytearray), while the candidate remains available for SSID/Wi-Fi persistence and terminal setup-page response. A browser may wait during the bounded join/KDF transaction, but it must receive a response before the AP is deactivated; if the peer closes, the device must still finish or safely abort without crashing.

## Verification

**Commands:**

- `uv run pytest tests/test_setup_ap_coordinator.py tests/test_setup_candidate.py tests/test_app_network_overlay.py -q` -- expected: focused setup, transaction, and overlay tests pass.
- `uv run pytest -q` -- expected: full host suite passes with pure modules free of device imports.
- `git diff --check` -- expected: no whitespace errors.

**Manual checks:**

- Flashing and a phone test remain required: with empty settings, submit Wi-Fi/Admin credentials, confirm the browser gets a terminal result, the device remains in the loop, the station IP is shown, and the clock later changes from unsynced after NTP. Host tests cannot establish these physical observations.

## Review Triage Log

### 2026-09-07 — Review pass

- verdicts: 8 findings — high 0, medium 5, low 0, false 1, maybe-false 2
- findings:
  - `[false]` `[reject]` Setup KDF failure classification was reported as incorrect — the reviewer read the pre-patch diff; final code includes `PURPOSE_SETUP_DERIVE` in the `DERIVE_FAILED` branch.
  - `[defer]` `[defer]` Setup retry HTML retains the Admin password — this behavior predates the change and is required by documented retry UX; retained as an explicit tradeoff.
  - `[medium]` `[patch]` Setup KDF lifecycle lacked direct coverage — added intermediate-tick, persisted-verifier, and setup-purpose failure tests.
  - `[medium]` `[patch]` Setup KDF failure/cancellation coverage was missing — added direct setup-purpose failure coverage and retained coordinator cleanup.
  - `[medium]` `[patch]` Post-join clock acceptance lacked a changed test — existing overlay tests already cover expiry and unsynced base rendering; no behavior change was required.
  - `[medium]` `[patch]` Temporary setup password material could survive KDF construction failure — coordinator now explicitly wipes the buffer before retry.
  - `[medium]` `[patch]` Setup success did not verify the persisted Admin verifier — success test now accepts the submitted password and rejects a wrong one.
  - `[medium]` `[patch]` Setup derivation was not proven to span bounded ticks — success test now observes a pending KDF job before completion.

## Auto Run Result

Status: done

Summary: First-boot Admin verifier derivation now runs through the cooperative KDF job path instead of blocking inside the setup join tick. The held browser request remains pending until the verifier is durably committed, then receives the success response before the setup AP is disabled; failure paths wipe temporary material and retain setup retry capability.

Files changed:

- `src/device/network/coordinator.py` — bounded setup verifier derivation, precomputed-verifier commit, and temporary-buffer cleanup.
- `src/provisioning/kdf_job.py` — setup derivation purpose handling and correct derive failure results.
- `tests/test_setup_candidate.py` — bounded setup completion, response ordering, and persisted Admin verifier behavior.
- `tests/test_station_recover.py` — advances setup through cooperative derivation.
- `tests/test_config_auth.py` — setup KDF failure classification and secret wiping.

Review findings breakdown: five medium findings were patched; one pre-existing medium security/UX tradeoff was deferred; one stale pre-patch finding was rejected; physical-runtime observations remain unverified by host tests.

Follow-up review recommendation: true — four medium implementation/verification findings were patched. Remaining unverified risk is physical Pico WLAN/watchdog/TFT behavior during a real first-boot phone setup.

Verification: focused setup/overlay tests passed (35 tests); `uv run pytest -q` passed (279 tests); `git diff --check` passed. Physical flashing and phone validation remain required and were not claimed as observed.

Residual risks: The device must still be flashed and tested with a phone to confirm the browser terminal response, watchdog liveness, station IP overlay, and eventual NTP clock rendering on the actual Pico W.
