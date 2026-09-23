# Deployment Record — Mobile Settings Viewport

## Pre-deployment firmware and native-auth record

- Target: Raspberry Pi Pico W at `/dev/cu.usbmodem1101`.
- Target firmware observed over USB: MicroPython 1.20.0, RP2040, `_mpy=4358`.
- Compiler pinned for this deployment: `mpy-cross==1.20.0` (`uv tool run --from mpy-cross==1.20.0 mpy-cross --version`); output format mpy v6.1.
- Native verifier source: `src/provisioning/native_kdf.py`; deploy staging compiles it for ARMv6-M native emit per `tools/deploy.py`.
- Reproducible native module command: `uv tool run --from mpy-cross==1.20.0 mpy-cross -march=armv6m src/provisioning/native_kdf.py -X emit=native -o native_kdf.mpy`.
- Existing flashed-device auth evidence is recorded in `spec-memory-footprint-fixes.md` (2026-09-10): Pico login succeeded with v2/500-round verifier and authenticated `/settings` returned 200. Existing native-auth/compiler context is in `native-auth-precompile-station-http-fix.md`.
- Settings data preservation: `tools/deploy.py` overlays source files and does not clear `.settings-v1`; it removes/replaces only `src/` before copying firmware.

## Deployment

- Result: completed successfully; `uv run tools/deploy.py` memory gate passed and deployed build to `/dev/cu.usbmodem1101` using `mpy-cross==1.20.0`.
- Board check after reset: still reports MicroPython 1.20.0 (`_mpy=4358`); `/src/device/web/page_settings_content.mpy` and `/src/provisioning/native_kdf.mpy` are present.
- Settings preservation check: `.settings-v1` remains on device.
- Scope: no device/browser request or visual phone check performed; deployed module presence does not prove mobile rendering or authenticated route availability.
