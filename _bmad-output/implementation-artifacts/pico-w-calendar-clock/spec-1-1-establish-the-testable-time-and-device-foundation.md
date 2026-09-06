---
title: 'Establish the testable time and device foundation'
type: 'feature'
created: '2026-09-06'
status: 'in-review'
baseline_revision: 'b9018dcd86966a3b5a98e5b11b16e3e02a90c1ec'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-1-context.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Firmware is a monolithic `main.py` TFT splash with no `src/` tree, no pure time/trust model, and no host tests—so clock behavior cannot be verified before Pico-only APIs are involved.

**Approach:** Introduce the approved `src/` substrate (config, pure time model/service, device display extraction), thin `main.py` to composition/fatal boot that still shows the existing splash, and add CPython pytest coverage for UTC→local snapshots and cold-boot unsynced absence.

## Boundaries & Constraints

**Always:**
- Preserve SPI0 pins GP16–GP21, 40 MHz mode 0, 320×240 landscape, and `MADCTL 0xA8` exactly as in `docs/hardware_configuration.md`.
- Pure modules under `src/time/` (and any pure helpers they use) must import under CPython with no `machine`, `network`, `ntptime`, or `src.device` imports.
- Store/sync wall time as UTC; local snapshots use fixed UTC+07:00 (no DST). `DateTime` fields: `year`, `month`, `day`, `weekday`, `hour`, `minute`, `second`. `TimeSnapshot`: `utc`/`local` as `DateTime | None`, `trust` as `synced|unsynced`, `sync_age_ms` as `int | None`.
- Non-secret defaults live as named constants in `src/config.py`. Root `.gitignore` excludes `/secrets.py`; commit only value-free `secrets.example.py`.
- Deploy-relative paths: keep `main.py` + `src/` layout so device imports match host tests.

**Never:**
- Do not implement Clock/Calendar renderers, App loop, network worker/NTP, or real `machine.RTC` `ClockPort` adapter (stories 1.2–1.5).
- Do not change hardware pin assignments or MADCTL.
- Do not put credentials in `src/config.py` or invent on-device behavior claims from host runs.
- Do not replace the splash baseline with a new UI in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid UTC → local | UTC `DateTime` + trust `synced` + age ms | Snapshot `local` = UTC+7 (date/time/weekday adjusted); trust/age preserved | No error expected |
| UTC near day boundary | UTC 16:30:00 (local crosses midnight) | Local date advances; weekday rolls correctly | No error expected |
| Cold boot / no valid time | No UTC available; RTC not yet valid | `utc`/`local`/`sync_age_ms` absent (`None`); trust `unsynced`; calendar entry forbidden | No crash; pure API returns absent snapshot |
| Unsynced with known UTC | Valid UTC + trust `unsynced` + age | Local derived; trust stays `unsynced`; calendar entry allowed once `local` exists | No error expected |
| Pure import surface | `import src.time.model` / `service` under CPython | Succeeds; modules do not import device/MicroPython-only APIs | Import failure = test fail |

</intent-contract>

## Code Map

- `main.py` -- Brownfield TFT splash + SPI bring-up; become composition/fatal-boot only; keep splash behavior via extracted display helpers.
- `docs/hardware_configuration.md` -- Read-only pin/SPI/MADCTL source of truth (GP16–21, 40 MHz, `0xA8`).
- `src/config.py` -- Create: named constants for pins, screen size, SPI baud, MADCTL, palette seeds, sync/dwell/retry defaults (no secrets).
- `src/device/display/` -- Create: move `ILI9341`, font glyphs, `color565`, splash drawing from `main.py` (hardware-bound; may import `machine`).
- `src/time/model.py` -- Create: `DateTime`, trust constants, `TimeSnapshot`, `calendar_entry_allowed(snapshot)` (true iff `local` is not `None`).
- `src/time/service.py` -- Create: pure `utc_to_local`, `make_snapshot(...)` / equivalent; no device imports; accept injected validity/trust/age inputs.
- `src/time/__init__.py`, `src/__init__.py`, `src/device/__init__.py`, `src/device/display/__init__.py` -- Package markers as needed for MicroPython/CPython imports.
- `secrets.example.py` -- Create value-free Wi-Fi placeholder keys only.
- `.gitignore` -- Ensure `/secrets.py` is ignored (add if missing).
- `tests/test_time_snapshot.py` (or split modules) -- Host tests for I/O matrix + import purity.
- `pyproject.toml` -- Create minimal pytest/`requires-python` so `uv run pytest` works (no project tooling yet).
- `_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-1-context.md` -- Epic constraints already distilled; do not re-open epic scope.

## Tasks & Acceptance

**Execution:**
- `pyproject.toml` -- Add minimal host test project metadata (pytest dep, python >=3.11) -- enables `uv run pytest`.
- `.gitignore` -- Ensure `/secrets.py` is ignored -- AD-9 credential boundary.
- `secrets.example.py` -- Add value-free example keys only -- documents device-local secrets shape.
- `src/config.py` -- Add named non-secret defaults (pins, display, timing) sourced from docs/current `main.py` -- single config ownership.
- `src/device/display/*.py` -- Extract TFT driver, font, splash helpers from `main.py` without changing pins/MADCTL -- establishes device boundary.
- `main.py` -- Reduce to composition + fatal boot that constructs SPI/display and shows existing splash -- AD-1 shell.
- `src/time/model.py` -- Define `DateTime`, trust values, `TimeSnapshot`, calendar-entry gate -- AD-3 surface.
- `src/time/service.py` -- Pure UTC→local (+7) and snapshot construction for valid and absent cases -- AD-4/AD-10.
- `tests/test_time_*.py` -- Cover I/O matrix scenarios and assert pure modules import without device deps -- host verification.

**Acceptance Criteria:**
- Given existing TFT bring-up and approved layout, when the substrate is introduced, then `main.py` is only composition/fatal boot and reusable code lives under `src/` boundaries while splash still initializes the same pins/MADCTL.
- Given pure time modules, when CPython imports them, then they load without `machine`/`network`/`ntptime`/device-adapter imports, and `uv run pytest` passes.
- Given a UTC `DateTime`, when a pure snapshot is derived, then local is UTC+07:00 with named fields and trust/sync-age state as defined.
- Given no valid time yet, when a snapshot is requested, then date-time and age fields are absent, trust is unsynced, and calendar entry is not permitted.
- Given checked-in configuration, when defaults are needed, then they are named constants in `src/config.py`, credentials stay out, `/secrets.py` is ignored, and `secrets.example.py` has no secret values.

## Spec Change Log

## Review Triage Log

## Design Notes

- Prefer simple integer UTC→local conversion (add 7 hours with carry into day/month/year/weekday) rather than `zoneinfo` so the same module runs on MicroPython.
- `ClockPort` / RTC adapter and App loop stay out of scope; tests inject validity/trust/age into pure snapshot helpers.
- Keep splash pixel behavior and colors functionally equivalent after extraction; palette product tokens may be added to `config.py` for later stories without requiring splash redesign now.

## Verification

**Commands:**
- `uv run pytest` -- expected: all new host tests pass
- `uv run python -c "from src.time import model, service"` -- expected: imports succeed on host

**Manual checks (if no CLI):**
- Flash/deploy is out of scope for this environment; do not claim on-device splash observation—user verifies after copy if desired.
