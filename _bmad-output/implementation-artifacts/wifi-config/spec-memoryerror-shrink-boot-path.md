---
title: 'Shrink Wi-Fi boot path after Pico MemoryError'
type: 'bugfix'
created: '2026-09-07'
status: 'done'
baseline_revision: '0650c172898359a1f7e411d49392142fbe68e3db'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - 'docs/hardware_configuration.md'
warnings: []
deferred:
  - summary: >-
      The flashed Pico has not yet demonstrated that the 1280-byte allocation failure is gone and the setup AP is physically available.
    evidence: |-
      Host tests prove deferred composition and the real lazy HTTP server under fakes. A flashed reset on 2026-09-07 reached `App loop starting (Clock view)` after the TFT checkpoint with no MemoryError; physical WLAN/AP visibility still needs a scan-capable client.
    location: >-
      Pico W runtime at /dev/cu.usbmodem1101
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** After the TFT boot checkpoint, the Pico raises `MemoryError` while allocating 1280 bytes before `App loop starting`; the coordinator never ticks, so an unconfigured device cannot expose `PiCalendar-Setup`.

**Approach:** Reduce peak boot heap by deferring Wi-Fi web/config-auth code and its allocations until the coordinator reaches the mode that needs it, while retaining setup-AP activation and all existing HTTP behavior.

## Boundaries & Constraints

**Always:** Preserve TFT pins/lifecycle; keep `NetworkCoordinator` the sole WLAN/socket owner and `App` the sole TFT writer; an unconfigured boot must still activate the open `PiCalendar-Setup` AP and emit its gateway status; keep pure modules host-importable; retain bounded, cooperative HTTP behavior.

**Never:** Do not change credentials, settings-record semantics, HTTP limits/routes, UI content, network policy, or claim a flashed-device result from host tests. Do not merely report free filesystem space or rely only on `.mpy`/freezing as the fix.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Unconfigured boot | Missing/invalid settings after TFT initialization | Coordinator construction completes without eagerly constructing/importing the web server; its first tick activates `PiCalendar-Setup` and emits `192.168.4.1` status | AP activation retains its named retry/error event behavior |
| Setup browser use | Active setup AP receives a request | The deferred HTTP surface is created before it is used and preserves setup scan/connect behavior | Creation/listen failure emits existing `listen_fail`, without crashing loop |
| Configured online device | Valid settings reaches station online | Config HTTP/auth/session/KDF facilities become available only when needed and existing login/settings behavior remains available | Existing KDF/busy/held-client handling remains safe |

</intent-contract>

## Code Map

- `main.py:1-68` -- currently imports and instantiates `SetupHttpServer` before `make_settings_coordinator`; remove this eager web dependency and add narrowly gated boot-memory diagnostics if useful.
- `src/device/network/models.py:60-69` -- lazy coordinator composition entry; preserves host-pure mode helpers.
- `src/device/network/coordinator.py:11-46,68-105,365-560,588-770,943-950` -- eager pages/KDF/session/scan/settings imports and instances are the boot heap peak; defer them at their mode-specific boundaries without moving WLAN ownership.
- `src/device/web/{__init__,server,router,pages,http_parse}.py` -- currently pulls a ~53 KB server/router/page graph, including fixed page assets; preserve its public behavior once lazily reached.
- `tests/test_setup_ap_coordinator.py` -- existing unconfigured AP ownership and retry coverage; extend it for lazy web construction/import behavior with fakes.
- `tests/test_setup_http.py`, `tests/test_config_auth.py`, `tests/test_session.py` -- regression coverage for setup and authenticated-config routes.
- `docs/hardware_configuration.md` -- read-only pin/lifecycle source of truth.

## Tasks & Acceptance

**Execution:**

- `main.py` -- stop eagerly importing/constructing the setup HTTP server; leave display initialization, coordinator composition, and loop order intact -- lowers peak after TFT checkpoint.
- `src/device/network/coordinator.py` -- introduce focused lazy accessors for mode-specific web/page, session, KDF, scan, and optional settings exception dependencies; instantiate the setup HTTP server only before serving it and config-auth state only in station-online work -- releases the setup AP path from config UI/auth footprint while preserving coordinator ownership.
- `tests/test_setup_ap_coordinator.py` and relevant HTTP/auth tests -- add fakes/assertions proving deferred construction occurs at the correct coordinator boundary and execute existing setup/config regressions -- prevents a boot-memory fix from breaking routes or AP activation.
- `main.py` or `src/config.py` -- if diagnostics are retained, make compact `gc` checkpoints explicitly opt-in and non-fatal -- makes flashed-device heap-stage evidence observable without permanent noisy output.

**Acceptance Criteria:**

- Given no valid settings record, when the Pico passes TFT initialization, then coordinator construction does not require the web-server/page/config-auth stack and the main loop can reach its startup checkpoint.
- Given that coordinator on its first tick, when it is in `SETUP_AP`, then it activates open `PiCalendar-Setup` and emits the existing setup status containing `192.168.4.1`.
- Given setup or station-online HTTP is exercised, when its mode first needs the deferred facility, then the facility is created once and existing setup, login, settings, session, and KDF tests still pass.
- Given a flashed unconfigured Pico, when the updated firmware is copied and reset, then the operator can observe an `App loop starting` checkpoint and `PiCalendar-Setup`; this is recorded as device-only verification, not inferred from pytest.

## Spec Change Log

## Review Triage Log

### 2026-09-07 — Review pass
- verdicts: 11 findings — high 0, medium 5, low 0, false 4, maybe-false 2
- findings:
  - `[medium]` `[patch]` `src/device/network/coordinator.py:306` allocated `SessionTable` at station success before config work — removed that allocation; tests now prove it remains absent until station-online HTTP dispatch.
  - `[medium]` `[patch]` configured boot allocated the HTTP server and session table before browser configuration use — session allocation now follows successful station-online listen setup and its tested HTTP dispatch boundary.
  - `[false]` `[reject]` `_get_http` makes a permanent failure opaque and retries allocations indefinitely — existing `listen_fail` is the specified recoverable failure behavior; retrying later is intentional and no reachable programming failure was demonstrated.
  - `[false]` `[reject]` `listen_fail` needs a retained construction cause or a new event — the existing named event is preserved exactly as required and the intent does not establish a diagnostic payload contract.
  - `[false]` `[reject]` no test proves the formerly eager modules remain unloaded — module-level imports were removed from the coordinator and the default production lazy-server path is now exercised; exact MicroPython heap residency cannot be established by CPython module assertions.
  - `[medium]` `[patch]` no default lazy-server browser path was tested — added fake-socket `GET /` coverage with neither injected server nor factory.
  - `[medium]` `[patch]` the default lazy factory could be absent while AP activation still passed — the new production-path request test fails if that factory/import path is removed.
  - `[medium]` `[patch]` session allocation after a station transition could regress without coverage — added a focused station-online boundary test.
  - `[false]` `[reject]` the work should have stopped at diagnosis because the wording is a decision prompt — invoking `bmad-build-auto` with the stated desired shrink path authorizes this implementation iteration.
  - `[maybe-false]` `[defer]` the actual Pico MemoryError may remain after the import deferral — only a flashed reset with serial heap/checkpoint evidence can determine this; recorded in `deferred`.
  - `[maybe-false]` `[defer]` `PiCalendar-Setup` may still not be observable on physical WLAN hardware — host fakes cannot establish radio/AP behavior; the same flashed unconfigured-device run settles it.

## Design Notes

The failure window is after `initialize_display()` and before `App loop starting`. `make_settings_coordinator()` lazily imports the 31.7 KB coordinator, which itself eagerly imports pages, server dependencies, sessions, and KDF code; `pages.py` contains 23.6 KB of fixed CSS/JS. The first AP activation cannot happen until `coordinator.tick()`, so reducing source file size alone is insufficient: construction must become light enough to reach that tick.

## Verification

**Commands:**

- `uv run pytest tests/test_setup_ap_coordinator.py tests/test_setup_http.py tests/test_config_auth.py tests/test_session.py -q` -- expected: existing setup/config behavior and new lazy-boundary assertions pass.
- `uv run pytest -q` -- expected: full host suite passes with no forbidden device imports in pure logic.

**Manual checks:**

- Flash to `/dev/cu.usbmodem1101` using the established deployment procedure, reset with no valid settings, and record serial checkpoints plus visible `PiCalendar-Setup` / `192.168.4.1`. Do not mark this observed until an operator performs it.

## Auto Run Result

Status: done

Summary: Reduced the post-TFT boot heap peak by removing eager web-server composition from `main.py` and deferring web pages, auth sessions, KDF, scan, and config-only dependencies to their coordinator use boundaries. Setup AP activation remains the first coordinator tick; its HTTP surface is then constructed on demand.

Files changed:
- `main.py` — removes eager `SetupHttpServer` import and instance.
- `src/device/network/coordinator.py` — adds lazy HTTP/session/page/KDF/scan/config dependency boundaries while preserving injected test servers and named setup errors.
- `tests/test_setup_ap_coordinator.py` — covers AP-first activation, default lazy server `GET /`, server creation failure, and session timing.
- `tests/test_config_auth.py`, `tests/test_network_coordinator.py`, `tests/test_setup_candidate.py` — update composition assumptions and config-session setup for lazy construction.

Review findings: 5 medium patch findings applied; 4 findings rejected with recorded evidence; 2 device-runtime findings deferred. Follow-up review is recommended because this pass applied five medium fixes and the remaining risk is the unverified flashed-device heap/AP behavior.

Verification: `uv run pytest tests/test_setup_ap_coordinator.py tests/test_setup_http.py tests/test_config_auth.py tests/test_session.py -q` passed (54 tests); `uv run pytest -q` passed (268 tests); `git diff --check` passed.

Residual risk: The changed firmware was copied to `/dev/cu.usbmodem1101` and two soft-reset captures reached `App loop starting (Clock view)` after the TFT checkpoint with no MemoryError. This host's Wi-Fi scan tool returned no networks, so physical confirmation of `PiCalendar-Setup` and `192.168.4.1` still needs a scan-capable phone or computer.
