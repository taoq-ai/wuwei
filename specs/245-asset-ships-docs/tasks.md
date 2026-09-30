# Tasks: The release asset ships the operator docs it links to

Each test task is written, run and seen failing for the stated reason before its
implementation task.

## Phase 1: Linked docs reach the signed asset [US1, US2]

- [X] T001 [US2] [US1] In tests/test_docs.py add
  `test_release_asset_ships_every_linked_doc` as specified in plan.md section 1 (stub
  signer, build via runpy, link check over README.md, skills/**/*.md, agents/**/*.md
  against MANIFEST.sha256, then docs/site/*.md and docs/assets/*.svg in manifest and
  archive, signer called on the manifest, `integrity.measure(stage).exit == 0`). Run
  `python -m pytest -q tests/test_docs.py -k release_asset`. Expected failure: the
  `missing` assertion names `README.md -> NOTICE`, `README.md -> docs/site/index.md`,
  `README.md -> docs/site/concepts.md`, `README.md -> docs/site/configuration.md` and
  `README.md -> docs/specs/2026-09-24-wuwei-design.md`.
- [X] T002 [US1] In scripts/build-release.py `build()`: add `'docs'` to the copytree
  tuple, add `'NOTICE'` to the file tuple, delete the `docs/` mkdir and the single
  `docs/integrity.md` copy. T001 passes.

## Phase 2: Keep the headless scratch build in step

- [X] T003 Run `python -m pytest -q tests/test_headless_e2e.py -k scratch_build`. Expected
  failure after T002: the scratch build exits 2 with `release unmeasured` because the
  scratch source has no `NOTICE`.
- [X] T004 In scripts/headless_e2e.py line 129 (`prepare()`), add `'NOTICE'` to the file
  tuple and change nothing else. T003 passes.

## Phase 3: Verify

- [X] T005 Run `python -m pytest -q tests/test_integrity.py -k release_package` (the
  existing release test still passes unchanged).
- [X] T006 Run `python -m pytest -q` from the repository root; everything passes. Check
  every changed file for em-dashes, emojis and absolute local paths, and confirm
  `git diff --stat` touches only tests/test_docs.py, scripts/build-release.py,
  scripts/headless_e2e.py and specs/245-asset-ships-docs/.
