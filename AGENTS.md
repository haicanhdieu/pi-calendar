<!-- bmad:context -->
<!-- Verified 2026-09-05 against the uncommitted working tree (no commits yet). Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## pi-calendar

Firmware and planning repository for a Raspberry Pi Pico W clock and calendar device. This block carries only rules and pointers: read the active PRD artifacts and `docs/` for product, hardware, design, and project-structure decisions before changing anything; do not restate them here.

## Policy

- Root buckets stay as installed: `_bmad-output/planning-artifacts/`, `_bmad-output/implementation-artifacts/`, `_bmad-output/test-artifacts/`. For every PRD, derive one stable lowercase kebab-case `<prd-slug>` and group artifacts inside each bucket as `<bucket>/<prd-slug>/<subtype>/`, flattened — files sit directly in the subtype folder, no dated run-folder layer (e.g. `_bmad-output/planning-artifacts/pico-w-calendar-clock/prds/prd.md`, not `.../prds/prd-<slug>-<date>/prd.md`). Never flatten artifacts directly into a bucket root.
- This repo runs each substantial feature as its own full PRD → UX → architecture → epics → implementation → test cycle, each under its own slug. Slugs so far: `pico-w-calendar-clock` (core clock/calendar device, the product name, not the repo dirname `pi-calendar`) and `wifi-config` (Wi-Fi provisioning + admin config web UI). Each slug's artifacts: `_bmad-output/planning-artifacts/<slug>/{briefs,prds,ux-designs,architecture}/`, `_bmad-output/implementation-artifacts/<slug>/`, `_bmad-output/test-artifacts/<slug>/{test-design,test-reviews,traceability}/`. A PRD may still cross-reference another slug's `prd.md` for shared vision/glossary (e.g. `wifi-config/prds/prd.md` points back to `pico-w-calendar-clock/prds/prd.md`) without repeating it — cross-slug reference is fine, cross-slug artifact mixing is not.
- Keep artifacts for different slugs isolated in separate slug directories inside each bucket; preserve BMAD's expected filenames and artifact types inside the active slug's subtype directory.
- The flattened slug-then-subtype grouping is enforced by config, not convention — do not edit installer-managed `_bmad/config.toml` or any skill's own `customize.toml`. Instead: `_bmad/custom/config.toml` overrides `[modules.bmm].implementation_artifacts` and `[modules.tea].test_artifacts`/`test_design_output`/`test_review_output`/`trace_output`; `_bmad/custom/bmad-prd.toml`, `bmad-ux.toml`, `bmad-architecture.toml`, `bmad-product-brief.toml` each override their `*_output_path` to `{planning_artifacts}/<active-slug>/<subtype>` and set `run_folder_pattern = ""` (drops the dated run subfolder). These overrides are scalars — they point at whichever slug is currently being worked, one at a time. Switching which slug a skill run auto-binds to means editing that slug's path into these five files before the run; other slugs' artifacts already on disk are unaffected by the switch. Currently pointed at `wifi-config` (the active work).
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
