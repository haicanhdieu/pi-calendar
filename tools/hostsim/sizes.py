"""Compiled-size measurement for the deployable module set."""

import os
import shutil
import subprocess
import tempfile

from tools.hostsim import budgets
from tools.hostsim.graph import (
    ROOT,
    boot_resident_modules,
    config_resident_modules,
    module_path,
    station_web_modules,
)
from tools.deploy import PRECOMPILE

PRECOMPILED_MODULES = {path[:-3].replace("/", ".") for path in PRECOMPILE}


class MpyCrossMissing(Exception):
    """``mpy-cross`` is not installed, so compiled sizes cannot be measured."""


def find_mpy_cross():
    found = os.environ.get("MPY_CROSS") or shutil.which("mpy-cross")
    if not found:
        raise MpyCrossMissing(
            "mpy-cross not found. Install the build matching the flashed "
            "firmware (`uv pip install mpy-cross==1.20.0`) or set MPY_CROSS."
        )
    return found


def compiled_sizes(modules, mpy_cross=None):
    """Map each module to the byte size of its ``mpy-cross`` output."""
    mpy_cross = mpy_cross or find_mpy_cross()
    out = {}
    staging = tempfile.mkdtemp(prefix="pi-calendar-sizes-")
    try:
        for module in modules:
            source = module_path(module)
            if source is None:
                continue
            target = os.path.join(staging, module + ".mpy")
            command = [mpy_cross]
            if module in PRECOMPILED_MODULES:
                command.append("-O3")
            command.extend((source, "-o", target))
            subprocess.run(command, check=True)
            out[module] = os.path.getsize(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return out


def report():
    """Measured sizes plus every budget breach, as a dict."""
    mpy_cross = find_mpy_cross()
    boot = boot_resident_modules()
    resident = config_resident_modules()
    web = station_web_modules(resident)
    boot_sizes = compiled_sizes(boot, mpy_cross)
    config_sizes = compiled_sizes(resident, mpy_cross)
    web_sizes = compiled_sizes(web, mpy_cross)

    boot_total = sum(boot_sizes.values())
    config_total = sum(config_sizes.values())
    web_total = sum(web_sizes.values())
    breaches = []

    def check(label, actual, budget):
        if actual > budget:
            breaches.append(
                "%s: %d bytes exceeds budget %d (+%d)"
                % (label, actual, budget, actual - budget)
            )

    check("clock-mode resident .mpy total", boot_total, budgets.BOOT_RESIDENT_MPY_BYTES)
    check(
        "config-mode resident .mpy total",
        config_total,
        budgets.CONFIG_RESIDENT_MPY_BYTES,
    )
    check("station-web .mpy total", web_total, budgets.STATION_WEB_MPY_BYTES)
    # Only config mode holds a resident set and the web chain at once.
    check(
        "config-mode + web .mpy total",
        config_total + web_total,
        budgets.COMBINED_MPY_BYTES,
    )

    all_sizes = dict(boot_sizes)
    all_sizes.update(config_sizes)
    all_sizes.update(web_sizes)
    for module, size in sorted(all_sizes.items()):
        ceiling = budgets.MODULE_MPY_BYTES_OVERRIDES.get(
            module, budgets.MODULE_MPY_BYTES
        )
        check("module %s" % module, size, ceiling)

    return {
        "boot_modules": boot,
        "config_modules": resident,
        "web_modules": web,
        "boot_sizes": boot_sizes,
        "config_sizes": config_sizes,
        "web_sizes": web_sizes,
        "boot_total": boot_total,
        "config_total": config_total,
        "web_total": web_total,
        "combined_total": config_total + web_total,
        "breaches": breaches,
    }


def format_report(data):
    lines = [
        "clock-mode resident   : %3d   %6d bytes (budget %d)"
        % (
            len(data["boot_modules"]),
            data["boot_total"],
            budgets.BOOT_RESIDENT_MPY_BYTES,
        ),
        "config-mode resident  : %3d   %6d bytes (budget %d)"
        % (
            len(data["config_modules"]),
            data["config_total"],
            budgets.CONFIG_RESIDENT_MPY_BYTES,
        ),
        "station-web modules   : %3d   %6d bytes (budget %d)"
        % (len(data["web_modules"]), data["web_total"], budgets.STATION_WEB_MPY_BYTES),
        "config-mode + web     :       %6d bytes (budget %d)"
        % (data["combined_total"], budgets.COMBINED_MPY_BYTES),
        "",
        "largest modules:",
    ]
    everything = dict(data["boot_sizes"])
    everything.update(data["config_sizes"])
    everything.update(data["web_sizes"])
    for module, size in sorted(everything.items(), key=lambda kv: -kv[1])[:8]:
        lines.append("  %-44s %6d" % (module, size))
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import sys

    sys.path.insert(0, ROOT)
    data = report()
    print(format_report(data))
    for breach in data["breaches"]:
        print("BUDGET BREACH:", breach)
    sys.exit(1 if data["breaches"] else 0)
