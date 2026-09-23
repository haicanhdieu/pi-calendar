"""Deploy main.py/src/secrets.py to a flashed Pico W, precompiling the
largest first-boot import chains to .mpy so MicroPython loads bytecode
instead of compiling source on-device (see docs/heap_budget.md).

A memory-budget gate runs first; see docs/heap_budget.md.

Usage:
    uv run tools/deploy.py --port /dev/cu.usbmodem1101
    MPY_CROSS=/path/to/mpy-cross uv run tools/deploy.py --port /dev/cu.usbmodem1101
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules whose on-device .py compile has been observed to raise MemoryError
# (setup-AP HTTP surface, the station-mode admin site, and the display/UI
# render path, which is the biggest single chunk of on-device compile cost).
# Ship these as precompiled .mpy; everything else deploys as plain .py.
PRECOMPILE = [
    "src/device/web/pages.py",
    "src/device/web/page_setup_content.py",
    "src/device/web/page_login_content.py",
    "src/device/web/page_settings_content.py",
    "src/device/web/http_parse.py",
    "src/device/web/server.py",
    "src/device/web/setup_pages.py",
    "src/device/web/setup_router.py",
    "src/device/web/router.py",
    "src/device/web/page_alert_editor.py",
    "src/device/web/alert_route.py",
    "src/device/web/alert_validation.py",
    "src/device/web/postpone_route.py",
    "src/device/web/settings_post.py",
    "src/provisioning/kdf_job.py",
    "src/provisioning/setup_kdf.py",
    "src/provisioning/constants.py",
    "src/provisioning/scan.py",
    "src/provisioning/validation.py",
    "src/provisioning/verifier.py",
    "src/provisioning/session.py",
    "src/ui/clock_view.py",
    "src/ui/calendar_view.py",
    "src/ui/compositor.py",
    "src/ui/components.py",
    "src/ui/display_port.py",
    "src/ui/view_state.py",
    "src/ui/settings_view.py",
    "src/ui/touch_state.py",
    "src/ui/touch_calibration.py",
    "src/app.py",
    "src/device/network/coordinator.py",
    "src/device/network/mailbox.py",
    "src/device/network/models.py",
    "src/device/network/worker.py",
    "src/device/network/ntp_ops.py",
    "src/device/display/font.py",
    "src/device/display/ili9341.py",
    "src/device/display/adapter.py",
    "src/device/display/bootstrap.py",
    "src/device/display/splash.py",
    "src/device/display/color.py",
    "src/device/clock_mode.py",
    "src/device/config_mode.py",
    "src/device/knock.py",
    "src/device/mode_flag.py",
    "src/alert/runtime.py",
    "src/alert/scheduler.py",
    "src/alert/terminal.py",
]

NATIVE_PRECOMPILE = {
    "src/provisioning/native_kdf.py": ("armv6m", "native"),
}


def find_mpy_cross():
    env = os.environ.get("MPY_CROSS")
    if env:
        return env
    found = shutil.which("mpy-cross")
    if found:
        return found
    raise SystemExit(
        "mpy-cross not found. Install the version matching the flashed "
        "firmware's sys.implementation._mpy (check via "
        "`mpremote connect <port> exec \"import sys; print(sys.implementation)\"`), "
        "e.g. `uv pip install mpy-cross==1.20.0` into a venv, then pass "
        "MPY_CROSS=/path/to/mpy-cross."
    )


def stage_tree(mpy_cross):
    staging = Path(tempfile.mkdtemp(prefix="pi-calendar-deploy-"))
    src_out = staging / "src"
    precompile_set = {ROOT / p for p in PRECOMPILE}

    for path in (ROOT / "src").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT / "src")
        if path in precompile_set:
            dest = (src_out / rel).with_suffix(".mpy")
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [mpy_cross, "-O3", str(path), "-o", str(dest)], check=True
            )
        elif str(path.relative_to(ROOT)) in NATIVE_PRECOMPILE:
            arch, emit = NATIVE_PRECOMPILE[str(path.relative_to(ROOT))]
            dest = (src_out / rel).with_suffix(".mpy")
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [mpy_cross, "-march=" + arch, str(path), "-X", "emit=" + emit, "-o", str(dest)],
                check=True,
            )
        else:
            dest = src_out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)

    return staging


def deploy(port, staging):
    def mpremote(*args):
        subprocess.run(["mpremote", "connect", port, *args], check=True)

    # Wipe the device's src/ first: mpremote fs cp only overlays matching
    # names, and a stale on-device .py shadows a freshly deployed .mpy of
    # the same module (MicroPython prefers .py), silently undoing the fix.
    subprocess.run(
        ["mpremote", "connect", port, "fs", "--recursive", "rm", ":src"],
        check=False,
    )
    mpremote("fs", "cp", "-r", str(staging / "src") + "/.", ":src")
    mpremote("fs", "cp", str(ROOT / "main.py"), ":main.py")
    if (ROOT / "secrets.py").exists():
        mpremote("fs", "cp", str(ROOT / "secrets.py"), ":secrets.py")
    mpremote("reset")


def run_memory_gate():
    """Check the memory budgets before touching the device.

    A build that exceeds them boots but cannot serve the settings page, and
    the only symptom on hardware is ``Empty reply from server`` -- expensive
    to diagnose and, before this gate existed, repeatedly shipped by accident.
    Catching it here costs about a second.
    """
    sys.path.insert(0, str(ROOT))
    from tools.hostsim.__main__ import main as gate_main

    print("Checking memory budgets (see docs/heap_budget.md)...")
    return gate_main([])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="mpremote serial port")
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Do not delete the staged tree (for inspection)",
    )
    parser.add_argument(
        "--skip-memory-gate",
        action="store_true",
        help=(
            "Deploy even if the memory budgets are exceeded. Only for "
            "deliberately flashing a diagnostic build."
        ),
    )
    args = parser.parse_args()

    if args.skip_memory_gate:
        print("WARNING: memory gate skipped; this build may not serve the "
              "settings page.")
    elif run_memory_gate() != 0:
        raise SystemExit(
            "\nRefusing to deploy: the build exceeds its memory budget.\n"
            "Fix the breaches above, or pass --skip-memory-gate to flash it "
            "anyway for diagnosis."
        )

    mpy_cross = find_mpy_cross()
    staging = stage_tree(mpy_cross)
    try:
        deploy(args.port, staging)
    finally:
        if args.keep_staging:
            print("Staged tree kept at:", staging)
        else:
            shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    main()
