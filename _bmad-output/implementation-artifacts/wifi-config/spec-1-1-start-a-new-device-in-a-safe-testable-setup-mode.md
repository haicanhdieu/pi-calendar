---
title: '1.1 Start a new Device in a safe, testable setup mode'
type: 'feature'
created: '2026-09-06'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
baseline_revision: 'df557d503e67e14b591c0ffd8880fb57cc2962e1'
context:
  - '{project-root}/_bmad-output/implementation-artifacts/wifi-config/epic-1-context.md'
warnings: []
deferred:
  - summary: >-
      Open AP activation does not set ifconfig gateway 192.168.4.1; status event
      reports that IP without applying it on the radio.
    evidence: |-
      _tick_setup_ap only config(essid, security=0)+active(True). MicroPython often
      defaults the AP gateway, but it is unverified on-device; story 1.3/flash proof
      should confirm or set ifconfig explicitly.
    location: >-
      src/device/network/coordinator.py
    severity: medium
  - summary: >-
      If bak→current rename fails transiently, load latches unconfigured for the
      process lifetime even though .bak may still be recoverable.
    evidence: |-
      load() sets _loaded True when restore returns False. Settled by a retry path
      that leaves _loaded false while bak remains valid, or by on-device rename
      reliability evidence.
    location: >-
      src/device/settings_store.py
    severity: medium (unverified)
  - summary: >-
      urandom/salt derive raising ValueError may escape commit as an unnamed
      error instead of SettingsCommitError.
    evidence: |-
      Settle with a FakeFS/urandom that raises ValueError during commit; if the
      exception escapes unwrapped, map it to COMMIT_VALIDATE_FAIL.
    location: >-
      src/device/settings_store.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A new or invalidly configured Device has no safe boot path into setup: credentials still come from gitignored `secrets.py`, and there is no SettingsStore, SETUP_AP mode, or host-testable provisioning validation.

**Approach:** Add a pure settings/validation layer plus SettingsStore persistence, and evolve NetworkCoordinator so boot with an unusable settings record enters SETUP_AP, owns WLAN/sockets, activates open `PiCalendar-Setup`, and emits typed NetworkEvents—without mutating App or drawing the TFT.

## Boundaries & Constraints

**Always:** SettingsStore is the only reader/writer of the ignored record; invalid/unsupported records are preserved and treated as unconfigured; Admin password is stored only as salted PBKDF2-HMAC-SHA256 verifier; provisioning validation and transition policy import no `machine`, `network`, or socket modules; coordinator alone owns WLAN/socket objects and emits typed events; keep `coordinator.tick()` then `app.step()` cadence; inject FS/WLAN/entropy/ticks for host tests.

**Never:** HTTP Setup pages, candidate join, scan UI, TFT setup/IP overlay, three-failure STA fallback, session/auth (those are 1.2/1.3/Epic 2); delete or overwrite invalid settings on boot; log or return Admin plaintext; change GPIO/SPI/TFT pins; claim on-device AP proof from host tests; pull coordinator through `src.device.network` package `__init__` (keep host surface = mailbox only).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Absent record | No current/bak settings file | Validation → unconfigured; coordinator → `SETUP_AP`; open AP `PiCalendar-Setup` | No crash |
| Unreadable / malformed / incomplete / unsupported version | Corrupt or wrong-schema bytes on disk | Unconfigured; enter `SETUP_AP`; original bytes preserved | No delete/overwrite of invalid current |
| Valid complete record | Canonical `settings_version: 1` object | Store returns configured settings; coordinator does **not** enter `SETUP_AP` for that boot decision | Keep existing mailbox NTP path usable until later stories own STA join |
| Commit success | Valid candidate fields + Admin password | Atomic tmp→bak→current; salt+verifier stored; no plaintext Admin on disk | `os.sync` when available |
| Commit mid-failure | FS errors during rename/sync | Prior good current/bak recoverable per AD-3 restore/quarantine rules | Named failure; no partial plaintext Admin |
| SETUP_AP tick | Mode `SETUP_AP`, fake WLAN | Activates open AP SSID `PiCalendar-Setup`; emits typed setup-status event; no App/TFT calls | WLAN errors → named event, no crash |
| Pure import | Import provisioning + validation under CPython | No `machine`/`network`/socket imports | AST or import smoke in pytest |

</intent-contract>

## Code Map

- `main.py:51–74` -- Composition root: Mailbox + NetworkCoordinator + App loop; wire SettingsStore and boot mode here without blocking `sleep_ms(10)` cadence.
- `src/device/network/coordinator.py:21–114` -- Extend with modes `BOOT`/`SETUP_AP` (and stubs for later STA modes); today secrets-gated STA+NTP only; keep injection of `wlan`/`ticks_module`; add settings_store + event sink; never draw TFT or mutate App.
- `src/device/network/mailbox.py` + `__init__.py` -- Reuse pure mailbox for NTP path; do **not** re-export coordinator from package root; add `models.py` for modes/events beside coordinator.
- `src/app.py:131–171` -- Read-only for this story: still consumes mailbox SyncResult; do not add NetworkEvent TFT overlay yet (story 1.3).
- `src/credentials.py` + `secrets.py` -- Legacy Wi-Fi soft-check; retain for valid-settings/legacy NTP until SettingsStore owns STA credentials in later stories; do not deploy as long-term provisioning source.
- `src/ticks.py` -- Wrap-safe deadlines for any timed SETUP_AP work.
- `src/config.py` -- Non-secret constants only (AP SSID string, settings basename, PBKDF2 iteration count may live here or as store constants—no secrets).
- `.gitignore:16–20` -- Add ignore rules for `.settings-v1`, `.settings-v1.tmp`, `.settings-v1.bak`, `.settings-v1.rejected`.
- **Create:** `src/device/settings_store.py` -- Sole FS boundary; validate-as-whole; AD-3 atomic commit + boot restore/quarantine; derive/store verifier.
- **Create:** `src/provisioning/` -- Pure record validation + PBKDF2 verifier helpers (no device imports).
- **Create:** `src/device/network/models.py` -- Mode constants + typed NetworkEvent values for setup-status (and placeholders later stories need).
- **Create:** `tests/test_settings_store.py`, `tests/test_provisioning_validation.py`, `tests/test_setup_ap_coordinator.py` -- Fakes for FS/WLAN/entropy; cover I/O matrix; AST import hygiene for pure modules.
- `tests/test_network_coordinator.py` -- Reuse FakeWlan/FakeTicks patterns; keep existing NTP tests green when not in SETUP_AP.
- Read-only planning distillate: `_bmad-output/implementation-artifacts/wifi-config/epic-1-context.md` (AD-2/AD-3 rules).

## Tasks & Acceptance

**Execution:**
- `src/provisioning/validation.py` (+ package `__init__`) -- Implement whole-record validation for `settings_version: 1` field rules (SSID/password lengths, verifier hex lengths, `color_scheme: "forest-amber"`, `admin_verifier_version`); treat absent/malformed/unsupported as unconfigured without mutation -- host-safe foundation for boot decisions.
- `src/provisioning/verifier.py` -- PBKDF2-HMAC-SHA256 (20_000 iters, 16-byte salt, 32-byte digest), hex encoding, constant-time compare helper; no plaintext retention -- satisfies salted Admin verifier requirement under CPython.
- `src/device/settings_store.py` -- Load/validate via provisioning; current file `.settings-v1`; AD-3 tmp/bak/rejected atomic commit + boot restore; `commit` accepts wifi fields + admin password (or precomputed verifier in tests) and never writes plaintext Admin; inject open/replace/rename/sync/urandom -- sole persistence boundary.
- `src/device/network/models.py` -- Define mode enum/constants and NetworkEvent types used by SETUP_AP status emission -- typed events instead of App mutation.
- `src/device/network/coordinator.py` -- On construct/boot: read SettingsStore; unconfigured → `SETUP_AP`; tick activates open AP `PiCalendar-Setup` (injected WLAN), emits NetworkEvent to an injected sink/list; configured → keep existing mailbox NTP behavior; do not import App or display -- story SETUP_AP ownership AC.
- `main.py` -- Construct SettingsStore + event sink; pass into NetworkCoordinator; preserve tick/step loop -- device boots into testable setup path when unconfigured.
- `.gitignore` -- Ignore `.settings-v1` and `.settings-v1.{tmp,bak,rejected}` -- secrets stay untracked.
- `tests/test_provisioning_validation.py`, `tests/test_settings_store.py`, `tests/test_setup_ap_coordinator.py` -- Cover I/O matrix + AST no `machine`/`network`/socket in pure modules; FakeWlan asserts open AP SSID; existing NTP coordinator tests still pass.

**Acceptance Criteria:**
- Given an absent, unreadable, malformed, unsupported, or incomplete settings record, when the Device boots / coordinator starts, then validation treats it as unconfigured and the coordinator enters `SETUP_AP` without deleting the record or crashing.
- Given a Device in `SETUP_AP`, when the coordinator is ticked from the main loop, then it alone owns Pico WLAN/socket objects, activates open `PiCalendar-Setup`, and emits typed events rather than mutating `App` or drawing the TFT.
- Given persisted settings, when they are read or committed, then only `SettingsStore` accesses the ignored versioned record, validates it as a whole, performs the AD-3 atomic replacement protocol, and stores a salted one-way Admin verifier rather than plaintext Admin password.
- Given provisioning validation, SETUP_AP transition policy, and settings logic, when imported under CPython, then they have no `machine`, `network`, or socket imports and `uv run pytest` exercises them with fakes.

## Spec Change Log

## Review Triage Log

### 2026-09-06 — Review pass
- verdicts: 27 findings — high 0, medium 17, low 3, false 5, maybe-false 2
- findings:
  - `[medium]` `[patch]` Duplicate AP/SSID/gateway/iteration constants across config vs models/verifier/store — unified consumers on `src/config.py` values.
  - `[false]` `[reject]` `MODE_BOOT` unused at runtime — placeholder for later STA stories; boot resolves via `boot_mode_for_settings` by design.
  - `[medium]` `[defer]` AP tick never applies ifconfig `192.168.4.1` while status event claims that IP — deferred to on-device proof / later story.
  - `[medium]` `[patch]` SETUP_AP boot still called `report_time_source_failure` with credentials wording — gated so SETUP_AP no longer reports that fault.
  - `[false]` `[reject]` Valid settings still need `secrets.py` for NTP — intentional transitional path until 1.2/1.3 own STA join from the store.
  - `[low]` `[patch]` Misleading `test_settings_store_is_only_persistence_boundary_for_boot` — replaced to assert real SettingsStore boot configuration.
  - `[medium]` `[patch]` Incomplete/unsupported/bak-restore coordinator coverage thin — factory+absent-store and real-store boot tests added; bak restore remains covered in settings_store tests.
  - `[medium]` `[patch]` AP activation retry after transient failure untested — fail-once FakeApWlan test added.
  - `[medium]` `[patch]` `wifi_ssid` allowed embedded NUL — validation now rejects NUL in SSID.
  - `[false]` `[reject]` Empty triage log / stale Code Map in-spec — process artifact during review; not a product defect (fix would be editing this build's spec for its own sake).
  - `[medium]` `[patch]` Status emit after `_setup_ap_active=True` can lose status — latch only after successful status emit.
  - `[medium]` `[patch]` Error sink raise can escape `tick` — error emit wrapped in try/except.
  - `[low]` `[reject]` Non-callable/non-list event_sink — everyday sink is list/callable from main; invalid sinks hit ap_fail path; not worth extra type surface.
  - `[medium]` `[patch]` Sync fail after bak rename can leave SETUP_AP while valid current exists — restore treats post-rename sync failure as success when current validates.
  - `[maybe-false]` `[defer]` Bak rename failure latches unconfigured without retry — would be medium if true; needs explicit retry-or-evidence decision.
  - `[maybe-false]` `[defer]` urandom/salt derive raising ValueError may escape as unnamed commit failure — settle by injecting failing urandom in commit tests; if true, wrap as `COMMIT_VALIDATE_FAIL`.
  - `[medium]` `[patch]` Half of salt/verifier pair silently ignored — now `COMMIT_VALIDATE_FAIL` when exactly one provided.
  - `[medium]` `[patch]` JSON `true` accepted as `settings_version` via `True == 1` — require `type(version) is int`.
  - `[medium]` `[patch]` SETUP_AP framed as missing Wi-Fi credentials (edge-case layer duplicate of BH) — same main.py gate fix.
  - `[false]` `[reject]` Claim that corrupt current always yields SETUP_AP ignores bak restore — AD-3 restore is correct; matrix wording is simplified, not a code defect.
  - `[false]` `[reject]` Quarantine rename vs Never-delete — `.rejected` preserves evidence per AD-3; not a delete.
  - `[medium]` `[patch]` `main.py` SETUP_AP `sync_enabled` gate untested — added `ntp_sync_enabled` helper + host tests.
  - `[medium]` `[patch]` `main.py` SettingsStore injection untested — added `make_settings_coordinator` factory used by main + absent-store test.
  - `[medium]` `[patch]` AP retry untested (verification-gap duplicate) — same fail-once test.
  - `[medium]` `[patch]` Commit sync-failure named error untested — `COMMIT_SYNC_FAIL` test added.
  - `[low]` `[patch]` Verification-gap other: misleading boundary test — same fix as BH.
  - `[medium]` `[patch]` Verification-gap other: duplicate config constants — same unify fix as BH.

## Design Notes

**Current record name:** Use `.settings-v1` as the live record so sidecars `.settings-v1.tmp` / `.settings-v1.bak` / `.settings-v1.rejected` match AD-3.

**Configured boot in 1.1:** A valid record must not enter `SETUP_AP`. Station join from stored Wi-Fi and HTTP setup remain later stories; keep the existing secrets+mailbox NTP path functional for configured/legacy clocks so the calendar loop still syncs in host tests and current flashes.

**Event sink:** Inject a simple callable/list on the coordinator for NetworkEvents (App wiring of overlays is story 1.3). Golden SETUP_AP event should carry mode/SSID/`192.168.4.1` status fields without display calls.

**Open AP:** `wlan.config(essid="PiCalendar-Setup", security=0)` (or platform equivalent) + `active(True)` on AP interface; inject AP WLAN separately from STA if the fake needs both—host tests only assert the contract, not Pico coexistence.

## Verification

**Commands:**
- `uv run pytest` -- expected: all tests pass, including new settings/SETUP_AP coverage and existing network/app tests
- `uv run pytest tests/test_provisioning_validation.py tests/test_settings_store.py tests/test_setup_ap_coordinator.py -q` -- expected: I/O matrix cases green

**Manual checks (if no CLI):**
- After flash with no `.settings-v1`, device should present open AP `PiCalendar-Setup` (user-observed; do not claim from host).

## Auto Run Result

Status: done

**Summary:** Story 1.1 delivers SettingsStore + pure provisioning validation/PBKDF2, and NetworkCoordinator SETUP_AP boot that activates open `PiCalendar-Setup` and emits typed NetworkEvents without mutating App or drawing the TFT. Review patches hardened emit latching, validation, restore/sync, and host-tested composition helpers.

**Files changed:**
- `src/provisioning/` — pure validation + verifier
- `src/device/settings_store.py` — AD-3 atomic settings I/O
- `src/device/network/models.py` — modes/events + boot/sync helpers
- `src/device/network/coordinator.py` — SETUP_AP ownership path
- `main.py` / `src/config.py` / `.gitignore` — composition, constants, ignore rules
- `tests/test_provisioning_validation.py`, `tests/test_settings_store.py`, `tests/test_setup_ap_coordinator.py` — matrix coverage
- `_bmad-output/implementation-artifacts/wifi-config/epic-1-context.md`, `spec-1-1-...md` — planning artifacts

**Review:** Patched many medium items (sync gate, factory wiring, AP retry, sync-fail commit, emit latch, validation, restore, credentials message, constants). Deferred: AP ifconfig gateway application; bak-rename latch retry. Rejected: MODE_BOOT placeholder, secrets transitional path, claim mismatches vs AD-3, intent-alignment scope notes, invalid-sink type surface.

**Follow-up review recommended:** true — risk: post-review patches to emit ordering and bak-restore sync handling were not re-reviewed by a second hunter pass.

**Verification:** `uv run pytest --ignore=.agents --ignore=.claude` → 194 passed. Focused provisioning/settings/SETUP_AP suites green after patches.

**Residual risks:** On-device open AP / gateway behavior unproven here; legacy `secrets.py` still required for NTP when settings are configured until later stories; deferred bak-rename latch and ifconfig items above.
