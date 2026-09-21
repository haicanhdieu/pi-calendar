---
title: 'Fix empty response from authenticated alert add page'
type: 'bugfix'
created: '2026-09-21'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/alert-clock/prds/prd.md
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/alert-clock/architecture/ARCHITECTURE-SPINE.md
warnings: []
deferred:
  - summary: >-
      Setup-mode request-failure recovery lacks dedicated coordinator integration coverage.
    evidence: |-
      Shared server failure handling now consumes and logs setup request failures, but no test exercises a setup request that reaches the new fallback path. Run a flashed/setup-AP or focused coordinator test before relying on this path.
    location: >-
      src/device/network/coordinator.py:873
    severity: medium
  - summary: >-
      Real Pico/browser/serial confirmation remains uncollected.
    evidence: |-
      Host tests use fake sockets and simulated exceptions; they cannot prove Pico heap behavior, WLAN reachability, browser response, or serial diagnostics. Flash the firmware and repeat GET /settings/add with serial capture.
    location: >-
      Manual device verification
    severity: medium
baseline_revision: '6e5141e5660569eac00964662a4ed1cc0b9331db'
---

<intent-contract>

## Intent

**Problem:** An authenticated browser request to `http://192.168.1.32/settings/add` connects but receives no HTTP bytes and reports `ERR_EMPTY_RESPONSE`. Host routing already recognizes this path, so the device-side request path is failing after accept and before response transmission.

**Approach:** Make `/settings/add` produce a bounded HTTP response on Pico, including when request-time page/editor allocation or rendering fails. Preserve authentication, alert-editor behavior, and cooperative server recovery; expose a secret-free serial phase for any device failure.

## Boundaries & Constraints

**Always:** Keep web handling cooperative and bounded; preserve `/settings/add` authentication and editor output; keep pure web code free of hardware imports; ensure client sockets close cleanly after terminal responses; retain a useful host-test reproduction for the failure boundary.

**Never:** Do not weaken authentication, change alert persistence/schema, alter hardware pins, add blocking retries, claim on-device success from host tests, or hide the underlying exception by removing diagnostics.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Authenticated add page | Station-online mode, valid session, `GET /settings/add` | Complete HTTP response with inline add editor | No error |
| Unauthenticated add page | Station-online mode, no/expired cookie | Existing redirect to `/login` | No editor or alert data leaked |
| Request-time allocation failure | Authenticated add request with simulated `MemoryError`/render failure | Bounded non-empty 5xx response, client closed, server remains usable | Secret-free serial phase/code |
| Follow-up request | Failure on one add request, then valid settings request | Later request receives normal response | Failed client state fully released |

</intent-contract>

## Code Map

- `src/device/web/router.py:89-159` -- authenticates protected GETs and renders `/settings/add`; request-time lazy editor import occurs through `pages.response_settings_page`.
- `src/device/web/pages.py:136-151` and `src/device/web/page_settings_content.py:59-90` -- build settings response and lazy inline alert editor; likely allocation boundary for add-only failure.
- `src/device/web/server.py:206-292, 350-430` -- accepts, dispatches, converts response to streaming source, and closes clients; exceptions are handled by coordinator rather than returned to browser.
- `src/device/network/coordinator.py:501-585` -- catches `MemoryError`/other web exceptions, currently closes all clients and logs `web_asset`/phase; this can yield zero-byte browser response.
- `tests/test_config_auth.py:119-190, 500-530` -- existing auth and `/settings/add` route assertions; extend with complete-response coverage.
- `tests/test_memory_footprint_fixes.py:80-160` -- bounded streaming server harness; reuse for terminal response and client cleanup checks.
- `_bmad-output/implementation-artifacts/alert-clock/stories/1-2-add-an-alert-with-a-time-and-recurrence.md` -- completed feature contract; preserve its editor/auth/persistence behavior.

## Tasks & Acceptance

**Execution:**
- `src/device/web/pages.py`, `src/device/web/page_settings_content.py`, and/or `src/device/web/server.py` -- isolate the failing add-page allocation/render boundary and return a bounded non-empty response while preserving normal editor output -- prevent browser `ERR_EMPTY_RESPONSE`.
- `src/device/network/coordinator.py` -- retain recoverable per-request failure handling and emit a phase/code without dropping response opportunity -- keep cooperative loop alive.
- `tests/test_config_auth.py`, `tests/test_memory_footprint_fixes.py`, and focused web tests -- cover authenticated success, auth redirect, simulated request failure, client closure, and subsequent request recovery -- prove the matrix.

**Acceptance Criteria:**
- Given a valid authenticated session, when `GET /settings/add` is served on station-online web, then browser receives a complete non-empty HTTP response and response contains add-editor controls.
- Given no valid session, when `GET /settings/add` is served, then response remains the existing login redirect and contains no editor or alert mutation.
- Given request-time editor/render allocation failure, when the request is dispatched, then browser receives bounded non-empty HTTP error bytes, client closes, and cooperative web service continues.
- Given one failed add-page request, when a later valid settings request arrives, then it receives a normal response and no stale parser/client state remains.
- Given existing alert add/edit flows, when focused and full host tests run, then prior behavior and persistence tests remain passing.

## Design Notes

`ERR_EMPTY_RESPONSE` proves TCP accept but not application response. Current coordinator catches broad web exceptions around `http.tick`, closes clients, and logs only a compact phase/type; this explains zero bytes while preserving loop recovery. Fix must keep the failure bounded and observable, not turn failures into a fake successful page.

## Verification

**Commands:**
- `uv run pytest tests/test_config_auth.py tests/test_memory_footprint_fixes.py` -- expected: focused web/auth/streaming tests pass.
- `uv run pytest` -- expected: full host suite passes.
- `git diff --check` -- expected: no whitespace errors.
- `graphify update .` -- expected: graph reflects source changes.

**Manual checks (device):**
- Flash changed firmware, authenticate, request `/settings/add`, and capture browser response plus serial `web_*` checkpoints. Host tests cannot prove Pico heap, WLAN, or browser behavior.

## Review Triage Log

### 2026-09-21 — Review pass
- verdicts: 14 findings — high 1, medium 8, low 2, false 3, maybe-false 0
- findings:
  - `[high]` `[patch]` Fallback response could reallocate after heap failure — replaced `ResponseSource` construction with module-level bounded bytes.
  - `[medium]` `[patch]` Dynamic exception-name construction could allocate during failure handling — replaced with fixed `request_memory`/`request_error` codes.
  - `[medium]` `[patch]` Setup request failures were not consumed or logged — added setup-mode consumption and bounded logging.
  - `[medium]` `[patch]` Request failure omitted retry timestamp — passed `now` and kept request recovery immediate.
  - `[false]` `[reject]` Request-specific failure category was said to be lost — fixed `request_*` serial log remains; existing `web_asset` event category is intentional and preserved.
  - `[medium]` `[patch]` Generic request exceptions lacked coverage — added `RuntimeError` 503/recovery test.
  - `[false]` `[reject]` 503 completeness was said to lack validation — shared bounded writer tests already verify exact streamed bytes; fallback uses same writer.
  - `[false]` `[reject]` Fallback construction failure remained possible — fallback no longer calls `ResponseSource`; module-level bytes avoid that allocation boundary.
  - `[low]` `[reject]` Setup integration test was missing — behavior is covered by shared server path; dedicated setup evidence deferred as a non-user-visible test gap.
  - `[low]` `[patch]` Expired `/settings/add` session lacked coordinator coverage — added expired-cookie redirect test.
  - `[medium]` `[patch]` Lazy edit-page session factory lacked coordinator coverage — added authenticated `/settings/edit/<id>` test.
  - `[medium]` `[defer]` Device serial/browser evidence missing — host environment cannot flash or prove Pico behavior; recorded required manual evidence above.
  - `[medium]` `[patch]` Verification layer repeated missing edit-page coverage — same coordinator edit test added.
  - `[medium]` `[patch]` Verification layer repeated missing generic request-exception coverage — same `RuntimeError` 503 test added.

## Auto Run Result

Status: done

Summary: Fixed authenticated `/settings/add` empty responses by converting request-dispatch failures into bounded 503 bytes, preserving client/listener recovery, and logging fixed secret-free request failure phases. Added lazy session coverage for add/edit paths and auth/failure regression tests.

Files changed:
- `src/device/web/server.py` -- bounded request-failure response, fixed failure codes, parser cleanup, lazy sessions for add/edit.
- `src/device/network/coordinator.py` -- setup/station failure consumption, diagnostics, retry scheduling, and response draining.
- `tests/test_config_auth.py` -- add success/auth expiry, edit session factory, MemoryError and RuntimeError recovery tests.
- `spec-settings-add-empty-response.md` -- implementation, review, and verification record.
- `graphify-out/` -- refreshed generated graph after source changes.

Review findings breakdown: 9 patch rows applied; 3 false rows rejected with evidence; 1 low row rejected as non-user-visible coverage gap; 2 medium items deferred (setup-specific integration coverage and physical-device evidence).

Follow-up review recommendation: true — high-severity fallback allocation risk was patched; physical Pico/browser behavior remains unverified.

Verification:
- `uv run pytest tests/test_config_auth.py tests/test_memory_footprint_fixes.py` -- 58 passed.
- `uv run pytest` -- 641 passed.
- `git diff --check` -- passed.
- `graphify update .` -- passed.

Residual risks: Firmware was not flashed. Device heap, WLAN/browser behavior, and serial checkpoints remain unverified. Setup-specific request-failure integration coverage remains deferred.
