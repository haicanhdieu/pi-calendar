---
title: 'Fix alert deletion from settings editor'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: '261a1cd04eaa94fcd6e606c5e761c0154ce48460'
review_loop_iteration: 0
context: []
warnings: []
deferred: []
---

## Intent

**Problem:** Deleting an alert from its Settings editor submits edit-form fields alongside `alert_action=delete`. The strict delete route rejects that browser request with `Invalid alert action.`

**Approach:** Render deletion as a separate authenticated form containing only `alert_action=delete` and the selected stable `alert_id`. Add a live-device E2E regression that derives submitted fields from the rendered delete form and verifies alert disappears.

## Boundaries & Constraints

**Always:** Keep delete confirmation, auth boundary, exact-id deletion, strict delete-field validation, and atomic SettingsStore commit. Preserve edit form behavior and neighboring settings.

**Never:** Loosen delete route field validation, delete on GET, bypass confirmation, or mutate hardware pins/runtime scheduling.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY_PATH | Authenticated browser submits rendered Delete form for existing id | Exactly that alert is removed; Settings page shows deletion success | No error |
| EXTRA_FIELDS | Delete POST includes edit or unrelated form fields | No mutation | Existing invalid-action response remains |
| UNKNOWN_ID | Authenticated delete form names absent id | No mutation | Existing not-found response remains |
| UNAUTHENTICATED | Delete POST without valid session | No mutation | Existing login redirect remains |

## Code Map

- `src/device/web/page_alert_editor.py:7-47` -- edit form currently contains Delete submit button; hidden edit fields are submitted with it, conflicting with strict delete handler.
- `src/device/web/alert_route.py:62-91` -- `delete_alert` requires exactly action and id; retain this security validation.
- `src/device/web/settings_post.py:58-70` -- authenticated delete dispatch; success page reports deletion.
- `tests/test_config_auth.py:445-485,579-615` -- existing route markup, exact-id persistence, and extra-field rejection coverage; preserve and extend markup checks if needed.
- `tests_e2e/test_settings_page_e2e.py:250-305` -- live-device alert round trip currently hand-builds delete request; change to submit fields read from rendered delete form.
- `tests_e2e/config_mode.py` -- ensures live target serves authenticated config page before E2E suite.

## Tasks & Acceptance

**Execution:**
- `src/device/web/page_alert_editor.py` -- render standalone Delete form with only action/id after edit form closes -- make browser POST match strict route contract.
- `tests/test_config_auth.py` -- assert delete form is independent and confirmation remains; preserve test that extra-field requests are rejected -- guard rendering and route boundary.
- `tests_e2e/test_settings_page_e2e.py` -- extract successful editor's rendered delete form fields and submit them against live settings endpoint -- reproduce browser-originated regression and verify persistence/rendered result.

**Acceptance Criteria:**
- Given authenticated editor for existing alert, when browser submits rendered Delete form after confirmation, then only selected alert is removed, page reports `Alert deleted.`, and subsequent settings page omits its id.
- Given rendered edit form, when user saves edits, then existing edit fields and values still submit and persist normally.
- Given delete POST with extra fields or unknown id, when submitted, then server rejects it and stored alert list remains unchanged.
- Given unauthenticated delete request, when submitted, then existing authentication redirect occurs and stored data remains unchanged.

## Verification

**Commands:**
- `uv run pytest tests/test_config_auth.py` -- expected: focused rendering, strict validation, auth, and persistence tests pass.
- `uv run --with requests pytest tests_e2e/test_settings_page_e2e.py -k alert_add_edit_delete_round_trip -v` -- expected: live-device regression passes after flashing updated firmware; suite skips if target unavailable.
- `git diff --check` -- expected: no whitespace errors.
- `graphify update .` -- expected: graph reflects source changes.

**Manual checks (device):** Flash firmware, open Settings, edit an alert, confirm Delete, and verify alert disappears without `Invalid alert action.` Host tests cannot prove browser/device behavior.


### 2026-09-23 — Review pass
- verdicts: 12 findings — high 0, medium 8, low 0, false 4, maybe-false 0
- findings:
  - `[false]` `[reject]` Generated Graphify files add broad unrelated diff — `graphify update .` is required after source edits by repository policy; graph files now reflect current source and new spec.
  - `[medium]` `[patch]` E2E setup could leave created alert behind on pre-cleanup assertion failure — moved creation and subsequent setup inside `try/finally`, with new-id discovery for cleanup.
  - `[medium]` `[patch]` E2E parser did not validate rendered form method/action — parser now requires POST `/settings` before submission.
  - `[medium]` `[patch]` E2E parser overwrote duplicate named fields — parser now retains ordered controls and requires exactly one delete action and alert id.
  - `[medium]` `[patch]` Unit test depended on exact form serialization — replaced string splitting with tolerant HTML form-boundary parsing.
  - `[medium]` `[patch]` Unit markup check omitted form method/action — now checks both edit and delete forms target POST `/settings`.
  - `[medium]` `[patch]` Confirmation text assertion did not bind confirmation to Delete button — test now checks submit button and its confirmation handler inside delete form.
  - `[false]` `[reject]` JavaScript-disabled confirmation behavior was unspecified — confirmation behavior predates change and requested intent does not introduce a no-JavaScript requirement.
  - `[false]` `[reject]` Add-editor disabled Delete case was absent from matrix — disabled Add-editor behavior is unchanged and outside alert deletion regression.
  - `[medium]` `[patch]` E2E test submitted hand-built fields and missed rendered successful controls — it now submits fields parsed from delete form and asserts exact action/id payload.
  - `[medium]` `[patch]` E2E parser ignored checked checkbox/radio and other successful controls — parser now captures named successful controls; exact payload assertion rejects extras such as `alert_enabled`.
  - `[false]` `[reject]` E2E did not click native confirmation in a browser — this live-device E2E suite exercises HTTP using rendered form payloads; request asked for E2E verification of deletion behavior, and unchanged unit markup test verifies the confirmation handler remains.

## Auto Run Result

Status: done

Summary: Split alert deletion into a standalone POST form with only `alert_action=delete` and the selected `alert_id`, preserving strict server validation. Added rendered-form and live-device E2E regression coverage.

Files changed:
- `src/device/web/page_alert_editor.py` — keep Delete controls out of edit form submission.
- `tests/test_config_auth.py` — verify separate form, route, allowed fields, and confirmation.
- `tests_e2e/test_settings_page_e2e.py` — derive delete submission from rendered controls and guarantee cleanup.
- `graphify-out/` — refresh repository knowledge graph after source changes.
- `_bmad-output/implementation-artifacts/alert-clock/spec-settings-delete-alert-action.md` — record plan, review, and result.

Review findings: patched 8 medium findings; deferred 0; rejected 4 findings as recorded above. Patched counts by verdict: high 0, medium 8, low 0. Follow-up review recommended because live-device E2E remains unverified on updated firmware.

Verification:
- `uv run pytest tests/test_config_auth.py` — passed, 58 tests.
- `uv run --with requests pytest tests_e2e/test_settings_page_e2e.py -k alert_add_edit_delete_round_trip -v` — live target first exposed old page markup (firmware predates fix); retry then returned HTTP 503 at login due device session-table exhaustion. Test now uses rendered form fields and cleanup. Flash updated firmware and reset device before live E2E rerun.
- `git diff --check` — passed.
- `graphify update .` — completed.

Residual risk: browser/device deletion behavior needs confirmation after flashing updated firmware; host tests cannot establish Pico behavior.
