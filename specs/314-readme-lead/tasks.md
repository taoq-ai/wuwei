# Tasks: README lead, WUWEI first in the comparison, short limits

**Input**: `specs/314-readme-lead/spec.md`, `plan.md`, `research.md`
**Test command**: `python -m pytest -q` from the repository root.

Each test task lands and is run, and fails for the stated reason, before its implementation
task.

## Phase 1: Comparison table by question, WUWEI first (US2, US4)

- [X] T001 [US2] `tests/test_docs.py`: rewrite `test_readme_compares_with_other_tools` as in
  plan.md (five question columns, at most six columns, WUWEI first row, six names and links
  kept, "Where WUWEI is worse" absent, banned words absent). Run it; it fails on the missing
  `Who plans the day` header.
- [X] T002 [US2] `README.md`: replace the `## How WUWEI compares` section (intro, table,
  paragraph, `### How they compose` in two sentences) with the plan.md text; delete
  `### Where WUWEI is worse`. Re-check each external cell against `research.md`. Run T001;
  it passes.

## Phase 2: Lead, alt text, docs index and Limits (US1, US3, US4)

- [X] T003 [US1] [US3] `tests/test_docs.py`: add `test_readme_lead_and_limits` as in
  plan.md (lead position and phrases; `ranked` and `retro` in the hero alt and the
  `docs/site/index.md` intro; `## Limits` between Quick start and Development installs with
  its four facts and three links). Run it; it fails on the missing lead.
- [X] T004 [US1] `README.md`: insert the lead after the hero nav line and replace the hero
  `alt` value, both from plan.md.
- [X] T005 [US1] `docs/site/index.md`: replace the intro sentence on line 7 with the
  plan.md text.
- [X] T006 [US3] `README.md`: add `## Limits` after Quick start, before
  `## Development installs`, from plan.md. Run T003; it passes.

## Phase 3: Verify

- [X] T007 Mutation check by hand: delete one Limits line, one tool link, move the WUWEI
  row down, and add "enterprise" to the README, one at a time; `tests/test_docs.py` fails
  each time. Restore.
- [X] T008 Run the humanizer (embedded mode) or the checklist in
  `charters/_common-authoring.md` over every paragraph written; grep `README.md`,
  `docs/site/index.md` and `tests/test_docs.py` for em-dashes and emojis.
- [X] T009 Run `python -m pytest -q`; everything passes.
- [X] T010 In the final report (no file in the repository), give the PR body notes: old table (`README.md:44-52` on `main`) and new table
  one after the other, and the URLs from `research.md` as re-checked claims. Do not run
  `gh`.
