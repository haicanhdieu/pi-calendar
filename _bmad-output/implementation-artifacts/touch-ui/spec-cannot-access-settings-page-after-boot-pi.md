---
title: 'Restore LAN settings-page access after Pico boot'
type: 'bugfix'
created: '2026-09-13'
status: 'done'
baseline_revision: '4a0a236b9fbd81959e2516e4f44a7a1eaa561976'
review_loop_iteration: 1
followup_review_recommended: false
context:
  - 'docs/hardware_configuration.md'
warnings:
  - 'A first fix attempt (eager-load station web/session modules at STATION_ONLINE entry, in NetworkCoordinator.__init__) was flashed to the device and made things worse: it caused a different subsystem (display/UI render loop) to start throwing MemoryError on every tick, logged as repeating "App loop: MemoryError, recovered". Do not reintroduce eager module loading inside NetworkCoordinator.__init__ or immediately after any self._mode = MODE_STATION_ONLINE assignment without first checking free heap at that exact point in the real boot sequence (not just isolated).'
deferred:
  - summary: >-
      Confirmed heap-fragmentation root cause preventing SessionTable()
      construction on the first station request remains unresolved; settings
      still does not load on the real device.
    evidence: |-
      Confirmed via on-device micropython.mem_info(1) dump (see this spec's
      Handoff section) -- MemoryError on SessionTable() construction is
      deterministic every boot because the free heap is fragmented into
      thousands of 1-2 block allocations with no single contiguous run large
      enough for the module/table allocation. gc.collect() does not help
      (mark-sweep, not compacting). A prior eager-import attempt to fix this
      was reverted after it broke the display/UI render loop instead. See
      Handoff's "Recommended next steps" for candidate approaches.
    location: >-
      src/device/network/coordinator.py (station config lazy-import boundary)
    severity: high
  - summary: >-
      New unconditional gc.collect() call before every http.tick() dispatch
      in _tick_station_config may add unmeasured per-tick latency to the
      cooperative loop.
    evidence: |-
      Added immediately before the http.tick() call, this now runs on every
      station-online tick once assets are ready (not gated like the
      pre-existing asset-import gc.collect()), unlike the KDF path's explicit
      KDF_MAX_STEP_MS budget. What would settle it: on-device timing of
      gc.collect() duration at realistic heap fragmentation, and whether the
      main loop enforces any per-iteration time budget this could violate.
    location: >-
      src/device/network/coordinator.py:564-566
    severity: medium (unverified)
  - summary: >-
      tools/deploy.py's PRECOMPILE list has no test coverage asserting its
      contents or deploy behavior, including the newly added
      src/provisioning/session.py entry.
    evidence: |-
      Verified pre-existing -- no test infrastructure exists anywhere in the
      repo for PRECOMPILE; this diff does not introduce or worsen the gap,
      but it remains an untested deploy-critical path.
    location: >-
      tools/deploy.py:40
    severity: low
---

<intent-contract>

## Intent

**Problem:** After boot, the Pico receives LAN address `192.168.1.32`, but the owner cannot access its settings page through that address.

**Approach:** Identify the observable browser and serial failure at the station-online HTTP boundary, then make the narrowest recovery-safe correction and prove it with a host regression test plus flashed-device evidence.

## Boundaries & Constraints

**Always:** Preserve the cooperative `NetworkCoordinator` as the only WLAN/socket owner; keep station login/settings routes available only in `STATION_ONLINE`; make every allocation/listen/request failure secret-free, recoverable, and serial-visible; keep pure logic free of MicroPython hardware imports.

**Never:** Do not change pins, loosen admin authentication, expose setup routes on the LAN, report browser/device behavior as host-observed, or silently mask listener/allocation failures.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Station HTTP healthy | Configured Pico is `STATION_ONLINE`; browser requests `/` or `/settings` without a session | Redirect to `/login`, then render the login page | No error expected |
| Listener/asset failure | Station-online web construction, listen, asset import, or request processing fails | Existing cooperative loop remains alive, retry is bounded, and a named secret-free serial/event code is emitted | Browser can retry after the bounded retry interval |
| Reported field failure | Browser cannot reach `http://192.168.1.32/` after boot | Diagnostic evidence identifies whether this is connect/refusal/timeout, HTTP response, or redirect/auth behavior | Do not select an implementation fix until the failure class is known |

</intent-contract>

## Code Map

- `main.py:78-124` -- creates the settings-aware coordinator, runs `coordinator.tick()` in the cooperative loop, and prints otherwise-suppressed transient exceptions.
- `src/device/network/coordinator.py:230-276` -- routes `STATION_ONLINE` through drop detection and `_tick_station_config()` before NTP work.
- `src/device/network/coordinator.py:508-605` -- constructs/listens to the station web server, lazy-loads station assets, logs named failures, and dispatches login/password KDF actions.
- `src/device/web/server.py:94-130, 175-225, 389-452` -- owns the TCP listener/client lifecycle and dispatches station-online requests.
- `src/device/web/router.py:92-120, 123-168` -- `/` and `/settings` route contract; unauthenticated GET redirects to `/login`.
- `src/device/web/pages.py:122-146` -- exact login redirect and settings response builders.
- `tests/test_config_auth.py:93-124, 300-370` -- host coverage for routing/login/settings and listener/asset failure recovery.
- `tests/test_station_recover.py:78-109` -- host coverage that configured boot reaches `STATION_ONLINE` and emits its assigned IP; it does not prove a flashed board's TCP reachability.

## Tasks & Acceptance

**Execution:**
- `src/device/network/coordinator.py`, `src/device/web/server.py`, and the narrow responsible layer determined by device evidence -- correct the diagnosed station HTTP failure while retaining bounded retries and existing auth guards.
- `tests/test_config_auth.py` or a focused new test module -- add a regression that exercises the discovered failure and the external HTTP behavior.
- `_bmad-output/implementation-artifacts/wifi-config/` -- record pinned firmware/native-auth context and flashed-device serial/browser evidence for the fix if deployment changes native-auth firmware.

**Acceptance Criteria:**
- Given a configured device that has joined its LAN, when a browser requests `http://<displayed-ip>/` or `/settings` without a valid session, then it receives the existing redirect to `/login` rather than a connection failure or unrelated error.
- Given a station HTTP allocation, listener, asset, or request failure, when the coordinator handles it, then the app loop and station association remain recoverable and serial output contains the existing named secret-free phase/code.
- Given the fixed firmware flashed to the Pico, when it boots and shows `192.168.1.32`, then device evidence records the serial checkpoints and the browser's status/redirect/page result.

## Spec Change Log

## Review Triage Log

### 2026-09-14 — Review pass
- verdicts: 12 findings — high 1, medium 2, low 6, false 1, maybe-false 2
- findings:
  - `[false]` `[reject]` blind-hunter: except-Exception asset-import branch "doubles up" logging (`self._log("web_asset "+type)` then `_web_failure("asset",...)`) — refuted: `_web_failure` only emits its own `"web_"+phase` log once per phase (dedup via `_web_failures_emitted`), and the explicit `_log` call carries the exception type name the dedup log never includes; the pattern also pre-dates this diff (only `http.close_clients()` was added to this branch), so it is not new duplication.
  - `[maybe-false]` `[defer]` blind-hunter: new unconditional `gc.collect()` before every `http.tick()` call (coordinator.py:564-566) adds unmeasured per-tick cost to the cooperative loop, unlike the KDF path's explicit 5ms budget — what would settle it: on-device timing of `gc.collect()` duration at realistic heap size/fragmentation, and whether the main loop enforces any per-iteration budget this could violate. If true, medium.
  - `[medium]` `[patch]` blind-hunter: new regression test (`test_station_asset_import_failure_closes_clients_and_stays_recoverable`) only forces `MemoryError` on the asset import, leaving the sibling `except Exception:` branch's new `http.close_clients()` call (coordinator.py:554-558) completely uncovered — action: add a sibling test raising a non-MemoryError exception from the same import point, asserting `close_clients()` fires, `error_code == "web_asset"`, and mode stays `MODE_STATION_ONLINE`.
  - `[low]` `[reject]` blind-hunter: the two new markdown artifacts restate the same narrative with no reverse link from the touch-ui spec back to the new wifi-config file — the wifi-config file already links to the spec's Handoff as source of truth; closing the loop the other way would mean editing this build's spec, which is out of scope for triage-applied fixes.
  - `[low]` `[reject]` blind-hunter: spec's `## Auto Run Result` section still reads `Status: blocked` even though the Handoff below resolves that gap — real but its only fix is editing this build's spec (superseded by this pass's own Auto Run Result rewrite below).
  - `[low]` `[reject]` blind-hunter: spec's `## Verification` command list (two test files) undersells the actual validation performed (371/371 full suite) — real but its only fix is editing this build's spec's Verification section.
  - `[low]` `[defer]` blind-hunter: `tools/deploy.py`'s `PRECOMPILE` list gained an entry with no test asserting the list's contents or deploy behavior — verified pre-existing: no test infrastructure exists anywhere in the repo for `PRECOMPILE`, so this diff does not introduce or worsen the gap.
  - `[low]` `[reject]` blind-hunter: spec's Tasks & Acceptance checklist isn't annotated to show AC1 (settings page reachable) is still unmet — real but its only fix is editing this build's spec.
  - `[low]` `[patch]` edge-case-hunter: the `except MemoryError:` asset-import branch gained a `self._heap_checkpoint("station_asset_fail")` diagnostic call, but the sibling `except Exception:` branch (coordinator.py:554-558) did not — action: add the same checkpoint call to the `except Exception:` branch so both failure paths capture identical heap diagnostics.
  - `[maybe-false]` `[defer]` edge-case-hunter: same finding as the gc.collect() row above (shared root cause) — grouped, same disposition.
  - `[medium]` `[patch]` verification-gap: pre-verified — grepped all test files, confirmed no test forces a non-MemoryError exception through the lazy station-asset import, so the `except Exception:` branch's new `http.close_clients()` call (coordinator.py:554-558) is unverified; a regression there would ship undetected. Same root cause and disposition as the blind-hunter row above (grouped).
  - `[high]` `[defer]` intent-alignment: diff implements a narrower reading of the intent (safe-failure cleanup) than the literal Problem/AC1 (settings page reachable); the underlying heap-fragmentation root cause remains open and confirmed via device evidence in this spec's own Handoff, yet frontmatter `deferred: []` does not track it — action: add a deferred entry for the open heap-fragmentation root cause per the Handoff's "Recommended next steps."

## Auto Run Result

Status: blocked (superseded -- see 2026-09-14 result below)
Blocking condition: intent gap -- the report does not say whether `http://192.168.1.32/` times out, refuses the connection, displays an HTTP status/error, or redirects to login; nor does it include the required post-boot serial checkpoints. These are observably different failure classes with different responsible layers.

### 2026-09-14 -- Auto Run Result

**Summary:** The intent gap above was resolved with real device evidence in an interactive live-device session (see Handoff below): the failure class is a silent indefinite browser hang caused by a missing `http.close_clients()` call in two station-asset-import failure branches, compounding an unresolved, confirmed heap-fragmentation `MemoryError` in `SessionTable()` construction. This automated pass added the required host regression coverage and evidence record for that already-diagnosed and already-applied fix, then closed two review-found coverage gaps.

**Files changed (this pass, on top of the pre-existing uncommitted device-verified fix):**
- `tests/test_config_auth.py` -- added `test_station_asset_import_failure_closes_clients_and_stays_recoverable` (MemoryError branch) and `test_station_asset_import_generic_exception_closes_clients` (generic-Exception branch, added during review patch) covering the `http.close_clients()` fix.
- `src/device/network/coordinator.py` -- added `self._heap_checkpoint("station_asset_fail")` to the `except Exception:` branch (review patch), matching the sibling `except MemoryError:` branch.
- `_bmad-output/implementation-artifacts/wifi-config/native-auth-precompile-station-http-fix.md` -- new file recording the pinned `PRECOMPILE` change and the open heap-fragmentation finding.
- (Pre-existing, unmodified this pass) `src/device/network/coordinator.py` -- `http.close_clients()` added to both asset-import failure branches; `tools/deploy.py` -- `src/provisioning/session.py` added to `PRECOMPILE`.

**Review findings breakdown (2026-09-14 review pass, 12 findings from 4 layers):**
- Patched (2): missing test coverage for the `except Exception:` branch's `close_clients()` call (medium); missing `_heap_checkpoint` call in that same branch (low). Both fixed by the re-engaged implementation subagent; verified below.
- Deferred (3, added to frontmatter `deferred`): the open heap-fragmentation root cause blocking `SessionTable()` construction (high); the new unconditional `gc.collect()` before every `http.tick()` call, unmeasured latency risk (medium, unverified); `tools/deploy.py`'s `PRECOMPILE` list has no test coverage, pre-existing (low).
- Rejected (5): a claimed duplicate-logging pattern in the `except Exception:` branch (false -- the two log calls carry different information and the dedup log may not even fire); a missing reverse cross-reference from the spec to the new wifi-config file, a stale `Status: blocked` line in this section, an undersold `## Verification` command list, and an unannotated Tasks & Acceptance checklist (all real but their only fix is editing this build's spec, which is out of scope for triage-applied fixes -- addressed directly in this Auto Run Result update instead).

**Follow-up review recommendation:** false. This pass patched one medium and one low finding -- not a high, and not two-or-more mediums -- so per the first-pass threshold no further review round is warranted. Patch counts by verdict: medium 1, low 1.

**Verification performed:**
- `uv run pytest tests/test_config_auth.py tests/test_station_recover.py` -- 47 passed.
- `uv run pytest` (full host suite) -- 372 passed.
- Manual device checks: not re-performed this pass (no hardware attached); the flashed-device evidence already captured in the Handoff below (TCP connect succeeds, HTTP response now closes cleanly instead of hanging) covers the code state as of this pass, since no device-affecting code changed since that capture -- only the `_heap_checkpoint` addition (no-op unless `config.WEB_HEAP_CHECKPOINTS = True`) and new tests were added.

**Residual risks:**
- Settings page still does not load on the real device -- the heap-fragmentation `MemoryError` on `SessionTable()` construction is unresolved (tracked in frontmatter `deferred`, high).
- The new unconditional `gc.collect()` before every `http.tick()` call has unmeasured cooperative-loop timing impact (tracked in frontmatter `deferred`, medium/unverified).

## Handoff (2026-09-14, interactive live-device session)

The intent gap above is now resolved with real device evidence. Failure class confirmed: TCP connect succeeds (listener is bound and healthy), but the HTTP response never arrives -- pre-fix this was a silent indefinite hang (curl times out client-side with zero bytes, no FIN/RST); post-fix (see below) it is a fast, clean connection close with zero bytes ("Empty reply from server").

### Root cause (confirmed via on-device `micropython.mem_info(1)` dump)

The station config surface lazy-imports several modules only on the *first* browser request to `/` or `/settings`, specifically so idle devices that never touch config don't pay the RAM cost (see the comment above the `if not self._station_assets_ready:` block in `coordinator.py`). By the time that first request actually arrives, the display/UI render loop and network worker have already been running for a while and have fragmented the heap into thousands of tiny 1-block/2-block allocations. Captured evidence:

```
GC: total: 179328, used: 131392, free: 47936
No. of 1-blocks: 1825, 2-blocks: 269, max blk sz: 242, max free sz: 361
```

`max free sz: 361` is in GC blocks (16 bytes each on RP2040) -- i.e. the single largest contiguous free run is only ~5.6KB, even though ~48KB is nominally free. Loading `src/provisioning/session.py` (needed to construct the config-auth `SessionTable`) needs a contiguous chunk it can no longer find, so it throws `MemoryError` on essentially every station request, deterministically, every boot.

Bisection method used (in case this needs repeating): add `self._heap_checkpoint("label")` calls (already the project's own host-safe pattern, gated by `config.WEB_HEAP_CHECKPOINTS`) at each candidate step, flip that config flag to `True` temporarily, redeploy, and passively capture serial (`scratchpad/passive_capture.py` in this session -- a single-process pyserial reader; do NOT interleave `mpremote run`/`reset` with a live serial capture, they fight over the port and also knock the device out of `main.py` back into the REPL, requiring a physical unplug/replug to recover). This narrowed the failure from "asset import block" -> "session_table() call inside `_dispatch_config`" -> confirmed via `micropython.mem_info(1)` printed right at the failure point.

Two things that looked plausible and were disproven with device evidence, to save the next session time:
- **Not a first-import-compiles-from-source issue.** `src/provisioning/session.py` was missing from `tools/deploy.py`'s `PRECOMPILE` list (now added -- real fix, keep it), but adding it alone did not resolve the failure. The module still fails to *load* (not compile) at the fragmented heap point.
- **Not fixable with `gc.collect()`.** MicroPython's GC is mark-sweep, not compacting/moving -- it reclaims garbage but cannot merge scattered free blocks into one larger one. A `gc.collect()` was added before `http.tick()` anyway (cheap, harmless, occasionally helps) but does not touch the fragmentation itself.

### What's fixed and confirmed working on the device right now

Current diff (both changes deployed and verified, 370/370 host tests pass):

1. `src/device/network/coordinator.py` -- `http.close_clients()` was missing from two of the four failure branches around the lazy station-asset import (`except MemoryError` and `except Exception` inside `if not self._station_assets_ready:`), while every *other* identical failure branch in the file already closes clients. This was a real, standalone bug: on failure, the already-accepted browser TCP connection was left open with no response and no close, so the browser just hung until its own client-side timeout. Fixed by adding `http.close_clients()` to both branches, matching every other failure branch. Also added a `gc.collect()` immediately before `http.tick()` in the same method (cheap, does not hurt, does not fully solve fragmentation -- see above). Also added named `self._heap_checkpoint(...)` calls around the asset-import block (no-op unless `config.WEB_HEAP_CHECKPOINTS = True`) for future diagnosis.
2. `tools/deploy.py` -- added `"src/provisioning/session.py"` to `PRECOMPILE`. Real, standalone fix (that module ships as source-compiled-on-device today, unlike its siblings in `src/provisioning/`), keep it regardless of what happens with the fragmentation fix below.

Net effect on the device today: Settings page still does not load (still `MemoryError` on `session_table()`, still logged as `web_asset`), but the browser now gets a fast clean failure instead of hanging forever. This alone is a real, shippable improvement even before the fragmentation issue is solved.

### What was tried and reverted (do not repeat without a different approach)

Eager-loaded the station web + session modules (`import` only, not `SessionTable()` construction, to preserve the existing "sessions stay `None` until a `/`/`/settings` request" contract -- see `tests/test_config_auth.py::test_login_and_unknown_routes_do_not_allocate_sessions`) at the earliest point `MODE_STATION_ONLINE` is reached: `NetworkCoordinator.__init__` (covers the common real case -- device boots already configured, goes straight to `STATION_ONLINE`) and the two `self._mode = MODE_STATION_ONLINE` transition sites in `_complete_store_station_success` and its counterpart near line 1081. Passed all 370 host tests. Flashed to the device: it made things *worse* -- the display/UI render loop immediately started throwing `MemoryError` on every single tick (`App loop: MemoryError, recovered`, repeating nonstop), which it was not doing before. This means claiming ~16-18KB for web/session modules that early in boot starves something else (most likely the display/UI compositor's own buffer allocation, which appears to run soon after coordinator construction) that also needs a large contiguous chunk. Reverted cleanly; confirmed back to the stable state described above (370/370 tests pass, redeployed, passive-capture-confirmed only a single `station_assets_ready` line, no more `App loop: MemoryError` spam).

### Recommended next steps

The fragmentation problem is real and architectural, not a one-line fix. Options worth investigating, roughly in order of how much they'd tell you before committing to a change:

1. Get a `micropython.mem_info(1)` dump (or just `gc.mem_free()` + the block-count line) right after display/UI bootstrap completes and right before the coordinator would first attempt the lazy import, on a normally-booting device, to see how fragmented the heap already is before *any* web-config work happens, and how much of that is display/UI's own doing vs. WiFi driver buffers vs. general churn.
2. If display/UI bootstrap is the main fragmentation source, investigate whether its large allocations (framebuffer, compositor buffers) can be moved earlier/pinned so they don't compete with a later-timed eager station-web import -- i.e., do the eager import used in this session's reverted attempt, but sequenced to run *after* display bootstrap's big allocations are already settled, not in `__init__` which may run before them.
3. Alternatively, look at whether `src/provisioning/session.py` (and the four already-fine station page/router modules) can be imported once, very early in `main.py`, before the display driver initializes at all -- i.e., move the "make session/web reachable" cost to the very start of boot rather than trying to time it around STATION_ONLINE transitions.
4. As a fallback if none of the above pans out cleanly: reduce the memory footprint of whatever is generating the 1825 separate 1-block allocations visible in the `mem_info` dump (that's unusually high fragmentation for a device that's otherwise idle when a browser first connects) -- may point to a churny allocation pattern somewhere in the render or network-worker loop worth finding independently of this bug.

Tooling notes for whoever picks this up:
- Device is at `/dev/cu.usbmodem101` on this machine; use `uv run tools/deploy.py --port /dev/cu.usbmodem101` to flash.
- `mpremote run <script>` and `mpremote ... reset` both knock the device out of `main.py` and leave it sitting at the REPL prompt -- a physical USB unplug/replug is the reliable way back to normal boot. `mpremote connect <port> soft-reset` also leaves it at the REPL (Ctrl-D reboots but doesn't resume `main.py`), it just does so without USB re-enumeration.
- For passive serial capture without disturbing the running device, a single-process pyserial reader (never `cat` + a separate `mpremote` on the same port at once -- they fight over the fd) is the reliable approach; a 30-40s window is comfortably enough to boot, reach STATION_ONLINE, and observe several browser request/failure cycles.

## Verification

**Commands:**
- `uv run pytest tests/test_config_auth.py tests/test_station_recover.py` -- expected: existing and new station-web behavior tests pass.

**Manual checks:**
- Flash the Pico, capture `App loop starting`, web construction/listen, and any `web_*` checkpoints, then record the browser result for `http://192.168.1.32/` and `/login`.
