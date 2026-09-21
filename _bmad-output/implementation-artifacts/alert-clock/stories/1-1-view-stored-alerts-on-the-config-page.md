---
title: 'View stored alerts on the Config page'
type: 'feature'
created: '2026-09-21'
status: 'done'
baseline_revision: '0b5207b'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/alert-clock/epics/epics.md
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/alert-clock/architecture/ARCHITECTURE-SPINE.md
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/alert-clock/ux-designs/DESIGN.md
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Existing authenticated Config has no alert section, and version-1 settings records cannot carry alert configuration. Owners need to inspect stored alerts without exposing settings to unauthenticated callers.

**Approach:** Migrate valid version-1 records atomically to the alert-capable record with empty alert defaults, pass canonical alert data only through the authenticated settings-page render, and render readable rows or an explicit empty state. Preserve existing auth, settings, and unsupported-record quarantine behavior.

## Boundaries & Constraints

**Always:** `SettingsStore` remains sole persistence boundary; migration preserves existing Wi-Fi/admin values; alert page remains inline on authenticated Config; HTML escapes stored values; pure validation stays host-compatible; use inherited browser palette and layout.

**Never:** Do not implement add/edit/delete/delay mutation routes, scheduling, TFT alert UI, buzzer behavior, new navigation, or later stories. Do not expose alert data before session validation or in login/redirect responses.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Legacy migration | Valid version-1 record | Atomic version-2 record adds `alerts: []`, `postpone_delay_minutes: 10`; existing Wi-Fi/admin fields remain unchanged | Commit failure leaves valid old record and reports existing load failure behavior |
| Unsupported record | Unsupported settings version | Existing quarantine/unconfigured behavior unchanged; no alert fields added | No migration or invented defaults |
| Empty list | Authenticated Config, zero alerts | Inline `ALERTS` section and explicit empty state above `POSTPONE` | None |
| Stored rows | Authenticated Config with valid alert records | Each row shows local time, readable recurrence, and `On`/`Off` state | Malformed stored alert data is rejected by whole-record validation |
| Unauthenticated read | No session or expired session | Existing redirect to login; no alert values in response | Existing session cookie clearing behavior |

</intent-contract>

## Code Map

- `src/provisioning/validation.py` -- canonical settings schema and version validation; extend accepted alert-capable record while retaining strict legacy validation.
- `src/device/settings_store.py` -- sole atomic settings read/write boundary; migrate valid legacy records on load and preserve existing commit/recovery semantics.
- `src/device/web/page_settings_content.py` -- authenticated Config HTML; add escaped alert section, readable recurrence formatter, and empty state without mutation controls.
- `src/device/web/pages.py` -- lazy page/response wrapper; pass canonical alert data to settings renderer.
- `src/device/web/router.py` -- session gate for Config GET; load settings only after authentication and pass it to page response.
- `src/device/network/coordinator.py` -- owns `SettingsStore`; update authenticated GET response call sites to provide current settings while leaving password-change flow intact.
- `tests/test_settings_store.py` -- atomic migration, defaults, preservation, unsupported-version, and failure tests.
- `tests/test_config_auth.py` -- authenticated/unauthenticated Config rendering and alert-row HTML tests.
- `_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md` -- document shared versioned settings authority for alert migration.
- `_bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md` -- correct stale buzzer cadence text required by Story 1.1.

## Tasks & Acceptance

**Execution:**
- `src/provisioning/validation.py`, `src/device/settings_store.py` -- add strict version-2 alert fields, canonical alert validation, and atomic version-1-to-version-2 migration with defaults.
- `src/device/web/page_settings_content.py`, `src/device/web/pages.py`, `src/device/web/router.py`, `src/device/network/coordinator.py` -- render authenticated alert list/empty state and readable weekday recurrence; keep all alert routes session-protected and mutation-free.
- `tests/test_settings_store.py`, `tests/test_config_auth.py` -- cover migration, atomic failure, preserved fields, row/empty rendering, escaping, and auth boundary.
- `_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md`, `_bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md` -- apply required documentation corrections.

**Acceptance Criteria:**
- Given a valid version-1 record, when `SettingsStore` loads it, then it commits a valid version-2 record with alert defaults atomically and preserves Wi-Fi/admin values.
- Given an unsupported record, when `SettingsStore` loads it, then existing quarantine behavior remains unchanged and no alert fields are added.
- Given an authenticated Config session with zero alerts, when the page loads, then inline `ALERTS` and explicit empty state appear above `POSTPONE`.
- Given authenticated Config data containing repeating and one-time alerts, when the page loads, then each row shows escaped local time, word-based recurrence, and enabled state in the browser palette.
- Given no valid session, when Config or an alert path is requested, then existing authentication rejection occurs and alert values are absent.
- Given planning artifacts before implementation, when Story 1.1 completes, then parent settings-version authority and 180/220 ms cadence documentation are corrected.

## Spec Change Log

## Review Triage Log

### 2026-09-21 — Review pass
- verdicts: 0 findings — high 0, medium 0, low 0, false 0, maybe-false 0
- findings:
  - No auxiliary review agents launched because invocation explicitly prohibited agent spawning; manual diff review completed.

## Verification

**Commands:**
- `uv run pytest tests/test_settings_store.py tests/test_config_auth.py` -- expected: all targeted host tests pass.
- `uv run pytest` -- expected: full host suite passes.

## Auto Run Result

Status: done

Summary: Added atomic version-1 to version-2 settings migration with alert defaults, authenticated Config alert listing and empty state, readable recurrence rendering, preservation during password commits, and required architecture/UX documentation corrections.

Files changed:
- `src/provisioning/validation.py` -- validates alert-capable version-2 records.
- `src/device/settings_store.py` -- migrates legacy records and persists alert fields atomically.
- `src/device/web/page_settings_content.py` -- renders alert rows and postpone summary.
- `src/device/web/pages.py`, `src/device/web/router.py`, `src/device/web/server.py` -- carry settings through authenticated Config rendering.
- `src/device/network/coordinator.py` -- injects store data and preserves alert fields during password changes.
- `tests/test_settings_store.py`, `tests/test_config_auth.py` -- migration, rendering, and auth coverage.
- `_bmad-output/planning-artifacts/wifi-config/architecture/ARCHITECTURE-SPINE.md` -- shared versioned settings authority.
- `_bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md` -- corrected 180/220 ms cadence.

Review findings: No findings. Manual diff review used because agent spawning was explicitly forbidden.

Follow-up review recommendation: false.

Verification:
- `uv run pytest tests/test_settings_store.py tests/test_config_auth.py tests/test_provisioning_validation.py` -- 59 passed.
- `uv run pytest tests/test_memory_budget.py -q` -- 72 passed.
- `uv run pytest` -- 566 passed.

Residual risks: Pico hardware/browser behavior remains unverified; no on-device claim made.
