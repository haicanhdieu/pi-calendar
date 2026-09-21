# Technical / Brownfield Review — Alert Clock Spine

Reviewed: 2026-09-21  
Target: `ARCHITECTURE-SPINE.md` draft

## Verdict

**Conditional pass.** Functional-core / imperative-shell choice, `App` state
ownership, `SettingsStore` persistence boundary, `TouchPort` integration, and
`machine.PWM` adapter boundary fit existing code. Resolve settings migration and
runtime configuration-notification contract before finalizing. Both otherwise
permit independently-built parts to diverge or break configured devices.

## Confirmed Technology Assertions

| Assertion | Result | Evidence |
| --- | --- | --- |
| Pico W is supported MicroPython target | Confirmed | Official Pico W download page identifies Raspberry Pi Pico W and publishes its firmware releases. |
| `1.29.0` is current stable at review date | Confirmed | Official Pico W page lists `v1.29.0 (2026-08-24)` as latest release; `v1.30.0` entries are preview builds. |
| `machine.PWM` is valid output abstraction | Confirmed | Official docs define `machine.PWM`, `freq`, `duty_u16`, and `deinit`; RP2 has 8 PWM blocks on RP2040. |
| Existing repository fits stated paradigm | Confirmed | `src/app.py` already owns mutable `AppState`; `src/ticks.py`, `src/time/`, `src/ui/touch_state.py`, and validation logic are pure; hardware stays under `src/device/` plus `main.py`. |

Official sources: [Pico W firmware releases](https://www.micropython.org/download/RPI_PICO_W/), [MicroPython PWM documentation](https://docs.micropython.org/en/latest/library/machine.PWM.html).

## Findings

### High — AD-4 requires migration contract, not only a versioned record

Current `src/provisioning/validation.py` accepts exactly seven v1 keys and
rejects every extra key; it also rejects every `settings_version != 1`.
`SettingsStore.load()` treats rejected records as unconfigured. Adding
`alerts`, `postpone_delay_minutes`, and postponed state without an explicit
v1-to-alert schema migration can therefore send already-configured devices into
Setup AP or discard their settings.

Spine says migration preserves Wi-Fi/admin fields, but does not bind:

- alert schema/version target;
- accepted legacy input shape;
- pure migration/normalization owner and validation order;
- atomic write-back point and failure behavior;
- defaults for legacy users (`alerts=[]`, delay `10`, no pending occurrence).

**Required spine fix:** make this an AD-4 rule. Existing validators and both
`SettingsStore.commit()` callers in `NetworkCoordinator` must use result. Do
not split alert data into second file.

### High — Web save → scheduler visibility boundary absent

`NetworkCoordinator.tick()` runs before `App.step()` in `main.py`. Existing
config mutations commit via `SettingsStore`; `App` receives only
`NetworkEvent`s. No existing event or retained version tells `App` that a web
save changed configuration. Alert scheduler cannot safely choose when to
replace its candidate configuration, especially while an occurrence captures
old member identities under AD-3.

**Required spine fix:** bind one route, e.g. coordinator emits typed
`alert_settings_changed(record/version)` after successful atomic commit and
`App` adopts it between touch handling and due detection; or give `App` an
explicit bounded settings revision/read boundary. State whether a failed save
emits no event and whether boot obtains normalized record before first due
evaluation.

### Medium — PWM pin/slice safety deferred correctly, but completion gate needs resource check

Deferring GPIO, voltage, polarity, driver circuit, and frequency until bench
verification matches `docs/hardware_configuration.md` and PRD. Add exact
completion evidence: selected GPIO must not collide with TFT/touch pins, and
its RP2040 PWM slice/channel/frequency coupling must not conflict with any
existing or planned PWM user. MicroPython notes a PWM frequency change can
affect other outputs sharing underlying generator. Include this in deferred
bench checklist, then record it in hardware docs.

### Medium — “current stable” is correct, release pin is stronger than “current”

`1.29.0` verified on review date and matches parent Wi-Fi/touch spines. Keep
the exact release for reproducibility; avoid implementation depending on
`latest` documentation, which is development-branch documentation. Target
flashed firmware identity still needs device evidence before deployment.

## No Blocking Fit Problems Found

- `BuzzerPort.tick(now, sounding)` preserves existing cooperative loop shape.
- `machine.PWM` belongs below `src/device/`; pure `src/alert/` remains host-testable.
- Exclusive `active-alert` surface extends current `active_surface` model and
  touch edge semantics without introducing interrupt state writes.
- Civil due time versus wrap-safe elapsed deadlines matches current
  `ticks_add`/`ticks_diff` contract.

## Finalization Gate

Do not mark spine final until two High findings are bound as architecture rules
and source PRD/UX reconciliation confirms them. Then run migration and config
visibility host tests; PWM/touch/audio claims require flashed-device evidence.
