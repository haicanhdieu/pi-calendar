# Lunar precision fix: Pico deployment evidence

Date: 2026-10-10. Target: `/dev/cu.usbmodem101`, Raspberry Pi Pico W / RP2040.

## Deployment

- Board reports MicroPython 1.20.0, `_mpy=4358`.
- Compiler: `mpy-cross` 1.20.0, emitting mpy v6.1.
- Command: `MPY_CROSS=/Users/minhtrucnguyen/.local/share/uv/tools/mpy-cross/bin/mpy-cross uv run tools/deploy.py --port /dev/cu.usbmodem101`.
- Deployment exited successfully; compiled-size and host heap simulation gates passed.
- Clock resident compiled size: 49,234 bytes / 50,500-byte budget.
- Native authentication module built by existing deployment tooling with `-march=armv6m -X emit=native`; source remains `src/provisioning/native_kdf.py`. Pinned context and previous authentication evidence: `../../../implementation-artifacts/wifi-config/native-auth-precompile-station-http-fix.md` and `../../../implementation-artifacts/wifi-config/deployment-mobile-settings-viewport.md`.
- Device checks confirmed `.settings-v1` and `src/provisioning/native_kdf.mpy` remain present. No settings reset performed.

## Observed device conversion

Executed `gregorian_to_lunar` from deployed module over USB:

```text
lunar_vectors [(9, (29, 8, False)), (10, (1, 9, False)), (11, (2, 9, False))]
lunar_device_check_ok
```

These are Gregorian October 9–11, 2026, converted in Vietnam UTC+7.
Assertions passed for October 10 → `(1, 9, False)` and July 25, 2025 → `(1, 6, True)`.
Board reset after checks to resume firmware.

## Host evidence and limits

- Before fix, binary32 simulation reproduced October 10 → `(30, 8, False)`.
- After fix, focused lunar/clock tests: 55 passed. Full host suite: 702 passed.
- Physical display rendering and post-reset application boot logs were not observed. Device conversion checks establish numerical correctness for these vectors, not browser, WLAN, or authentication behavior.
