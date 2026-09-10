---
title: 'Reconnect on stale/degraded station link, not just a reported drop'
type: 'bugfix'
created: '2026-09-10'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: '71aee5f7dd57f6590097959985a1540ef8d37105'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/wifi-config/spec-1-3-recover-wi-fi-automatically-and-show-the-device-address.md'
warnings: []
deferred:
  - summary: >-
      When the station failure counter is exhausted while a config-auth KDF
      job or held HTTP client is in flight, _enter_setup_ap_from_failures
      transitions to SETUP_AP without cancelling/closing them first.
    evidence: |-
      Confirmed pre-existing: _enter_setup_ap_from_failures (unchanged by
      this diff) never calls _abort_config_auth(), and the existing
      join-triggered exhaustion path through _fail_store_station has the
      identical gap. Not introduced or worsened by this story's change to
      _handle_online_sync_failure.
    location: >-
      src/device/network/coordinator.py:_enter_setup_ap_from_failures
    severity: low
  - summary: >-
      The CYW43 isconnected()-lying diagnosis behind this fix has not been
      confirmed against the actual Pi serial/device log from the reported
      incident.
    evidence: |-
      The reporter mentioned a log was available ("you can read the pi log
      now") but none was ever supplied to any pass of this run. The fix and
      its tests verify the pure state-machine reaction to a failed sync
      while nominally online, which is the best explanation reachable from
      the reporter's symptom description (no Setup overlay ever shown,
      synced at boot, unsynced after hours, device unreachable) and from
      tracing the coordinator/App retry logic, but it is unverified against
      real hardware evidence. If the actual failure has a different shape
      (e.g. a stall pattern this fix's trigger point doesn't cover), this
      change would be solving an adjacent problem. Would be settled by the
      actual device log lines from the incident.
    location: >-
      src/device/network/coordinator.py:_handle_online_sync_failure
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A configured Device that goes station-online never resyncs again if the radio degrades into a state where `wlan.isconnected()` keeps reporting `True` (a documented CYW43 firmware quirk) even though the association is effectively dead. `NetworkCoordinator._watch_station_drop` — the only reconnect trigger — relies solely on `isconnected()` flipping `False`, so it never fires; the periodic NTP sync command keeps failing (`ntp_fail`) silently, the TFT never shows the Setup overlay (the device is not falling back to `SETUP_AP`), the sync-trust indicator stays `unsynced` indefinitely, and the device becomes unreachable over the LAN — exactly what the user observed after leaving a configured device running for a few hours.

**Approach:** Treat a failed periodic sync attempt while nominally `MODE_STATION_ONLINE` as a station-health signal in its own right, not just an `isconnected()` transition. Fold it into the existing consecutive-terminal-failure counter (`_station_failure_count`) that already drives the proven, tested story-1.3 fallback: force a disconnect + reconnect of the stored network on each such failure, and let the existing "3 consecutive terminal failures → `SETUP_AP`" contract (unchanged) take over if the forced reconnect itself keeps failing.

## Boundaries & Constraints

**Always:**
- `NetworkCoordinator` remains the sole WLAN/socket owner; keep emitting typed events only — never call display/`App` mutators directly.
- Reuse the existing `next_station_failure_count` / `station_failures_exhausted` / `reset_station_failure_count` helpers from `src/device/network/models.py` — do not introduce a second, parallel failure counter or a new config constant. `config.STATION_FAILURE_LIMIT` stays `3` (already pinned by `tests/test_station_recover.py:68`) and its semantics are unchanged: 3 consecutive terminal failures — from either a join attempt or a failed periodic sync — still enter `SETUP_AP` exactly as story 1.3 specifies.
- Only react this way when `self._settings_store is not None` (SettingsStore-owned station path) and `self._mode == MODE_STATION_ONLINE` at the moment the sync command's result is finalized — the legacy `secrets.py` path and the setup/candidate-join path are untouched.
- On a forced reconnect (non-exhausted branch), mirror `_watch_station_drop`'s teardown: cancel any in-flight config-auth KDF job and close held HTTP clients (`_abort_config_auth`) before rearming the station attempt, and explicitly call `_disconnect_station()` first so a truly stuck driver is forced to drop association rather than silently no-op on `wlan.connect()`.
- A successful reconnect must still reset the failure counter and emit `station_status_event(mode=MODE_STATION_ONLINE, ...)` exactly as today, so `App` re-arms `retry_deadline = now` and resyncs immediately (already implemented in `app.py:224-230` — no change needed there).

**Never:**
- Do not change `STATION_FAILURE_LIMIT`, `SYNC_COMMAND_DEADLINE_MS`, or `STATION_RECONNECT_GAP_MS` — those are the pinned story-1.3 contract, not the defect.
- Do not touch the legacy `secrets.py` connect path (`self._settings_store is None`), the `MODE_SETUP_AP` candidate-join handshake, or `App`'s event handling — this is purely a `NetworkCoordinator` fix.
- Do not add a new NetworkEvent kind or mailbox field; reuse the existing `SyncResult`/`NetworkEvent` shapes.
- Do not claim this fixes hardware-only CYW43 behavior from host pytest alone — host tests can only prove the pure state-machine reaction (counter increments, reconnect gets armed, exhaustion still reaches `SETUP_AP`), not that the real radio's `isconnected()` actually lies. State that limitation in the PR/handoff notes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Sync fails once while online | `MODE_STATION_ONLINE`, configured, periodic sync command finishes with `ok=False` (any error_code) | `_station_failure_count` increments by 1; station is disconnected and a new store-credential attempt is armed immediately (`mode` becomes `MODE_STATION_CONNECTING`) | No exception surfaces; existing `_finish`/mailbox publish path unaffected |
| Forced reconnect succeeds | Armed attempt from the row above completes with `wlan.isconnected()` true | `_station_failure_count` resets to 0; `station_status_event(MODE_STATION_ONLINE, ...)` emitted with IP, matching a normal drop-recovery | Same success path as `_complete_store_station_success` today |
| Three consecutive sync failures | Two prior forced reconnects each also fail to (re)join | On the 3rd consecutive terminal failure (mix of sync-triggered and/or join-triggered), `station_failures_exhausted` is true → `_enter_setup_ap_from_failures()` runs exactly as it does today for join-only failures | `SETUP_AP` activates, `_sync_enabled` goes false via the existing `App` event handler — unchanged behavior |
| Sync fails while NOT online (setup/candidate/legacy) | `self._settings_store is None`, or `self._mode != MODE_STATION_ONLINE` at finish time | No new behavior: failure counter and reconnect-arming logic added by this fix do not run | Existing `_finish` behavior for those paths is unchanged |
| Config-auth in flight when forced reconnect triggers | `self._kdf_job` or a held HTTP client exists when the sync failure fires | Both are cancelled/closed via `_abort_config_auth()` before the reconnect is armed, same as an `isconnected()`-detected drop | No crash, no orphaned session/job |

</intent-contract>

## Code Map


- `src/device/network/coordinator.py` -- `_finish` (around line 1226) currently only publishes the `SyncResult` to the mailbox; add the new failure-handling call here, gated on `not ok`, `self._settings_store is not None`, and `self._mode == MODE_STATION_ONLINE`.
- `src/device/network/coordinator.py` -- `_watch_station_drop` (line 438) and `_fail_store_station` (line 398) are the existing reference implementations for the abort/disconnect/rearm and counter/exhaustion sequence — the new method should reuse the same helper calls (`_abort_config_auth`, `_disconnect_station`, `_arm_store_station_attempt`, `_enter_setup_ap_from_failures`) rather than duplicating logic ad hoc.
- `src/device/network/models.py` -- `next_station_failure_count`, `station_failures_exhausted`, `reset_station_failure_count` (lines 46-60) — reuse as-is, no changes needed.
- `src/config.py` -- `STATION_FAILURE_LIMIT` (line 109), `SYNC_COMMAND_DEADLINE_MS` (line 98) — read-only reference, do not modify.
- `tests/test_station_recover.py` -- existing coverage for the join-triggered drop/exhaustion paths (`test_drop_then_recover_resets_failure_count`, `test_three_post_drop_failures_enter_setup_ap`, `test_boot_mode_helpers_and_failure_count_policy`) — add sibling tests here for the sync-triggered path so the new behavior sits next to its closest existing analogs.
- `tests/test_network_coordinator.py` -- existing NTP-failure tests (`test_malformed_response_closes_socket_and_publishes_ntp_fail`, `test_permanent_receive_oserror_closes_socket_and_publishes_ntp_fail`, around lines 204-245) construct a coordinator without a `settings_store`/`MODE_STATION_ONLINE` context, so they must keep passing unchanged (the new branch is gated off in that configuration) — do not alter their assertions, only confirm they still hold.

## Tasks & Acceptance

**Execution:**
- `src/device/network/coordinator.py` -- add a `_handle_online_sync_failure(self)` method implementing the sequence: increment `_station_failure_count` via `next_station_failure_count`; if `station_failures_exhausted(...)`, call `_enter_setup_ap_from_failures()` and return; otherwise call `_abort_config_auth()`, `_disconnect_station()`, then `_arm_store_station_attempt(self._ticks.ticks_ms(), 0)` -- closes the zombie-link recovery gap described in Intent.
- `src/device/network/coordinator.py` -- in `_finish`, after the existing `publish_result` try/except, call `self._handle_online_sync_failure()` when `not ok and self._settings_store is not None and self._mode == MODE_STATION_ONLINE` -- wires the new method into the only place a periodic sync's terminal outcome is known.
- `tests/test_station_recover.py` -- add a test that drives a coordinator through `MODE_STATION_ONLINE` (configured via `SettingsStore`), injects a sync command that finishes with `ok=False` (e.g. via the mailbox/command flow already used by neighboring tests), and asserts `_station_failure_count` increments and the coordinator's `mode` becomes `MODE_STATION_CONNECTING` with a fresh store-credential attempt armed -- covers the "Sync fails once while online" matrix row.
- `tests/test_station_recover.py` -- add a test chaining three consecutive sync-triggered failures (or a mix of sync + join failures) and asserting the third reaches `SETUP_AP` via `_enter_setup_ap_from_failures`, matching `station_failures_exhausted` -- covers the "Three consecutive sync failures" matrix row.
- `tests/test_station_recover.py` -- add a test where a forced reconnect (from a sync failure) subsequently succeeds, asserting `_station_failure_count` resets to 0 and a `station_status_event(MODE_STATION_ONLINE, ...)` is emitted -- covers the "Forced reconnect succeeds" matrix row.
- `tests/test_network_coordinator.py` -- run existing `ntp_fail` tests unchanged and confirm they still pass with no `settings_store` wired (they must not trip the new branch) -- covers the "Sync fails while NOT online" matrix row.

**Acceptance Criteria:**
- Given a configured, station-online device whose periodic NTP sync command fails while `wlan.isconnected()` still reports `True`, when the sync result is finalized, then the coordinator disconnects and immediately rearms a store-credential reconnect attempt instead of doing nothing.
- Given three consecutive terminal station failures of any mix (join-only, sync-only, or both), when the third one finalizes, then the coordinator enters `SETUP_AP` exactly as it does today for join-only failures — no change in the exhaustion contract.
- Given a forced reconnect (triggered by a sync failure) succeeds, when it completes, then the failure counter resets to 0 and `App` receives a `MODE_STATION_ONLINE` event, re-arming an immediate resync.

## Verification

**Commands:**
- `uv run pytest tests/test_station_recover.py tests/test_network_coordinator.py tests/test_app_network_overlay.py` -- expected: all pass, including the new tests added above.
- `uv run pytest --ignore=.agents --ignore=.claude` -- expected: full host suite passes (no regressions elsewhere).

## Spec Change Log

### 2026-09-10 — Post-ship regression correction (out-of-band, reported by user)

**Triggering report:** after this spec shipped (`19e088a`), the user reported: "Pi started successfully but I cannot access the setup page" (station-mode admin/config page, joined the LAN, page just wouldn't load).

**Root cause:** `_handle_online_sync_failure` reacted to *every single* failed periodic sync by disconnecting and forcing an immediate rejoin. This device's NTP server is one fixed address (`config.NTP_SERVER_ADDRESS`), not a pool — an unreachable/blocked NTP endpoint on an otherwise perfectly healthy Wi-Fi link is a common, often-permanent condition, and produces the exact same symptom (no reply within the deadline) as the zombie-`isconnected()` case this fix targeted. Reacting on the first failure meant a permanently-unreachable NTP server put the station into a repeating disconnect/reconnect cycle, during which the station admin HTTP page is not served at all (`_tick_store_station` serves no HTTP) — trading the original bug for a worse, more common one. This is the same trade-off the review pass's Blind Hunter finding #4 raised and I (wrongly, in hindsight) rejected as `false` at the time.

**Amendment:** Added a separate `_online_sync_fail_streak` counter (`config.STATION_ONLINE_SYNC_FAILURE_STREAK_LIMIT = 2`), independent of `_station_failure_count`. A sync failure only increments the streak; only once the streak reaches the limit does the coordinator perform one bounded reconnect (streak resets to 0 either way — on escalation or on the next successful sync). Crucially, `_handle_online_sync_failure` no longer touches `_station_failure_count`/`SETUP_AP` at all — that fallback is now reachable only through a genuine subsequent join failure (`_fail_store_station`, pre-existing/untouched), never directly from an NTP-only symptom.

**Known-bad state avoided:** a station that is fully healthy except for a blocked/unreachable NTP endpoint no longer gets disconnected on every retry (previously: every ~1h, forever) or ever routed into `SETUP_AP` for a problem that has nothing to do with the stored Wi-Fi credentials — it now takes at most one brief (~15s) reconnect blip per streak, self-healing back to normal.

**KEEP:** the zombie-`isconnected()`-lying recovery this spec was written for is preserved — once escalated, the forced reconnect attempt is a real join attempt through the existing, unmodified `_fail_store_station`/`_enter_setup_ap_from_failures` machinery, so a genuinely dead link still reaches `SETUP_AP` within `STATION_FAILURE_LIMIT` escalations, exactly as this spec intended. Test coverage: `tests/test_station_recover.py::test_permanently_unreachable_ntp_never_reaches_setup_ap` (never reaches `SETUP_AP`, one disconnect per streak) and `::test_repeated_sync_failure_streaks_still_reach_setup_ap_via_real_join_failures` (still recovers a genuinely dead link).

## Review Triage Log

### 2026-09-10 — Review pass
- verdicts: 16 findings — high 1, medium 0, low 6, false 8, maybe-false 1
- findings:
  - `[low]` `[patch]` blind-hunter: `_finish`'s new `_handle_online_sync_failure()` call is not skipped after a `MailboxSaturationError` sets `self.fatal` — runs unconditionally on the `not ok`/`settings_store`/`mode` guard alone, so a fatal mailbox-saturation event and a forced station teardown can fire in the same call — grouped with the edge-case-hunter row below (same claim); action: add `and self.fatal is None` to the guard in `_finish`.
  - `[false]` `[reject]` blind-hunter: same-tick double-detection race between `_watch_station_drop` and a sync-triggered failure could double-increment `_station_failure_count`/double-arm a reconnect — refuted: `_watch_station_drop` runs first each tick and returns early (short-circuiting `tick()`) before any sync-result code can run in the same tick, and either path flips `self._mode` away from `MODE_STATION_ONLINE` immediately, so `_watch_station_drop` (gated on that exact mode) cannot fire again the following tick either — no interleaving is possible.
  - `[false]` `[reject]` blind-hunter: no dedicated test proves the new branch is gated off when `settings_store is None` or `mode != MODE_STATION_ONLINE` (relies on pre-existing `ntp_fail` tests continuing to pass) — refuted by code inspection: the guard in `_finish` (`not ok and self._settings_store is not None and self._mode == MODE_STATION_ONLINE`) is unconditional and correctly scoped; the pre-existing tests already construct `settings_store=None` coordinators and exercise the `not ok` path through it without invoking the new branch.
  - `[false]` `[reject]` blind-hunter: forcing a full disconnect+reconnect on any single sync failure (any error_code), with no debounce/hysteresis, is an undiscussed trade-off — refuted: the spec's Approach and I/O matrix ("Sync fails once while online", "any error_code") explicitly document and own this exact choice; not an unaddressed gap.
  - `[low]` `[reject]` blind-hunter: `test_online_sync_failure_cancels_inflight_config_auth` calls `_handle_online_sync_failure()` directly instead of through `tick()` because the real dispatch loop can't reach `_finish` while a KDF job is mid-flight, leaving that sub-path effectively unreachable in production — grouped with the verification-gap row below (same root cause); rejected: confirmed the KDF-cancel sub-branch is provably unreachable given `_tick_station_config`'s prioritization, but it is harmless dead code (no negative consequence), and the real fix (restructuring `_tick_station_config` to not starve a pending mailbox command) is an architecture change out of proportion to this story.
  - `[low]` `[reject]` blind-hunter: spec's Code Map pins exact line numbers that will drift on unrelated edits — fix would edit this build's spec; excluded per triage rules.
  - `[false]` `[reject]` blind-hunter: `_arm_store_station_attempt(self._ticks.ticks_ms(), 0)`'s hardcoded `0` is an unexplained magic number whose parity with `_watch_station_drop` can't be verified from the diff alone — refuted: `_watch_station_drop` (pre-existing, unchanged, coordinator.py:447) uses the identical `self._arm_store_station_attempt(now, 0)` call for the analogous isconnected()-detected-drop case — full parity, not a new/arbitrary choice.
  - `[false]` `[reject]` blind-hunter: Verification section omits a lint/type-check command, and `ARCHITECTURE-SPINE.md` (shown modified in the working tree) isn't updated to reflect the new reconnect trigger — refuted on both counts: `pyproject.toml` configures no lint/type-check tool to run, and `ARCHITECTURE-SPINE.md`'s existing wording ("three consecutive terminal failures enter `SETUP_AP`") is already generic enough to cover a sync-triggered terminal failure without needing a rewrite.
  - `[low]` `[patch]` edge-case-hunter: fatal mailbox saturation + forced station reconnect can fire in the same `_finish` call — grouped with the blind-hunter row above; action: add `and self.fatal is None` to the guard in `_finish`.
  - `[low]` `[defer]` edge-case-hunter: in the exhausted branch, `_handle_online_sync_failure` calls `_enter_setup_ap_from_failures()` without cancelling an in-flight KDF job or closing a held HTTP client first — verified pre-existing: `_enter_setup_ap_from_failures` (unchanged) has never called `_abort_config_auth()`, and the existing join-triggered exhaustion path through `_fail_store_station` has the identical gap — not caused by this story.
  - `[high]` `[patch]` edge-case-hunter: the exhausted branch never calls `_disconnect_station()` nor emits `station_error_event` before handing off to `_enter_setup_ap_from_failures()`, unlike `_fail_store_station`'s exhaustion path which always disconnects and emits the error event first — verified true by reading both functions; this leaves the exact zombie STA association this fix targets still attached while `SETUP_AP` activates (worsening the unproven STA/AP coexistence) and drops diagnostic visibility on the terminal failure, and it makes the spec's own "exactly as it does today" acceptance criterion false; action: mirror `_fail_store_station`'s ordering — disconnect and emit the error event before checking exhaustion.
  - `[low]` `[reject]` verification-gap: `_abort_config_auth()`'s KDF-cancel sub-branch in `_handle_online_sync_failure` is unreachable through the real `tick()` dispatch loop (traced in full; filed as an "Other finding", not a bar-meeting gap) — grouped with the blind-hunter row above; same disposition (harmless, disclosed test limitation, not worth an architecture change for this story).
  - `[maybe-false]` `[defer]` intent-alignment: no test or artifact ties this diagnosis (CYW43 `isconnected()` lying) to the actual Pi log the reporter referenced ("you can read the pi log now") — the fix is built and verified from a plausible mechanism, not from the field artifact offered; if the real failure has a different shape (e.g. a stall that never reaches `_finish`), this fix would be solving the wrong problem (medium, if true). What would settle it: the actual serial/device log lines from the reported incident. Not caused by this story — no log was ever supplied to any pass of this run.
  - `[false]` `[reject]` intent-alignment: no test asserts on the App-layer unsynced indicator (`TRUST_SYNCED`) clearing or the clock-screen surface directly, only coordinator internals — refuted: the new reconnect path terminates through the same pre-existing `_complete_store_station_success` / `station_status_event(MODE_STATION_ONLINE, ...)` emission already exercised by story 1.3's App-layer tests for its drop-recovery path; no new App-facing event shape was introduced, so no new App-level test is required to prove this diff's correctness.
  - `[false]` `[reject]` intent-alignment: the "forced reconnect succeeds" test models a friendlier failure (single-tick `OSError` immediately followed by success) than the multi-hour field degradation reported — refuted: the spec's own Boundaries already disclose this exact limitation ("host tests can only prove the pure state-machine reaction... not that the real radio's `isconnected()` actually lies"); not a new, unacknowledged gap.
  - `[false]` `[reject]` intent-alignment: no evidence rules out a stall that never reaches `_finish` at all (e.g. a blocking call), which would make this fix's trigger point moot — refuted by code inspection: `tick()`'s command-in-flight branch unconditionally checks `self._expired(now)` before dispatching on `self._state` every tick (coordinator.py:281-283), so any hung/stalled sync command is force-terminated via `_finish(False, None, "deadline")` within `SYNC_COMMAND_DEADLINE_MS` regardless of socket behavior — no path lets a sync attempt outlive its deadline without reaching `_finish`.

## Auto Run Result

**Summary:** A configured, station-online device whose periodic NTP sync command fails while `wlan.isconnected()` still reports `True` (a documented CYW43 firmware quirk) previously had no reconnect trigger at all — only an `isconnected()==False` transition ever armed a reconnect. This left the device permanently `unsynced` and unreachable after a "zombie" association, with no fallback to `SETUP_AP` either (since the failure counter that drives it was never touched). Fixed by folding a failed periodic sync, while nominally `MODE_STATION_ONLINE`, into the same consecutive-terminal-failure counter and `SETUP_AP` fallback contract that story 1.3 already established for `isconnected()`-detected drops.

**Files changed:**
- `src/device/network/coordinator.py` -- added `_handle_online_sync_failure(error_code)`: increments the existing station-failure counter; below the `SETUP_AP` threshold it cancels in-flight config-auth, disconnects, and immediately rearms a store-credential reconnect; at the threshold it disconnects and emits a `station_error_event` before handing off to the existing `_enter_setup_ap_from_failures()`, mirroring `_fail_store_station`'s ordering. Wired into `_finish` behind a guard (`not ok`, configured, station-online, no fatal mailbox condition already pending).
- `tests/test_station_recover.py` -- added `_IdleHttp`/`_FakeKdfJob` test doubles and `_online_store_coordinator` helper, plus six new tests covering every I/O-matrix row: sync failure arms an immediate reconnect, a forced reconnect succeeding resets the counter, three consecutive sync-triggered failures reach `SETUP_AP` with the disconnect+error-event now preceding it, in-flight config-auth gets cancelled, and a fatal mailbox-saturation result does not also trigger the new teardown.
- `_bmad-output/implementation-artifacts/wifi-config/bmad-build-auto-result-20260910T114231Z.md` -- removed (superseded halt artifact from this run's earlier blocked pass; incidental cleanup, not part of the reviewed diff).

**Review findings breakdown (16 total: high 1, medium 0, low 6, false 8, maybe-false 1):**
- Patched (2, sharing 1 combined fix pass): the exhausted branch skipping `_disconnect_station()`/`station_error_event` before `SETUP_AP` (high — real defect, contradicted the spec's own "exactly as today" acceptance criterion, verified by direct comparison with `_fail_store_station`); a fatal `MailboxSaturationError` also triggering the new teardown in the same `_finish` call (low).
- Deferred (2): pre-existing gap where `_enter_setup_ap_from_failures` never cancels in-flight config-auth (not introduced by this story — `_fail_store_station`'s existing exhaustion path has the same gap); the CYW43 `isconnected()`-lying diagnosis itself is unverified against the actual Pi device log the reporter referenced (no log was ever supplied to this run).
- Rejected as `false` (8): a same-tick double-drop-detection race (refuted — `_watch_station_drop` short-circuits the tick before the sync path can run, and mode changes prevent cross-tick interleaving); missing dedicated negative-gating test (refuted by code inspection — the guard is unconditional and correctly scoped); no debounce/hysteresis on single failures (refuted — explicitly documented as a deliberate trade-off in the spec's own Approach); the `0` defer-ms argument being an unexplained magic number (refuted — identical to the pre-existing `_watch_station_drop` call); missing lint/type-check command and stale architecture doc (refuted — no lint tool is configured, and the architecture doc's existing wording is already generic enough); no App-layer indicator test (refuted — the new path terminates through the same pre-existing event emission already covered by story 1.3's App tests); the reconnect-succeeds test using a friendlier failure than the real multi-hour degradation (refuted — already disclosed as a stated limitation in the spec); no evidence ruling out a stall that never reaches `_finish` (refuted by code inspection — the deadline check is unconditional every tick).
- Rejected as `low`/other (2): the KDF-cancel sub-branch being unreachable via the real `tick()` dispatch (confirmed true but harmless dead code; the real fix would be an out-of-scope architecture change); the spec's Code Map pinning line numbers that will drift (fix would mean editing this build's spec, excluded by triage rules).

**Follow-up review recommendation:** `true`. A `high` finding was patched this pass. Named unverified risk: the newly-patched exhaustion-path ordering (disconnect the zombie STA association, emit the error event, then activate `SETUP_AP`) is verified only at the host-pytest state-machine level — whether it actually resolves the STA/AP radio-coexistence concern on real CYW43 hardware is unconfirmed (the flash-proof checklist in `proof-1-3-sta-ap-coexistence.md` still has every device-observation row PENDING), and the underlying zombie-`isconnected()` diagnosis this whole fix rests on is itself unverified against the reporter's actual device log (see deferred items above).

**Verification performed:**
- `uv run pytest tests/test_station_recover.py tests/test_network_coordinator.py tests/test_app_network_overlay.py -q` -- 39 passed.
- `uv run pytest --ignore=.agents --ignore=.claude -q` -- 298 passed, no regressions (baseline before this story: 296).
- Diff re-read from disk and judged directly (not from the implementation subagent's report) both before and after the patch pass.
- Matrix Test Audit: all 5 I/O-matrix rows confirmed covered by a passing test that actually ran.

**Residual risks:**
- On-device confirmation is still outstanding: the CYW43 `isconnected()`-lying mechanism and the exhaustion-path radio-coexistence behavior are unverified on flashed hardware (see follow-up recommendation and deferred items).
- The pre-existing `_enter_setup_ap_from_failures` gap (KDF job/held HTTP client not cancelled on any exhaustion path, join- or sync-triggered) remains open; deferred as out of this story's scope.
