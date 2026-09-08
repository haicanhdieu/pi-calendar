"""Deploy main.py/src/secrets.py to a flashed Pico W, precompiling the
largest first-boot import chains to .mpy so MicroPython loads bytecode
instead of compiling source on-device (see docs/heap_constraints.md).

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
# (setup-AP HTTP surface and the station-mode admin site). Ship these as
# precompiled .mpy; everything else deploys as plain .py.
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
    "src/provisioning/kdf_job.py",
    "src/provisioning/validation.py",
    "src/provisioning/verifier.py",
]


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
                [mpy_cross, str(path), "-o", str(dest)], check=True
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="mpremote serial port")
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Do not delete the staged tree (for inspection)",
    )
    args = parser.parse_args()

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
