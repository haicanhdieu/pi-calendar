<!-- bmad:context -->
<!-- Verified 2026-09-05 against the uncommitted working tree (no commits yet). Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## pi-calendar

Firmware and planning repository for a Raspberry Pi Pico W clock and calendar device. This block carries only rules and pointers: read the active PRD artifacts and `docs/` for product, hardware, design, and project-structure decisions before changing anything; do not restate them here.

## Policy

- Root buckets stay as installed: `_bmad-output/planning-artifacts/`, `_bmad-output/implementation-artifacts/`, `_bmad-output/test-artifacts/`. For every PRD, derive one stable lowercase kebab-case `<prd-slug>` and group artifacts inside each bucket as `<bucket>/<prd-slug>/<subtype>/`, flattened — files sit directly in the subtype folder, no dated run-folder layer (e.g. `_bmad-output/planning-artifacts/pico-w-calendar-clock/prds/prd.md`, not `.../prds/prd-<slug>-<date>/prd.md`). Never flatten artifacts directly into a bucket root.
- This repo currently has one product, slug `pico-w-calendar-clock` (the product name, not the repo dirname `pi-calendar`). Its artifacts: `_bmad-output/planning-artifacts/pico-w-calendar-clock/{briefs,prds,ux-designs,architecture}/`, `_bmad-output/implementation-artifacts/pico-w-calendar-clock/`, `_bmad-output/test-artifacts/pico-w-calendar-clock/{test-design,test-reviews,traceability}/`.
- Keep artifacts for different PRDs isolated in separate slug directories inside each bucket; preserve BMAD's expected filenames and artifact types inside the active PRD's subtype directory.
- The flattened slug-then-subtype grouping is enforced by config, not convention — do not edit installer-managed `_bmad/config.toml` or any skill's own `customize.toml`. Instead: `_bmad/custom/config.toml` overrides `[modules.bmm].implementation_artifacts` and `[modules.tea].test_artifacts`/`test_design_output`/`test_review_output`/`trace_output`; `_bmad/custom/bmad-prd.toml`, `bmad-ux.toml`, `bmad-architecture.toml`, `bmad-product-brief.toml` each override their `*_output_path` to `{planning_artifacts}/pico-w-calendar-clock/<subtype>` and set `run_folder_pattern = ""` (drops the dated run subfolder). Adding a second PRD means adding its slug the same way in each of these override files.
- Treat each `_bmad-output/<bucket>/<prd-slug>/` tree as the source of truth for that PRD's planning-to-implementation-to-testing trail; do not place those artifacts in `docs/` or the repository root.
- Keep product, hardware, and design decisions in `docs/` and the PRD artifacts, never in this block.
- Do not change hardware pin assignments in software unless the physical wiring has changed and the documentation is updated in the same change.

## Where things are

- Hardware and product source of truth: `docs/`
- Per-PRD planning, implementation, and test artifacts, grouped bucket-then-slug-then-subtype: `_bmad-output/{planning-artifacts,implementation-artifacts,test-artifacts}/<prd-slug>/<subtype>/`
- Project folder structure: `_bmad-output/planning-artifacts/<prd-slug>/architecture/project-structure.md`
- Slug-then-subtype path overrides: `_bmad/custom/config.toml` and `_bmad/custom/bmad-{prd,ux,architecture,product-brief}.toml`
- BMAD configuration and workflow scripts: `_bmad/config.toml` and `_bmad/scripts/`
- Firmware entry point: `main.py`
- BMAD loop state and policy: `.bmad-loop/`

## Running and verifying

- Run BMAD scripts as `uv run _bmad/scripts/<name>.py`; they declare `requires-python = ">=3.11"` inline and bare `python` ignores that.
- TODO: no host test suite exists. When the first calendar logic lands, create it under `tests/` and run it with `uv run pytest`.
- Firmware cannot be run in this environment. Never report on-device behaviour as observed; say what needs flashing and leave the device run to the user. Deployment tooling is recorded in the active PRD's artifacts.

## Conventions that differ from defaults

- Pure logic — calendar math, date arithmetic, view-state decisions, lunar conversion — must not import `machine`, `network`, or `ntptime`; those imports fail under CPython and take the whole host test suite down. Keep hardware access in the display and device layers and pass values in.

<!-- /bmad:context -->
