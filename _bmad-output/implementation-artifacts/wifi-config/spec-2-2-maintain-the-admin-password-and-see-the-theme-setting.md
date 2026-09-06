---
title: 'Maintain the Admin password and see the theme setting'
type: 'feature'
created: '2026-09-07'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: 'f019cd50f75381da04cbf412f3eb5faca20d276d'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/wifi-config/epic-2-context.md'
warnings: []
deferred:
  - summary: >-
      Password-change admit renew is not uniquely asserted under advancing ticks while KDF is in flight.
    evidence: |-
      Router sets renew_session_id and server calls renew before hold, but host tests use frozen FakeTicks;
      post-success liveness can also be explained by keep_only renewing after commit. A test that advances
      past the pre-admit deadline mid-derive would settle whether mid-admit renew is load-bearing.
    location: >-
      src/device/web/server.py:_dispatch_config
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Authenticated Config shows Admin Password and Color Scheme rows, but Save does not persist a new Admin verifier, other sessions stay valid after a credential change, and theme selection is not yet guaranteed as an inert no-op.

**Approach:** Wire authenticated password-change POST through the same cooperative KDF + SettingsStore commit path as Setup, keep the acting session and invalidate others on success with `Password changed.` announced, and leave Color Scheme as a single disabled Forest & Amber stub that never errors or mutates settings.

## Boundaries & Constraints

**Always:**
- Config password/theme routes only while `STATION_ONLINE`; reuse 2.1 session cookie (`pc_session`), idle renew, and mode gates.
- New Admin password: UTF-8 length 8–63, no NUL (same band as Setup admin); derive with PBKDF2-HMAC-SHA256 + fresh 16-byte salt; atomic SettingsStore commit preserving existing Wi-Fi fields and `color_scheme: "forest-amber"`.
- Cooperative KDF: at most one `KdfJob`; ≤200 rounds/tick; concurrent KDF → fixed `503 Busy`; wipe password bytearrays on every terminal outcome; never return/log plaintext, verifiers, salts, cookies, bodies, or raw headers.
- On successful change: one terminal coordinator transition keeps only the acting session ID, renews it 15 minutes, and applies the new verifier immediately to subsequent logins.
- On derivation or commit failure: leave the old verifier and every session unchanged; do not announce success.
- Theme UI: exactly one preselected, visually disabled `Forest & Amber` option; selection is an inert no-op that must not error or persist a different scheme.
- Host-testable policy/auth/HTTP without `machine`/`network`/`ntptime`.

**Never:**
- Force re-login of the acting session; add logout, recovery, factory reset, TLS, WAN exposure, username, multi-theme logic, or CSRF beyond SameSite.
- Change TFT pins/SPI, display lifecycle, epic-1 STA recovery, or settings record schema keys.
- Block the render loop with full 20k-iteration PBKDF2 in one tick.
- Persist plaintext Admin or mutate `color_scheme` away from `forest-amber`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy change | Auth session; POST valid `new_password` | Commit new salt/verifier; keep acting session; drop others; settings page announces `Password changed.` | Wipe password bytes |
| Old vs new login | After change; login with old / new password | Old → Incorrect password; new → session | Unchanged reject path |
| Theme open/select | Auth GET settings; open Color Scheme; tap option | One disabled Forest & Amber; no error; store unchanged | No-op |
| Unauth / wrong mode | No session or not STATION_ONLINE | Redirect login / 404; settings unchanged | Clear bad cookie |
| Malformed / short / concurrent | Bad body/CT/length or KDF busy | 400 / 503 Busy; verifier + sessions unchanged | Fixed bodies |
| Commit/derive fail | KDF or SettingsStore fails after auth | Settings unchanged; all sessions remain; no success banner | Wipe password bytes |

</intent-contract>

## Code Map

- `src/provisioning/kdf_job.py` -- Extend beyond `PURPOSE_LOGIN_VERIFY`: add derive purpose (e.g. `password_change_derive`) with fresh salt, terminal `DERIVE_OK`/`DERIVE_*` codes, and salt_hex/verifier_hex available to the coordinator before wipe; keep ≤200 rounds/tick.
- `src/provisioning/session.py` -- Add keep-only/invalidate-others API: after expiry sweep, retain acting encoded ID, drop the rest, renew acting deadline (`ticks_add(now, SESSION_IDLE_MS)`).
- `src/provisioning/validation.py` -- Reuse/admin-only field check for new password UTF-8 8–63 / no NUL (mirror Setup admin band); do not invent new length constants ad hoc in the router.
- `src/device/settings_store.py:190–262` -- Reuse `commit(..., admin_salt_hex=, admin_verifier_hex=)` with loaded `wifi_ssid`/`wifi_password` and `COLOR_SCHEME_V1`; no schema change.
- `src/device/web/pages.py:434–470,577–578` -- Wire Save into `POST` form (`new_password`); `settings_page_html(password_changed=False)` success banner `Password changed.` (`aria-live`); keep theme stub disabled/`aria-disabled`; approved tokens from epic-2.
- `src/device/web/router.py:88–159` -- Authenticated `POST /`|`/settings` → password-change KDF action (session required, renew acting id); reject unauth/malformed/busy like login; theme needs no mutating route.
- `src/device/web/server.py` -- Hold client across password-change KDF like login; surface new action without blocking; clear request body after password bytearray copy.
- `src/device/network/coordinator.py:380–475` -- Own password-change job; on `DERIVE_OK` commit then `keep_only` acting session; on any fail leave store/sessions untouched; abort job on station drop like `_abort_config_auth`.
- UX read-only: `_bmad-output/planning-artifacts/wifi-config/ux-designs/mockups/key-config-settings.html`.
- Continuity (2.1): `session.py`, `pc_session`, login verify job, `route_config_request`, STATION_ONLINE HTTP tick — extend, do not rewrite.
- Tests: extend `tests/test_config_auth.py`, `tests/test_session.py`; add password-change/theme coverage; AST hygiene for pure modules.

## Tasks & Acceptance

**Execution:**
- `src/provisioning/kdf_job.py` + `session.py` + `validation.py` -- Derive-purpose job, keep-only sessions, new-password field validation -- AD-3/AD-5 password-change primitives.
- `src/device/web/pages.py` + `router.py` + `server.py` -- Form POST, success banner, authenticated password-change route/hold -- FR7/FR8 surface.
- `src/device/network/coordinator.py` (+ SettingsStore reuse) -- Derive → atomic commit → invalidate others/renew acting; fail-closed -- non-blocking gate.
- `tests/test_session.py`, `tests/test_config_auth.py` (+ coordinator coverage as needed) -- Cover I/O matrix; old/new login; theme inert; fail-closed commit/KDF.

**Acceptance Criteria:**
- Given an authenticated Config session, when I open the inline Admin Password control and submit a valid replacement, then SettingsStore atomically persists only its new verifier, the current session remains usable, all other sessions are invalidated, and the UI announces `Password changed.`
- Given a completed password change, when another browser or a subsequent login uses the old password, then it is rejected; when it uses the new password, then it succeeds.
- Given the authenticated settings list, when I open Color Scheme, then the visible inline picker shows exactly one preselected, disabled `Forest & Amber` option; selecting it is a no-op and never errors.
- Given the password and theme controls, when their requests are malformed, unauthorized, or outside `STATION_ONLINE`, then the router rejects them through the defined bounded HTTP/auth behavior and does not disclose or alter settings.

## Spec Change Log

## Review Triage Log

### 2026-09-07 — Review pass
- verdicts: 18 findings — high 0, medium 3, low 4, false 10, maybe-false 1
- findings:
  - `[false]` `[reject]` Short/empty new_password returns bare 400 instead of settings with inline error — matrix requires fixed 400 for malformed/short; matches login allowlist pattern for bad input.
  - `[low]` `[reject]` Missing minlength/maxlength on new-password field — everyday users still get server 400; adding client constraints is more than a trivial correction and not required by ACs.
  - `[false]` `[reject]` Derive/commit failure has no error aria-live — Design Notes/Always require fail-closed without success announcement; silence is intentional.
  - `[false]` `[reject]` Peer abort mid-change still commits — Always requires derive→commit→keep_only on success; held client only gates response delivery (unlike login session mint).
  - `[false]` `[reject]` acting_id None skips keep_only — router always sets renew_session_id from the looked-up entry before ACTION_PASSWORD_CHANGE_KDF.
  - `[false]` `[reject]` salt_hex/verifier_hex remain on KdfJob after DERIVE_OK — intentional handoff for commit; cleared on non-success terminals; job dropped after finish.
  - `[low]` `[reject]` No peer-abort mid password-change host test — intentional commit-on-success behavior; adding abort policy tests would invent requirements not in the intent.
  - `[medium]` `[patch]` Missing multipart Content-Type coverage for password-change POST — fixed: added `test_password_change_multipart_content_type_rejected`.
  - `[low]` `[reject]` Test helper skips form-urlencoded escaping for exotic passwords — test harness only; production path uses parse_form_urlencoded.
  - `[low]` `[reject]` Theme stub lacks aria-selected/pointer-events — AC satisfied by disabled Forest & Amber + no mutating route; extra ARIA is polish.
  - `[false]` `[reject]` Success banner placement vs mock toast — AC only requires announcing `Password changed.`; page-level aria-live banner meets it.
  - `[false]` `[reject]` keep_only False after commit still shows success — acting id is present at admit and renewed; False only if session already expired mid-KDF (table cleared); verifier change is still correct.
  - `[medium]` `[patch]` ValidationResult retains plaintext after bytearray copy — fixed: `check = None` immediately after copy in `_route_password_change_post`.
  - `[false]` `[reject]` Approach “same path as Setup” overclaim — both use SettingsStore commit + PBKDF2; Config’s cooperative KdfJob vs Setup’s in-commit derive is intentional; fixing would edit intent/spec text.
  - `[false]` `[reject]` (claim) AC “session remains usable” vs keep_only False — same root as keep_only False row; unreachable when acting session survives admit renew.
  - `[medium]` `[patch]` Derive-fail fail-closed path never exercised — fixed: added `test_coordinator_password_change_derive_fail_leaves_sessions`.
  - `[maybe-false]` `[defer]` Password-change admit renew not uniquely observed under advancing ticks — mid-KDF wall time ≪ 15m idle; keep_only renews on success; deferred with unverified medium note.
  - `[false]` `[reject]` (vg other) Success announced when keep_only fails — duplicate of keep_only False claim; same refutation.

## Design Notes

**Acting session:** Password change does not mint a new cookie. After successful commit, `keep_only(acting_id)` + renew; other browser sessions fail the next protected request (clear cookie + redirect login).

**KDF purposes:** Login remains verify-against-stored; password change is derive-with-fresh-salt. Still one job slot — concurrent login or change while busy → `503 Busy`.

**Theme:** No theme POST required. Client-side disabled option + no mutating server route satisfies “selecting it is a no-op and never errors”; `color_scheme` stays `forest-amber` on password commits.

**Fail-closed:** If derive finishes but commit raises `SettingsCommitError`, do not invalidate sessions and do not show `Password changed.`

## Verification

**Commands:**
- `uv run pytest tests/test_session.py tests/test_config_auth.py tests/test_setup_http.py tests/test_network_coordinator.py -q` -- expected: all pass
- `uv run pytest -q` -- expected: full suite green; no new `machine`/`network`/`ntptime` imports in pure modules

## Auto Run Result

Status: done

**Summary:** Authenticated Config password change via cooperative derive KDF → atomic SettingsStore commit (Wi-Fi + `forest-amber` preserved) → `keep_only` acting session with `Password changed.` announcement; Color Scheme remains a single disabled Forest & Amber stub. Review patched plaintext drop on admit, derive-fail fail-closed coverage, and multipart Content-Type rejection.

**Files changed:**
- `src/provisioning/kdf_job.py` — derive purpose + DERIVE_* terminals + salt/verifier hex handoff
- `src/provisioning/session.py` — `keep_only` acting-session API
- `src/provisioning/validation.py` — `validate_admin_password_field`
- `src/device/web/{pages,router,server}.py` — form POST, success banner, password-change hold/route
- `src/device/network/coordinator.py` — password-change KDF ownership, commit, fail-closed
- `tests/test_session.py`, `tests/test_config_auth.py` — matrix + review patches
- `spec-2-2-…md`, `sprint-status.yaml` — planning/status

**Review:** Patched 3 medium entries (plaintext wipe, derive-fail test, multipart test). Deferred: mid-admit renew under advancing ticks (maybe-false/medium unverified). Rejected: bare 400 (false), minlength (low), fail silence (false), peer-abort commit (false), acting_id None (false), salt_hex handoff (false), peer-abort test (low), form escaping in helper (low), theme ARIA polish (low), banner vs mock (false), keep_only False success (false×2), Setup-path claim (false). Follow-up review recommended: true — residual risk that near-idle acting sessions could expire during cooperative derive if admit renew regresses unnoticed (deferred; ≥2 medium patches).

**Verification:** targeted suite 54 passed; full suite 264 passed.

**Residual risks:** On-device flash/browser proof not run; deferred mid-admit renew tick assertion; real FS commit-fail modes beyond patched `store.commit` raise.
