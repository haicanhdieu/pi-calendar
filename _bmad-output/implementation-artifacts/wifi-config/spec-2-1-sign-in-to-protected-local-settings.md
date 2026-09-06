---
title: 'Sign in to protected local settings'
type: 'feature'
created: '2026-09-06'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: 'c562d733b3c2118c21ab7c64af5a562d3c875940'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/wifi-config/epic-2-context.md'
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** On the home LAN the Device has no Config login or session gate—anyone who reaches its address can (once routes exist) touch settings, and Setup-only HTTP never serves STATION_ONLINE.

**Approach:** Add STATION_ONLINE-only Config routes: password-only login with cooperative salted-verifier check, bounded in-memory sessions + HttpOnly Strict cookie, redirect unauthenticated protected GETs to login, and serve an authenticated mobile flat settings shell (password-change/theme behavior stays story 2.2).

## Boundaries & Constraints

**Always:**
- Config login/settings routes only when `STATION_ONLINE`; Setup routes only when `SETUP_AP` (already gated).
- Verify via stored `admin_verifier_version` / salt / verifier with constant-time compare; never return or log plaintext, verifiers, salts, cookies, bodies, or raw headers.
- Cooperative KDF: at most one `KdfJob`; ≤200 PBKDF2 rounds per coordinator tick; concurrent KDF → fixed `503 Busy`; overwrite/discard password bytearrays on terminal outcomes.
- Sessions: opaque 16-byte `os.urandom` → unpadded base64url (22 chars `[A-Za-z0-9_-]{22}`); ≤4 in-memory entries; idle renew only on successful authenticated protected requests (`ticks_add(now, 900000)`); expire with wrap-safe `ticks_diff`; invalid/expired cookies cleared `Max-Age=0` + redirect to login; full table after expiry cleanup → `503 Busy`, no cookie.
- Cookie: no persistence attribute; `HttpOnly`; `SameSite=Strict`; `Path=/`.
- HTTP allowlist GET + form-urlencoded POST; fixed local templates; `html_escape`; checked-in resource limits; NetworkCoordinator sole WLAN/socket owner; App sole TFT writer.
- Host-testable policy/auth/HTTP without `machine`/`network`/`ntptime`.

**Never:**
- Implement password change, multi-theme logic, logout, recovery, factory reset, TLS, WAN exposure, username field, or CSRF beyond SameSite.
- Change settings record schema, TFT pins/SPI, display lifecycle, or rewrite epic-1 STA recovery / Setup candidate path.
- Block the render loop with full 20k-iteration PBKDF2 in one tick.
- Serve Config routes in SETUP_AP or Setup routes in STATION_ONLINE.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Unauth protected GET | STATION_ONLINE; no/invalid session; GET `/` or `/settings` | 302/redirect to login; Setup paths 404 | Clear bad cookie Max-Age=0 |
| Login GET | STATION_ONLINE; GET `/login` | Password-only form; no username | — |
| Bad password | POST login; wrong password | Page shows only `Incorrect password`; no session cookie | No diagnostics/secrets logged |
| Good login | POST login; valid password; table has room | Set session cookie; redirect to settings | KDF via job; busy if job active |
| Session full | Valid password; 4 live sessions after expiry sweep | `503 Busy`; no cookie | Fixed body |
| Auth settings | Valid session; GET settings | Flat mobile settings list; approved tokens; no external fetch | Renew idle deadline |
| Mode gate | SETUP_AP requests Config path / STATION requests Setup path | 404 | — |
| Expired cookie | Cookie present; deadline passed | Clear cookie; redirect login | — |

</intent-contract>

## Code Map

- `src/config.py:102–121` -- Add session idle ms (900000), max sessions (4), cookie name (`pc_session`), KDF rounds/tick (200); leave TFT_* and HTTP size limits intact except reuse.
- `src/provisioning/verifier.py:41–126` -- Reuse `verify`/`pbkdf2` primitives; add or companion incremental `KdfJob` stepper (≤200 rounds/tick) under `src/provisioning/` (e.g. `kdf_job.py`) — do not call full `verify_admin_password` on the HTTP path in one tick.
- `src/provisioning/session.py` (new) -- Pure session table: create/lookup/expire/renew/full; base64url encode/decode + constant-time ID compare; host-testable with FakeTicks.
- `src/device/web/http_parse.py` -- Add cookie-name parse helper from raw `Cookie` header (today stores raw string only).
- `src/device/web/pages.py:314–332` -- Extend `http_response` for optional `Set-Cookie` / Location; add `login_page_html` / `settings_page_html` (UX tokens from epic-2; password/theme rows visible but change POST deferred to 2.2); responses for redirect, incorrect password, busy.
- `src/device/web/router.py` -- Keep `route_setup_request` SETUP_AP-only; add `route_config_request` (or unified dispatcher) for `/login`, `/`|`/settings` under STATION_ONLINE with session guard + login POST → KDF dispatch action.
- `src/device/web/server.py:115–250` -- Dispatch by mode (setup vs config); hold client across KDF like Connect hold; surface login/session actions without blocking.
- `src/device/network/coordinator.py:139–141,335–366` -- While STATION_ONLINE (after drop-watch), tick HTTP + advance at most one KDF job; load salt/verifier from SettingsStore for verify; never call App/TFT.
- `src/device/settings_store.py` -- Read-only `load()` for salt/verifier on login; no schema change.
- UX reference (read-only): `_bmad-output/planning-artifacts/wifi-config/ux-designs/mockups/key-config-login.html`, `key-config-settings.html`.
- Tests: mirror `tests/test_setup_http.py` / `test_setup_candidate.py` FakeStream/FakeTicks patterns; new `tests/test_config_auth*.py`, `tests/test_session*.py`; extend coordinator suite for STATION_ONLINE HTTP tick.
- Read-only: pins, epic-1 recovery overlays, SettingsStore commit protocol, Setup AP candidate handshake.

## Tasks & Acceptance

**Execution:**
- `src/config.py` -- Add auth/session/KDF budget constants -- checked-in AD-5 budgets.
- `src/provisioning/session.py` (+ optional `kdf_job.py`) -- Session table + cooperative KDF job API -- host-testable auth primitives.
- `src/device/web/http_parse.py` + `pages.py` + `router.py` + `server.py` -- Cookie parse; login/settings HTML; Config routing; Set-Cookie/redirect/busy; mode-dispatched server tick -- FR6 surface.
- `src/device/network/coordinator.py` -- Serve HTTP on STATION_ONLINE; own single KDF job + session table; wire store verifier into login -- non-blocking gate.
- `tests/test_session*.py`, `tests/test_config_auth*.py`, extend `tests/test_setup_http.py` / coordinator tests -- Cover I/O matrix; AST hygiene for pure modules.

**Acceptance Criteria:**
- Given the Device is `STATION_ONLINE`, when I request a protected Config route without a valid session, then the allowlisted router redirects me to a password-only login form and Setup routes are unavailable.
- Given the login form, when I submit an invalid password, then the page returns only `Incorrect password` without diagnostic detail, secret logging, or a session.
- Given a valid password, when the auth service verifies it using its versioned salted verifier and constant-time comparison where available, then it creates an opaque unpredictable entry in a checked-in bounded in-memory session table and sends an `HttpOnly`, `SameSite=Strict`, `Path=/` cookie.
- Given a valid session, when I open the Config page, then I see the mobile flat settings list with inline controls, approved visual tokens, semantic controls, and no external fetch or framework dependency.

## Spec Change Log

- Chose checked-in session cookie name `pc_session` (AD-5 / Design Notes).

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 16 findings — high 0, medium 11, low 2, false 3, maybe-false 0
- findings:
  - `[medium]` `[patch]` Station drop leaves KDF/held login unclean across reconnect — fixed: `_abort_config_auth` cancels job and `close_all` on drop before leaving ONLINE.
  - `[medium]` `[patch]` Peer abort mid-login still creates session slot — fixed: create session only when `has_held_client`; remove entry if queue fails.
  - `[medium]` `[patch]` Login Content-Type admits multipart via `"form"` substring — fixed: require `application/x-www-form-urlencoded` when present.
  - `[false]` `[reject]` Config templates never call `html_escape` — login/settings HTML is fixed strings with no user-controlled dynamic inserts; nothing to escape.
  - `[low]` `[reject]` No named diagnostic codes on login outcomes — not required by story ACs; unlikely everyday user defect; adding emit surface is more than a trivial correction.
  - `[medium]` `[patch]` `request.body` retains plaintext during held KDF — fixed: clear `request.body` after password bytearray copy; clear parser body on hold.
  - `[low]` `[reject]` Settings Save is silent no-op without disabled affordance — intentionally deferred to story 2.2 per Never / Design Notes.
  - `[false]` `[reject]` Incorrect-password copy/retry vs UX mockup — epic AC requires `Incorrect password` without period; empty field avoids echoing secret into HTML.
  - `[medium]` `[patch]` Missing tests for drop/peer-abort/multipart/malformed paths — fixed: added peer-abort, multipart reject, drop-mid-KDF tests; renew and KDF-budget assertions.
  - `[medium]` `[patch]` (edge) multipart Content-Type enters KDF path — same root as Content-Type patch above.
  - `[medium]` `[patch]` (edge) plaintext password lingering in parser during KDF — same root as body-clear patch above.
  - `[medium]` `[patch]` (edge) held peer closes before KDF finishes → orphan session — same root as peer-abort session patch above.
  - `[false]` `[reject]` (edge) `SessionTable.create` raises after job cleared → held never released — create only raises on bad urandom length; `os.urandom(16)` cannot trigger it.
  - `[medium]` `[patch]` (edge/claim) session exists without delivered cookie — same root as peer-abort session patch above.
  - `[medium]` `[patch]` (vg) authenticated GET renew never asserted through server path — fixed: advance FakeTicks past pre-renew deadline and re-GET settings.
  - `[medium]` `[patch]` (vg) cooperative KDF per-tick budget not observed — fixed: assert first `step(200)` returns `None` and `job.done` is false.

## Design Notes

**KDF admission:** Login POST that needs derive/verify starts one coordinator-owned job and drops the parsed body; a second concurrent login/KDF request gets fixed `503 Busy`. On match, create session (or busy if table full after expiry sweep) and Set-Cookie; on mismatch, re-render login with `Incorrect password` only.

**Settings shell vs 2.2:** Render Admin Password and Color Scheme rows (Forest & Amber visible) so the authenticated page matches UX; do not persist password changes or theme mutations in this story—POSTs for those can 404/405 or no-op until 2.2 without breaking 2.1 ACs.

**Cookie name:** Use a short fixed checked-in name (e.g. `pc_session`) from `config.py`; document in Code Map when chosen.

## Verification

**Commands:**
- `uv run pytest tests/test_session*.py tests/test_config_auth*.py tests/test_setup_http.py tests/test_network_coordinator.py -q` -- expected: all pass
- `uv run pytest -q` -- expected: full suite green; no new `machine`/`network`/`ntptime` imports in pure modules

## Auto Run Result

Status: done

**Summary:** STATION_ONLINE Config login with cooperative PBKDF2 verify, bounded in-memory sessions (`pc_session` HttpOnly/SameSite=Strict/Path=/), unauth redirects, and authenticated mobile flat settings shell. Review patched drop/KDF cleanup, orphan-session guard, Content-Type allowlist, body wipe, and renew/KDF-budget tests.

**Files changed:**
- `src/config.py` — session/KDF budget constants
- `src/provisioning/kdf_job.py`, `src/provisioning/session.py` — cooperative KDF + session table
- `src/device/web/{http_parse,pages,router,server}.py` — Config routes, pages, cookies
- `src/device/network/coordinator.py` — STATION_ONLINE HTTP + KDF ownership; drop abort
- `tests/test_session.py`, `tests/test_config_auth.py`, `tests/test_setup_http.py` — host coverage
- `epic-2-context.md`, `spec-2-1-…md`, `sprint-status.yaml` — planning/status

**Review:** Patched 6 medium entries (11 medium finding rows sharing those roots). Rejected: html_escape (false), diagnostics (low), Save stub (low), UX period/retain (false), create-raises (false). Deferred: none. Follow-up review recommended: true — unverified residual risk that drop-abort/`close_all` timing vs reconnect still has an untested race on real WLAN; patched medium count ≥2.

**Verification:** `uv run pytest` targeted suite 44 passed; full suite 254 passed.

**Residual risks:** On-device flash/browser proof not run here; password-change/theme POST remain story 2.2; NTP mailbox deferred while login KDF active (~100 ticks).
