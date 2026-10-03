# Tasks: The README borrows the shape of superpowers' README

**Input**: `specs/440-readme-shape/spec.md`, `plan.md`
**Test command**: `python -m pytest -q` from the repository root.

Each test task lands and is run, and fails for the stated reason, before its
implementation task. The test design is in plan.md, "Test changes".

## Phase 1: Credit (US4)

- [X] T001 [US4] `tests/test_docs.py`: extend `test_notice_credits_match_readme_acknowledgements`
  with `'superpowers'` in the names tuple and the README and MIT check on the NOTICE
  superpowers block. Run it; it fails on the missing superpowers name.
- [X] T002 [US4] `NOTICE`: add the superpowers entry from plan.md after ZIRAN.
  Run T001; it fails on the URL missing from the Acknowledgements section.
- [X] T003 [US4] `README.md`: add the superpowers bullet to `## Acknowledgements` after the
  Spec Kit bullet. Run T001; it passes.

## Phase 2: Section order and shape (US1, US2, US3, US5)

- [X] T004 [US5] `tests/test_docs.py`: change the order pin in
  `test_readme_compares_with_other_tools` to What WUWEI is and is not < Installation <
  How WUWEI compares. Run it; it fails because `## Installation` is missing.
- [X] T005 [US1] [US2] [US3] `tests/test_docs.py`: add
  `test_readme_tells_the_day_in_superpowers_shape` as in plan.md (heading order, 300-line
  budget, per-section counts and phrases, adapters table against `registry.known`, the
  Planned line, the harness subsections, skill and command names against `skills/` and
  `wuwei.__main__.GROUPS`). Run it; it fails on the missing `## How it works`.
- [X] T006 [US3] `README.md`: rename `## Install` to `## Installation`, make its body
  `### Claude Code` plus the development-source line, add `### Codex` and
  `### Other harnesses (planned)`, and move Installation and `## Quick start` (unchanged)
  to just before `## How WUWEI compares`. Run T004; it passes.
- [X] T007 [US1] `README.md`: add `## How it works` and `## The basic workflow` after
  `## What ships today`, from the plan.md outline.
- [X] T008 [US1] `README.md`: add `## When something goes wrong`.
- [X] T009 [US2] `README.md`: add `## What is inside` with the skills, seats, guards by
  hook event, the adapters table built from `registry.known` for each port, the Planned
  line and the docs links.
- [X] T010 [US1] `README.md`: add `## Philosophy`. Run T005; it passes. Run
  `test_glossary_words_link_at_first_use` and move each glossary link to its new first
  use until it passes; run `test_release_asset_ships_every_linked_doc`.

## Phase 3: Docs index (US4)

- [X] T011 [US4] `tests/test_docs.py`: add `test_docs_index_mirrors_the_readme_sections`
  as in plan.md. Run it; it fails on the current index order (Recovery before
  Concepts).
- [X] T012 [US4] `docs/site/index.md`: reorder the page list as in plan.md, bullet text
  unchanged. Run T011; it passes.

## Phase 4: Verify

- [X] T013 Mutation check by hand on `tests/test_docs.py`: remove one skill link, add a
  fake name to an adapters row, swap two new headings, add a sixth bullet to When
  something goes wrong, add a code block to `### Other harnesses (planned)`; the new tests
  fail each time. Restore.
- [X] T014 Run the humanizer (embedded mode) or the checklist in
  `charters/_common-authoring.md` over every paragraph written in `README.md` and `NOTICE`;
  compare the new sections with the superpowers README shape only, no shared sentences.
  Grep `README.md`, `NOTICE`, `docs/site/index.md` and `tests/test_docs.py` for em-dashes
  and emojis.
- [X] T015 Run `python -m pytest -q`; everything passes.
