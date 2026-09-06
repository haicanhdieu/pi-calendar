---
title: 'Establish the testable time and device foundation'
type: 'feature'
created: '2026-09-06'
status: 'done'
baseline_revision: 'b9018dcd86966a3b5a98e5b11b16e3e02a90c1ec'
review_loop_iteration: 0
followup_review_recommended: true
context:
  - '{project-root}/_bmad-output/implementation-artifacts/pico-w-calendar-clock/epic-1-context.md'
warnings: []
deferred:
  - summary: >-
      Weekday index convention (Monday = 0) is assumed by host tests but not documented on DateTime.
    evidence: |-
      Architecture/UX describe Monday-start month grids; DateTime.weekday is an opaque int preserved by utc_to_local arithmetic. Documenting or enforcing Monday=0 belongs with calendar/RTC adapter stories, not this foundation extract.
    location: >-
      src/time/model.py
    severity: low
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

### 2026-09-06 — Review pass
- verdicts: 24 findings — high 0, medium 5, low 16, false 3, maybe-false 0
- findings:
  - `[low]` `[reject]` Spec I/O matrix cites UTC 16:30 as local midnight cross — matrix text is wrong (16:30→23:30 same day); tests already cover 16:30 same-day and 17:00 midnight. Rejected because the fix is editing this build's `<intent-contract>`.
  - `[low]` `[defer]` Monday = weekday 0 undocumented on `DateTime` — real convention risk for later calendar/RTC work; deferred to those stories (see frontmatter `deferred`).
  - `[low]` `[patch]` `TimeSnapshot` docstring claimed immutable without freeze — removed the false "Immutable" word from `src/time/model.py`.
  - `[medium]` `[patch]` Import-purity AST helper missed `import src.device.foo` (and related deep paths) — `_imported_roots` now records every dotted prefix so `src.device` is hit. (`import src.device` was already caught; claim partially overstated.)
  - `[low]` `[reject]` `make_snapshot(None, trust, age)` discards trust/age — docstring already documents force-to-unsynced; no production callers yet; signature change would add public surface.
  - `[low]` `[patch]` Non-leap Feb 28→Mar 1 under +7 untested — added `test_non_leap_feb_rollover_to_march`.
  - `[low]` `[reject]` `src/device/display/__init__.py` eagerly imports `ILI9341`/`machine` — device package is allowed to bind MicroPython; intent does not require host-loadable display package imports.
  - `[low]` `[reject]` Epic context grammar ("Deliver a always-on") — cosmetic planning prose; not product code.
  - `[medium]` `[patch]` No host lock that `src/config.py` pin/SPI/MADCTL still match hardware docs — added `tests/test_config_hardware_defaults.py`.
  - `[low]` `[reject]` `utc_to_local` negative-hour branch untested — product offset is fixed +7; path unused in everyday use.
  - `[low]` `[reject]` Invalid trust strings accepted by `make_snapshot` — only injected by callers; no demonstrated bad producer in this story; validation would guard undemonstrated state.
  - `[low]` `[reject]` Negative `sync_age_ms` accepted — same as trust: injected-only, no demonstrated producer.
  - `[false]` `[reject]` `calendar_entry_allowed(None)` AttributeError — cold-boot path returns a `TimeSnapshot` with `local is None`, not a null snapshot object; None is not a demonstrated input.
  - `[low]` `[reject]` Impossible calendar dates pass through `utc_to_local` — date validity belongs with future RTC/NTP adapters; not required by this story's intent.
  - `[medium]` `[patch]` Purity AST gap for `from src import device` — fixed with the same `_imported_roots` prefix/`ImportFrom` name joining as the deep-import hole (grouped with blind-hunter AST finding).
  - `[low]` `[reject]` Spec matrix midnight-rollover claim at UTC 16:30 does not hold — same as first finding; reject (would edit intent-contract).
  - `[medium]` `[patch]` Hardware pin/SPI/MADCTL config unguarded after extraction (verification-gap, pre-verified) — added `tests/test_config_hardware_defaults.py` asserting docs values.
  - `[low]` `[reject]` Spec matrix UTC 16:30 Other finding — same reject as matrix-edit findings.
  - `[false]` `[reject]` Intent cold-boot "RTC not yet valid" vs `utc is None` encoding — correct Approach reading; RTC adapter explicitly out of scope.
  - `[false]` `[reject]` Calendar entry as product gate vs pure `calendar_entry_allowed` — same semantic on the allowed pure-helper surface; Calendar renderer excluded by intent.
  - `[low]` `[reject]` Day-boundary matrix clock vs 17:00 tests — same intent-contract edit reject.
  - `[medium]` `[patch]` Splash/hardware continuity untested on host — covered by the new config hardware-defaults test for pins/SPI/MADCTL (splash pixels remain device-only by intent).
  - `[low]` `[reject]` Secrets boundary files untested — `/secrets.py` gitignore and value-free `secrets.example.py` are present; silent secret-value regression is unlikely vs pin drift; no extra assertion added.
  - `[low]` `[reject]` Fatal boot composition untested — firmware cannot run here; intent forbids inventing on-device boot claims.

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

## Auto Run Result

Status: done

Summary: Story 1.1 foundation is complete — `src/` substrate (config, pure time model/service, device display extract), thinned splash `main.py`, host pytest for the time I/O matrix plus hardware config lock. Review pass patched import-purity AST holes, immutability docstring overclaim, non-leap February coverage, and TFT pin/SPI/MADCTL host assertions.

Files changed:
- `main.py` — composition/fatal-boot shell; SPI + splash via `src`
- `src/config.py` — named non-secret pin/SPI/MADCTL/timing defaults
- `src/time/model.py` — `DateTime`, `TimeSnapshot`, trust constants, calendar gate
- `src/time/service.py` — pure `utc_to_local` / `make_snapshot`
- `src/device/display/*` — ILI9341, font, splash extracted from brownfield `main`
- `secrets.example.py`, `.gitignore`, `pyproject.toml`, `uv.lock` — secrets boundary + host pytest
- `tests/test_time_snapshot.py` — I/O matrix, import purity (AST prefixes fixed)
- `tests/test_config_hardware_defaults.py` — locks config pins/SPI/MADCTL to hardware docs
- `_bmad-output/.../epic-1-context.md`, this spec — planning/review artifacts

Review findings: patches applied (medium×2 groups: AST purity + hardware config lock; low×2: docstring + non-leap test); 1 deferred (weekday Monday=0 docs); rejected: matrix 16:30 intent-contract edits, make_snapshot footgun, eager display `machine` import, epic grammar, negative-offset test gap, trust/age/date validation, calendar_entry(None), secrets file assertion, on-device boot observation, and false RTC/calendar surface mismatches.

Follow-up review recommendation: true — two medium patches landed (purity AST prefix logic; hardware defaults test). Unverified residual risk: a follow-up pass should re-confirm those two gates still fail closed on a deliberate `src.device` import smuggle and a pin/MADCTL typo.

Verification:
- `uv run pytest` — 11 passed
- `uv run python -c "from src.time import model, service"` — succeeded

Residual risks: splash pixel continuity and fatal-boot LED path are device-only (not observed here); weekday indexing convention deferred; intent-contract still mislabels UTC 16:30 as midnight cross (tests correct).

Blocking condition: none

Note: git commit skipped by orchestrator policy for this unattended pass; working tree remains dirty for the parent orchestrator to commit.
