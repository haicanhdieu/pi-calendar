# Proof 1.3 — STA/AP coexistence and Device address visibility

**Story:** 1-3-recover-wi-fi-automatically-and-show-the-device-address  
**Spec:** `spec-1-3-recover-wi-fi-automatically-and-show-the-device-address.md`  
**Target:** Raspberry Pi Pico W / MicroPython **1.29**

This artifact **separates** host protocol verification from flashed-device
observation. Device rows stay **empty / PENDING** until a human flashes the
Pico W and records what they see. Do **not** invent on-device results from
host pytest. An **unsupported** STA/AP coexistence result **blocks** the
browser-terminal-response claim from story 1.2 — redesign rather than silently
changing the handshake.

---

## Host Results

| Check | Command / scope | Result | Notes |
|-------|-----------------|--------|-------|
| Pytest (recovery + overlay + prior suites) | `uv run pytest --ignore=.agents --ignore=.claude` | PASS | 232 collected (2026-09-06 post-review fixes; focused suites green) |
| Failure-count / boot-mode purity | `tests/test_station_recover.py` | PASS | No `machine`/`network`/`ntptime` in `models.py` |
| Overlay reduction (App sole writer) | `tests/test_app_network_overlay.py` | PASS | Setup continuous; IP ≥10s wrap-safe; Calendar + invalidate |

### Host run log

```
2026-09-06 post-review fixes
uv run pytest --collect-only → 232 tests collected
Focused: test_app_network_overlay + test_station_recover + coordinator suites → 50 passed
```

---

## Device Observation (user flash required)

**Flash procedure:**

1. Deploy `main.py` + `src/` to the Pico W (product boot; `NETWORK_PROOF_MODE = False`).
2. Prefer a build that includes a complete `.settings-v1` **or** exercise Setup join once so STA credentials exist.
3. Open serial console; note firmware version (expect MicroPython Pico W **1.29.x**).
4. Walk each scenario below. Record **PASS / FAIL / UNSUPPORTED / SKIPPED** and operator notes.
5. If coexistence is **UNSUPPORTED**, stop — do **not** claim story 1.2 browser terminal response as proven on this firmware; open a redesign spike instead.

| Scenario | What to observe | Result | Operator notes |
|----------|-----------------|--------|----------------|
| STA/AP coexistence | While Setup AP `PiCalendar-Setup` is up, STA association can progress (or document firmware limitation) | | |
| Gateway `192.168.4.1` | Phone on Setup AP reaches `http://192.168.4.1/` | | |
| Scan during AP | Setup SSID list populates (or Rescan works) while AP remains usable | | |
| Bounded socket fairness | Clock/calendar keep updating; HTTP remains responsive under light load (no multi-second freeze) | | |
| Browser terminal responses | Connect success/failure HTML completes on the phone before AP teardown (1.2 claim) | | **Blocked if coexistence UNSUPPORTED** |
| Flash commits | Settings survive reboot; configured Device retries home Wi-Fi | | |
| TFT Setup overlay | Continuous `PiCalendar-Setup` + `192.168.4.1` while in Setup AP | | |
| TFT station IP overlay | After successful STA connect/reconnect, assigned IPv4 visible ≥10s | | |
| Three-failure fallback | After three consecutive terminal STA fails, Device re-enters Setup AP without reflash | | |

### Device run log

```
Date:
Pico W / MicroPython version:
Transport / deploy tool:
Serial port:

(paste serial or handwritten notes after flash — leave empty until then)
```

### Gate decision

| Gate | Status | Notes |
|------|--------|-------|
| Coexistence supports 1.2 browser terminal claim | PENDING | Set PASS only after coexistence + browser rows are PASS on 1.29 |
| Story 1.3 close (host + checklist ready) | PENDING | Host green + empty device rows ready for human fill is enough to enter review; device fill closes flash proof |

---

## Commit / binary note

Record the git commit (or archive hash) flashed when filling device rows:

```
flash_commit:
```
