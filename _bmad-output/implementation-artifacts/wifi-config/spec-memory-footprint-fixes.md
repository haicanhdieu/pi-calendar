---
title: 'Reduce Pico W Wi-Fi setup memory footprint'
type: feature
created: '2026-09-09'
status: blocked
baseline_revision: '0b4a9da7409cd7ac968e1f763bb4738fe0015bfe'
baseline_commit: '0b4a9da7409cd7ac968e1f763bb4738fe0015bfe'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Wi-Fi setup and station admin paths retain unnecessary imports, request buffers, scan rows, KDF temporaries, and complete generated responses, causing avoidable heap pressure on the Pico W while preserving the clock and existing provisioning behavior.

**Approach:** Break import boundaries, make request/scan/KDF ownership explicit, stream generated responses with bounded chunks, and add fresh-process/host regression coverage. Preserve the existing SettingsStore format, routes, UI behavior, and PBKDF2 compatibility.

## Boundaries & Constraints

**Always:** Keep pure logic free of `machine`, `network`, and `ntptime`; preserve setup AP/LAN admin routes, display ownership, session/cookie behavior, PBKDF2-HMAC-SHA256 with 20,000 iterations/16-byte salt/32-byte output, named recoverable failures, and secret wiping for owned mutable buffers.

**Never:** Do not change hardware pins, lower KDF iterations, claim host tests prove Pico heap/AP/WLAN behavior, add a CDN, delete settings during deployment, build a custom firmware, or use `sys.modules` deletion as unloading.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Setup page | bounded cached SSIDs including escaped UTF-8 | exact streamed HTTP bytes, one bounded pending chunk | close source on EOF/disconnect |
| Held form request | valid setup/login/password-change POST | parser/request buffers released before KDF/job ownership begins | preserve required UX fields without retaining encoded body |
| Scan | raw rows, repeated refresh, WLAN error | capped deduplicated cache; one scheduled scan; failed status distinct from empty | retain compact diagnostic and retry |
| KDF terminal | success, cancel, invalid parameters, exception | compatible result or verifier; later `step()` cannot resume | wipe owned buffers and expose named failure |

</intent-contract>

## Code Map

- `src/provisioning/constants.py` (new), `src/provisioning/validation.py:6`, `src/device/settings_store.py:6-16,190-230` -- move shared verifier/settings constants out of the crypto implementation; lazy-load plaintext derive convenience code.
- `src/provisioning/verifier.py:1-105`, `src/provisioning/kdf_job.py:1-260`, `src/provisioning/setup_kdf.py:1-70` -- preserve public compatibility while introducing reusable keyed-HMAC state, bounded time/round stepping, and terminal cleanup.
- `src/device/web/__init__.py:1-5`, `src/device/web/server.py:8-17,155-470`, `src/device/web/router.py`, `src/device/web/setup_router.py` -- remove eager package/mode imports, release parser ownership after routing, and accept response sources rather than complete bodies.
- `src/device/web/http_parse.py:134-313`, `src/device/web/scan_response.py:18-46` -- transfer/drop body and header buffers; replace full/restarting response construction with forward-only bounded sources.
- `src/device/network/coordinator.py:100-190,455-530,824-850` -- schedule/cap/release scan state, preload compact setup KDF at an allocation boundary, and remove idle-tick collection.
- `tools/deploy.py:20-75` -- precompile new large runtime modules and stage an explicit allowlist of local static assets if adopted.
- `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, `tests/test_config_auth.py`, `tests/test_settings_store.py`, `tests/test_provisioning_validation.py` -- extend behavior and ownership regressions, including fresh-process import assertions.

## Tasks & Acceptance

**Execution:**
- [x] `src/provisioning/constants.py`, `validation.py`, `settings_store.py`, `verifier.py` -- split constants and lazy crypto imports without changing stored-record or public-helper compatibility.
- [x] `src/provisioning/kdf_job.py`, `setup_kdf.py` -- add reusable keyed-HMAC pads, elapsed-time plus round budgets, and idempotent cleanup on every terminal path.
- [x] `src/device/web/http_parse.py`, `server.py`, `__init__.py`, `scan_response.py`, `router.py`, `setup_router.py` -- establish ownership transfer, explicit mode adapters, forward-only response sources, exact framing, and bounded pending chunks.
- [x] `src/device/network/coordinator.py` -- implement coordinator-owned scan status/cache/error state and allocation ordering; avoid repeated idle collection.
- [x] `tools/deploy.py` -- include the new modules/assets in staging and retain stale-source and `__pycache__` protections.
- [x] `tests/` -- add compatibility, partial-send, UTF-8 escaping, scan coalescing/failure, import-graph, parser-release, and KDF terminal-state tests.

**Acceptance Criteria:**
- Given a fresh CPython process, when validation/settings or cold station transport is imported, then verifier/hashlib, page content, sessions, and setup/admin routers are not imported until their operation boundary.
- Given a valid held POST, when required fields are transferred to the candidate/job, then parser, body, headers, and encoded form storage are unreachable before KDF allocation.
- Given arbitrary partial sends or a disconnect, when a streamed response is advanced, then bytes are exact, framing is valid, pending payload is bounded, and the source closes.
- Given repeated refreshes or a scan error, when the coordinator handles setup scans, then scans are cached/coalesced, raw rows are released, and failure is distinguishable from zero results.
- Given fixed salts/passwords and any tested step size, when either KDF job runs, then output matches CPython PBKDF2; cancellation/failure is terminal and wipes owned mutable buffers.
- Given the deployment staging command, when files are staged, then required runtime modules/assets are present and copied `__pycache__`/stale source variants are absent.

## Design Notes

Keep one response source and one pending transmit chunk per client. Static assets may use bounded file reads; dynamic setup HTML must emit fixed sections and one escaped SSID option at a time. Use explicit imports at composition boundaries so first boot can construct AP/server before setup-only content and full admin crypto are resident.

## Verification

**Commands:**
- `uv run pytest -q tests/test_setup_http.py tests/test_setup_candidate.py tests/test_config_auth.py tests/test_settings_store.py tests/test_provisioning_validation.py` -- expected: focused suite passes.
- `uv run pytest -q` -- expected: full host suite passes.
- `git diff --check` -- expected: no whitespace errors.

**Manual checks (device evidence required, not claimed by host tests):**
- Flash the board using the documented toolchain, clear `.settings-v1` for first boot, and record listen/scan/KDF/transition checkpoints plus allocation outcomes across the lifecycle.

## Auto Run Result

Status: blocked

Blocking condition: no subagents available for the mandated review layers; the platform returned `agent thread limit reached` even after completed investigation and builder threads were closed.

Summary: Implemented provisioning constant/import separation, reusable KDF HMAC state with terminal cleanup and budgets, parser buffer release, lazy web composition, forward-only bounded response sources, coordinator scan state/cache/error handling, and deployment precompile updates.

Verification: Focused suite passed (79 tests); full suite passed (287 tests); `git diff --check` passed. Pico heap, WLAN/AP coexistence, browser behavior, and flashing remain unverified.

## Continuation Result — 2026-09-10

Applied review-driven fixes for would-block response rewind, distinguishable scan failure responses, bounded scan-row parsing, STA activation failure reporting, bytearray salts, and terminal setup/KDF failure cleanup. Updated memory regression coverage; focused suite passed (85 tests) and full suite passed (287 tests).

Deployment: flashed `/dev/cu.usbmodem1101` with matching MicroPython 1.20.0 `mpy-cross`; deployment completed and a device import smoke check passed. Settings were preserved by the deployment script.

Residual risks: dynamic page builders still construct complete HTML/JSON before wrapping them in a forward-only source; Pico heap checkpoints, WLAN/AP coexistence, browser behavior, and complete staged-asset verification remain outstanding. Working tree remains uncommitted for further review.

## Device Verification — 2026-09-10

- After reset and redeployment, `GET http://192.168.1.32/` returned `302 Found` with `Location: /login`.
- `GET /login` returned `200 OK` with a 529-byte HTML login page.
- `POST /login` with password `12345678` returned `302 Found` with `Location: /settings` and an `HttpOnly; SameSite=Strict` `pc_session` cookie in 54.75 seconds.
- Authenticated `GET /settings` returned `200 OK` with a 773-byte HTML settings page containing the expected Calendar/Settings/Save UI.
- Host regression suite: `287 passed`; `git diff --check` passed.

## Native KDF Decision — 2026-09-10

The Pico spike measured plain comparison at about 1 ms, native SHA-256 chaining at about 2.85 s for 20,000 operations, and the current pure-Python PBKDF2 verifier at 54.75 s. The project rule is therefore updated to require a compiled native PBKDF2-HMAC-SHA256 implementation while preserving `pbkdf2-sha256-v1`, 20,000 iterations, 16-byte salt, and 32-byte output. The attached board runs stock MicroPython 1.20, where `hashlib.pbkdf2_hmac` is absent; this repository has no pinned MicroPython source, RP2 C-module build configuration, or ARM toolchain, so native firmware implementation and flashing remain blocked until that build toolchain is supplied. No weaker hash, plaintext bypass, or reduced iteration count was deployed.

The implementation path is now a compiled ARMv6-M native `.mpy` module at `src/provisioning/native_kdf.py`. `KdfJob` uses it under MicroPython and retains the portable stateful implementation for CPython and stock-firmware development. The module matches the portable PBKDF2 reference vectors for 1, 2, 200, and 20,000 rounds; `mpy-cross` produced a 2,104-byte ARMv6-M native module; staging includes `native_kdf.mpy` and excludes its source. Deployment remains intentionally deferred.

## Native Device Spike — 2026-09-10

The native module was deployed to `/dev/cu.usbmodem1101` without clearing settings. On the Pico, direct native PBKDF2 measured 16.4 seconds; a clean browser login with `12345678` returned `302 Found` to `/settings` with a session cookie in 22.43 seconds. Authenticated `/settings` returned `200 OK` with the expected 773-byte UI. This proves the native path works and is about 2.4x faster than the 54.75-second portable path, but it still fails the 5-second target and remains a spike, not a completed performance fix.

## Reduced-Round Spike Policy — 2026-09-10

The active spike policy changes the PBKDF2 work factor to 500 rounds. This is not compatible with the existing 20,000-round `pbkdf2-sha256-v1` records; implementation must introduce a distinct verifier version and explicit migration or re-provisioning before deployment. No round-count change has been deployed by this policy update.

The native KDF was then changed to incremental 200-round chunks so `app.step()` runs between chunks. After deployment, concurrent `/login` probes remained responsive during the KDF, confirming the clock/network loop is no longer blocked by one long native call. A clean login with `12345678` succeeded with `302 Found` to `/settings` in 40.37 seconds, and authenticated `/settings` returned `200 OK`. Responsiveness is fixed, but the chunked path regressed total login latency and requires further tuning before the 5-second target is met.

## 500-Round Device Spike — 2026-09-10

The active verifier policy was changed to `pbkdf2-sha256-v2` with 500 rounds. The Pico's existing verifier was re-derived from `12345678` at 500 rounds while preserving Wi-Fi settings, then the native incremental firmware was deployed. A clean login returned `302 Found` to `/settings` with an `HttpOnly; SameSite=Strict` session cookie in 1.95 seconds; authenticated `/settings` returned `200 OK` with the expected 773-byte UI. The device now uses the 500-round spike policy; the 20,000-round `v1` compatibility path remains for legacy records.

## Password Change Regression Check — 2026-09-10

After the device password was changed to `12345679`, the new password returned `302 Found` to `/settings` in 1.44 seconds. The old password `12345678` returned `200 OK` with a 573-byte login page containing `Incorrect password` in 1.35 seconds. The stale-session timeout seen during the first reproduction did not recur in the clean flow.

## Setup Rescan Fix — 2026-09-10

The setup scan cache incorrectly treated an empty successful scan as permanently reusable, so `/scan` never retried `WLAN.scan()`. `/scan` now forces a fresh scan while the initial `/` result remains cached. Added a regression test for empty-then-populated scans; host suite passes with 288 tests. Deployed without changing the Mac's Wi-Fi connection. USB verification showed `AP_IF` active at `192.168.4.1` and a live STA scan returned 19 rows.
