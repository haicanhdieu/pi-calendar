---
title: 'GitHub Issue #1: ICS Calendar URL Setting'
type: 'feature'
created: '2026-09-18'
status: 'draft'
route: 'dispatch'
review_loop_iteration: 1
baseline_commit: '0fb4f0735c22e6b6dc0aa8846926c243117f013a'
github_issue: 'https://github.com/haicanhdieu/pi-calendar/issues/1'
context:
  - 'AGENTS.md'
  - '_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Device settings page has no way for owner to provide an ICS calendar URL. Clock renderer supports caller-provided upcoming events, but no calendar source exists.

**Approach:** Add authenticated ICS URL control to settings page and persist its optional value without weakening existing settings-record recovery. Missing, malformed, or unreachable URL must produce no calendar-data error and leave clock behavior unchanged.

**Decision:** End-to-end ICS sync. Device retrieves/parses saved ICS data and supplies up to three upcoming timed events to the existing clock renderer; inaccessible sources yield no events without disrupting normal operation.

**Decision:** Support normal `https://` hostname ICS URLs. DNS and TLS must advance without freezing the cooperative firmware loop; a bounded native/async transport dependency and flashed-Pico proof are required before deployment.

## Boundaries & Constraints

**Always:** Keep station-only admin assets lazy and short-lived; preserve cooperative loop and secret-free diagnostics. Settings persistence remains solely in `SettingsStore`, retains atomic recovery behavior, and accepts existing valid version-1 settings records. URL must be HTML-escaped before re-render. Pure ICS parsing/selection code cannot import `machine`, `network`, or `ntptime`. Existing password-change commit must preserve saved URL.

**Never:** Do not add setup-page fields, change Wi-Fi/admin credentials, block network tick for DNS/HTTP, expose URL or request contents in diagnostics, alter touch UI, or claim host tests prove Pico heap/radio/browser behavior. Invalid/unreachable calendar source must not interrupt clock or calendar rendering.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Save URL | Authenticated admin submits valid ICS URL | URL is retained in settings and shown after redirect/reload | Atomic commit failure leaves prior settings and page usable |
| Clear URL | Authenticated admin submits empty URL | URL is removed/disabled; existing no-events behavior remains | No fetch attempted |
| Existing record | Valid deployed v1 record has no ICS field | Device remains configured and admin page loads | Default URL is absent, no reprovisioning |
| Invalid form | URL fails selected syntax/size policy | No setting change | Return bounded bad request; do not echo unsafe text |
| Source unavailable | Saved URL cannot resolve/connect/read/parse | Rendering continues with no new events | Named secret-free diagnostic; bounded retry policy |
| Source valid | Saved URL yields future timed events | Up to three soonest formatted events reach existing ClockView input | Malformed individual data ignored without failing loop |

</frozen-after-approval>

## Code Map

- `src/device/web/page_settings_content.py` — `settings_page_html()` creates current short admin form; add ICS control without adding setup-path imports.
- `src/device/web/pages.py` — lazy settings-page wrapper and response builder; pass persisted display state only after authenticated station request.
- `src/device/web/router.py` — authenticated `POST /settings` currently accepts only `new_password` and creates password KDF job; needs a separate bounded URL-save route/result or an extended request model that preserves password lifecycle.
- `src/device/web/server.py` — config dispatch owns parser release and held KDF clients; keep URL request body released before subsequent allocations.
- `src/device/network/coordinator.py` — password-change completion reloads settings and commits fixed fields; preserve ICS URL and own any future runtime sync work.
- `src/device/settings_store.py` and `src/provisioning/validation.py` — strict exact-key version-1 record and canonicalizer; need backwards-compatible optional/default URL representation before store can persist it.
- `tests/test_config_auth.py` — settings page, route, and station-online auth contracts.
- `tests/test_settings_store.py` — record validation, commit, backup/recovery contracts.
- `tests/test_clock_view.py` — existing renderer takes preformatted events; do not change unless option B needs integration coverage.
- `_bmad-output/implementation-artifacts/touch-ui/spec-clock-upcoming-events.md` — predecessor explicitly deferred ICS/API source; use as scope boundary.

## Tasks & Acceptance

**Execution:**
- [ ] `src/provisioning/validation.py`, `src/device/settings_store.py`, tests — define backwards-compatible optional ICS URL setting and atomic preservation through all commits/recovery paths.
- [ ] `src/device/web/page_settings_content.py`, `src/device/web/pages.py`, `src/device/web/router.py`, `src/device/web/server.py`, tests — render authenticated URL field, validate/save/clear it, escape retained value, and release request data promptly.
- [ ] `src/device/network/coordinator.py`, relevant tests — preserve URL through password changes; if option B, integrate bounded retrieval failures as non-fatal no-event outcomes.
- [ ] New pure ICS/sync modules and tests — only if option B; parse/select events and inject preformatted rows into existing clock path without device imports.
- [ ] `_bmad-output/implementation-artifacts/wifi-config/` — record required flashed-Pico evidence if network retrieval or config serving changes touch heap/radio paths.

**Acceptance Criteria:**
- Given authenticated admin on station-online settings page, when page loads, then it offers an ICS calendar URL field alongside existing settings.
- Given a saved URL, when password changes, then URL remains saved and valid settings record remains recoverable.
- Given no saved URL, when device runs, then calendar/clock behavior remains unchanged.
- Given saved URL cannot be reached or parsed, when retrieval runs, then cooperative loop continues and clock uses existing no-event behavior without surfacing secrets.
- Given legacy valid settings record, when firmware boots, then it remains configured with ICS URL treated as absent.

## Implementation Notes


## Spec Change Log


## Review Triage Log

### 2026-09-18 — Review pass 1

- `intent_gap` — Settings validation and UI accept ordinary HTTPS/hostname URLs while a safe Pico transport can only retrieve numeric IPv4 HTTP; user-visible URL support is undefined. Need a decision between constrained URL support and a nonblocking DNS/TLS transport.
- `high` — Failed refresh retains prior events, violating required unavailable-source no-event behavior. Moot pending URL-support re-derivation.
- `medium` — Clearing or replacing a URL leaves an in-flight socket/request alive and can display prior-source events. Moot pending URL-support re-derivation.
- `medium` — UTC and TZID timestamps lack required local-time conversion semantics. Intent does not define timezone policy.
- `low` — Out-of-range ICS date/time fields are accepted. Parser must reject malformed components on re-derivation.
- `medium` — Per-tick settings reads and response copies risk Pico heap/flash pressure. Re-derivation must use bounded retained state and streaming/body limits.
- `low` — RFC 5545 summary escaping is incomplete. Normalize supported text escapes before rendering.
- `medium` — No test exercises successful nonblocking HTTP transport or coordinator-to-clock provider seam. Re-derivation needs host coverage for both.


## Design Notes

Keep schema migration additive and backward-compatible: deployed exact-key v1 records cannot be made invalid merely because calendar URL is new. Avoid loading full admin assets or any ICS retrieval code on setup path. If end-to-end sync is selected, use injectable bounded port/state-machine design; a single blocking `urequests`/DNS call violates coordinator contract.

## Verification

**Commands:**
- `uv run pytest tests/test_settings_store.py tests/test_config_auth.py -q` -- expected: existing settings/auth behavior plus URL coverage pass.
- `uv run pytest -q` -- expected: host suite passes with no regression.

**Manual checks:**
- Flash Pico W, clear `.settings-v1` where required, authenticate on LAN, save/clear URL, and capture serial checkpoints plus unavailable-source result. Do not treat host results as Pico radio/heap/browser proof.
