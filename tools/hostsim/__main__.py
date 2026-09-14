"""CLI entry point: ``python -m tools.hostsim``.

Prints the compiled-size report always, and the heap simulation when a
matching MicroPython interpreter is available.  Exits non-zero on any budget
breach, so it works as a gate in ``tools/deploy.py`` and in CI.
"""

import argparse
import sys

from tools.hostsim import runner, sizes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-sim",
        action="store_true",
        help="Only check compiled sizes; do not run the MicroPython simulation.",
    )
    parser.add_argument(
        "--require-sim",
        action="store_true",
        help="Fail instead of skipping when no MicroPython interpreter is found.",
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Leave the staged tree in place for inspection.",
    )
    args = parser.parse_args(argv)

    problems = []

    try:
        size_data = sizes.report()
        print("== compiled sizes ==")
        print(sizes.format_report(size_data))
        problems.extend(size_data["breaches"])
    except sizes.MpyCrossMissing as exc:
        print("== compiled sizes ==")
        print("skipped:", exc)

    if not args.skip_sim:
        print()
        print("== heap simulation ==")
        try:
            result = runner.run(keep_staging=args.keep_staging)
            print(runner.format_report(result))
            problems.extend(runner.breaches(result))
        except runner.SimulatorMissing as exc:
            if args.require_sim:
                problems.append(str(exc))
            else:
                print("skipped:", exc)

    print()
    if problems:
        print("MEMORY BUDGET FAILED")
        for problem in problems:
            print("  -", problem)
        return 1
    print("memory budget OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
