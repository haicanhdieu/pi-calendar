---
title: 'Harden Pico web heap paths'
type: 'bugfix'
created: '2026-09-07'
status: 'in-review'
baseline_commit: '263f8294088421edf44540edf56d3b2310dd3f11'
route: 'dispatch'
review_loop_iteration: 0
context:
  - 'docs/hardware_configuration.md'
  - '_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The boot-path fix lets the Pico reach the app loop and activate `PiCalendar-Setup`, but the phone cannot reach its gateway because the deferred HTTP stack can still exhaust heap or fail silently after AP activation.

**Approach:** Make the setup HTTP path fit within the running Pico heap, separate setup-only resources from later admin-config resources, and make every allocation/listen failure observable and recoverable without stopping the clock or AP.

## Boundaries & Constraints

**Always:** Keep `NetworkCoordinator` the sole WLAN/socket owner and `App` the sole TFT writer. Preserve open `PiCalendar-Setup`, gateway `192.168.4.1`, bounded cooperative ticks, HTTP route/limit behavior, settings/auth semantics, and pure CPython-importable policy modules. Report operational failures without secrets.

**Never:** Do not change hardware pins, save Wi-Fi/Admin plaintext, weaken HTTP/auth policy, add dependencies/frameworks, claim host tests prove WLAN behavior, or overwrite the device's MicroPython firmware as part of this change.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| New-device boot | No valid settings, TFT initialized | Main loop reaches setup mode; AP activates before web allocation; setup `GET /` is served from the bounded setup-only footprint | Clock/TFT loop continues if web setup cannot start |
| Setup web allocation failure | Import, factory, page response, or listen allocation fails | AP remains active and coordinator emits a named, non-secret diagnostic identifying the failed phase | Retry is bounded/cooperative and does not hide `MemoryError` as a generic listen failure |
| Setup browser request | Phone connected to AP requests `/`, `/scan`, or `/connect` | Existing setup page, scan, validation, and candidate semantics remain available | Bad/oversized/unsupported request behavior stays fixed and bounded |
| Station-online configuration | Valid settings reaches home LAN | Admin-only page/auth/KDF resources are loaded only on first config use, not during setup or station transition | A late config resource failure is named and leaves clock/network state recoverable |

</frozen-after-approval>

## Code Map

- `main.py:24-94` -- composition root already reaches the loop after the prior import deferral; preserve display lifecycle and tick ordering.
- `src/device/network/coordinator.py:56-125,386-436,624-669` -- owns lazy HTTP/session/page/KDF creation; `_get_http()` currently catches all exceptions silently, so allocation/import failures leave an active AP without a listener.
- `src/device/web/{__init__,server,router,pages}.py` -- one import pulls server, router, setup HTML/CSS/JS, login, and settings assets together. `pages.py` is 23.6 KB and the device measurement shows the complete import costs roughly 76 KB.
- `src/device/web/http_parse.py` -- bounded pure parser to retain for setup-only transport.
- `src/provisioning/{validation,scan,session,kdf_job}.py` -- validation/scan are setup dependencies; sessions/KDF belong only to station-online config work.
- `src/app.py:171-232` and `src/device/network/models.py` -- event reduction contract; extend only with typed, secret-free operational errors if the UI/log needs a distinguishable web failure.
- `tests/test_setup_ap_coordinator.py`, `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, `tests/test_config_auth.py` -- existing AP, production lazy-server, route, and config regression coverage.
- `docs/hardware_configuration.md` -- target serial port source of truth; actual attached board reports MicroPython 1.20.0, while planning evidence names 1.29.0.

## Tasks & Acceptance

**Execution:**

- [x] `src/device/web/` -- split setup-serving code and fixed setup assets from station-online login/settings assets; ensure importing the setup server never imports config page/auth-only modules -- eliminate the identified 76 KB all-in-one import peak.
- [x] `src/device/network/coordinator.py` -- make web resource factories mode-specific, retain a compact failure state/code, and emit one typed, non-secret event/log per failed phase with cooperative retry -- prevent an unreachable AP gateway from failing silently.
- [x] `src/device/web/server.py` plus router/page imports -- expose phase-specific construction/listen failures without changing client route responses or ownership -- distinguish memory/import failure from bind/listen failure.
- [x] `src/config.py` and `main.py` if needed -- add opt-in, compact heap checkpoints around web startup without changing normal user-visible operation -- provide flashable proof of peak-memory stages.
- [x] `tests/test_setup_ap_coordinator.py`, `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, `tests/test_config_auth.py` -- prove import/asset separation, setup-only lazy serving, named resource-failure behavior, retries, and no eager config-auth allocation -- protect every matrix row.
- [ ] `_bmad-output/implementation-artifacts/wifi-config/spec-harden-pico-web-heap-paths.md` -- record serial/AP result from the flashed Pico run -- distinguish device evidence from host tests.

**Acceptance Criteria:**

- Given an unconfigured Pico after TFT initialization, when it enters `SETUP_AP`, then it starts the loop, activates the AP, and can serve `GET /` without importing login/settings/KDF/session resources.
- Given setup web resource allocation or listening fails, when the coordinator ticks, then it preserves the active AP and emits a named non-secret error that identifies construction, asset/page, or listen failure.
- Given a configured device with no browser request, when it reaches station online, then it has not created config HTTP/session/KDF resources; on first config use, existing auth behavior remains intact.
- Given the flashed device at `/dev/cu.usbmodem1101`, when reset with no valid settings, then serial shows the app loop and a phone can load `http://192.168.4.1/`; record the observed result rather than inferring it.

## Implementation Notes

## Spec Change Log

## Review Triage Log

| Verdict | Route | Evidence |
| --- | --- | --- |
| medium | patch | Setup failure left the user on a screen that could only resubmit an empty Wi-Fi password; retry now returns to the usable Wi-Fi step with allowed prefill. |
| false | reject | Station-online must own a listening socket before a browser can make its first config request; only config pages, sessions, and KDF are deferred. |
| medium | patch | Session state was created for public login/unknown routes; it now remains deferred until a route that needs it. |
| medium | patch | KDF import/allocation could raise outside the cooperative web recovery boundary; the password is wiped, held client closed, and named error emitted. |
| medium | patch | Candidate-time web failure closed the held `/connect` client before its terminal response; the held client is now retained. |
| medium | patch | A successful retry did not re-arm same-phase diagnostics; recovery now clears its recorded phase. |
| maybe-false | defer | Host tests cannot prove the flashed Pico's heap or phone gateway response; deployment plus a phone request settles this in the manual evidence row. |

| Verdict | Evidence |
| --- | --- |
| medium / patch | Candidate terminal responses still call `_pages()`, which imports admin assets while setup is active; use setup-only responses. |
| medium / patch | The split setup page removed its scan-driven two-screen, failure, and retry behavior; preserve those assets in the setup-only module. |
| medium / patch | Candidate-join serving can raise from `http.tick()` without recovery; report `web_asset`, close the request, and retry cooperatively. |
| medium / patch | A failed page/config dispatch can leave its client open after the coordinator catches the exception; close active clients before retrying. |
| medium / patch | A listener socket allocated before bind/listen failure is not closed; close it on both failure paths. |
| medium / patch | Setup content-type admission was broadened from urlencoded to arbitrary `form`; restore the exact urlencoded requirement. |
| medium / patch | Scan JSON does not escape control characters, so valid SSIDs can yield invalid JSON; escape all JSON control characters. |
| false | `web_construct` and `web_listen` remain distinct typed event codes, while memory subtype is recorded in the secret-free log; allocation is not hidden as a generic listen failure. |
| medium / patch | Setup listener and request asset failures lack focused retry/AP-preservation tests; add failure-injection coverage. |
| medium / patch | Station-online listener and asset failure events lack consumer-path coverage; add focused injected-server tests. |
| low / patch | Heap checkpoint messages are untested; add a flag-enabled logger assertion around setup startup. |

## Design Notes

Use a low-footprint setup transport/page module as the only dependency of setup mode. Keep shared parser and setup form validation in the pure core; defer admin routes, templates, sessions, verifier/KDF, and their imports until a station-online config request. Treat runtime resource acquisition as an explicit state outcome, not an exception swallowed by a broad `except`.

Setup assets/routes now live in `setup_pages.py` and `setup_router.py`; server-level config imports occur only while dispatching a station-online request. Named `web_construct`, `web_listen`, and `web_asset` events retry after `HTTP_RETRY_MS`. Set `WEB_HEAP_CHECKPOINTS = True` for `web_heap setup_before` and `web_heap setup_listening` serial evidence.

## Verification

**Commands:**

- `uv run pytest tests/test_setup_ap_coordinator.py tests/test_setup_http.py tests/test_setup_candidate.py tests/test_config_auth.py -q` -- expected: setup/config regressions and all heap-boundary tests pass.
- `uv run pytest -q` -- expected: full suite passes and pure-module import restrictions remain true.

**Manual checks:**

- Deploy `main.py` and `src/` to `/dev/cu.usbmodem1101`, reset with no valid settings, and capture serial heap/status checkpoints. From a phone on `PiCalendar-Setup`, load `http://192.168.4.1/` and record the result.
