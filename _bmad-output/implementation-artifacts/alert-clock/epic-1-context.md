# Epic 1 Context: Browser-Managed Alert Configuration

Source: `_bmad-output/planning-artifacts/alert-clock/epics/epics.md`, alert-clock architecture/UX artifacts, and completed Story 1.1.

## Scope

Epic 1 owns authenticated browser configuration for up to ten persisted alerts and the global postpone delay. Story 1.2 adds only a new alert; edit, delete, postpone-delay mutation, scheduling, TFT, buzzer, and later stories remain out of scope.

## Decisions

- SettingsStore is sole persistence boundary. Canonical alert-capable settings are version 2 with `alerts` and `postpone_delay_minutes`.
- Alert record: stable lowercase string `id`, integer `hour` 0–23, integer `minute` 0–59, boolean `enabled`, weekday list with Monday index 0; empty weekday list means one-time.
- Maximum ten stored alerts. Whole-record validation precedes one atomic commit. Existing Wi-Fi/admin fields must survive.
- Config routes require existing authenticated session. Browser page stays one flat page using existing palette/layout.
- Existing password-change commit must preserve alerts and postpone delay.

## Completed continuity

Story 1.1 migrated valid v1 records atomically, rendered authenticated alert rows/empty state, added readable recurrence formatting, preserved alert fields during password changes, and corrected required architecture/UX artifacts. Its implementation spec is `stories/1-1-view-stored-alerts-on-the-config-page.md` and commit is `17560d6ba0243eab68de8a720f366e00276099bc`.

## Story 1.2 implementation map

- `src/provisioning/validation.py`: extend/reuse strict v2 alert validation and expose focused form/alert validation without hardware imports.
- `src/device/settings_store.py`: reuse `commit()` as atomic canonical write boundary; no second persistence path.
- `src/device/web/page_settings_content.py`: render Add alert control and inline editor with time, enabled state, seven text weekday controls, Save, Delete; render success/error feedback and ten-alert limit explanation. Do not add label/sound/volume/per-alert postpone.
- `src/device/web/router.py`: keep mutation authenticated; parse and validate add-alert form; reject malformed/missing/out-of-range values without commit; return a bounded result for coordinator.
- `src/device/web/server.py`, `src/device/network/coordinator.py`: carry authenticated add result through existing cooperative server/coordinator and commit current settings plus new alert atomically; preserve password flow.
- `tests/test_provisioning_validation.py`, `tests/test_settings_store.py`, `tests/test_config_auth.py`: cover valid add, recurrence, invalid/no-op save, limit, auth boundary, persistence, and preservation.

## Constraints

Pure validation must remain CPython-compatible. No hardware behavior. Do not implement edit/delete/delay mutation or later alert runtime stories. Host tests cannot prove Pico/browser hardware behavior.
