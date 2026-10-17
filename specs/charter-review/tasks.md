# Tasks: charter-review

## Phase 1: Tests first

- [x] T001 [US1] `tests/test_charters.py`: sentence splitter, the 35-word test and the 30-word average test over charters and skills
- [x] T002 [US1] Generated agent word ceiling test
- [x] T003 [US2] No issue number or file of this repository in a charter or skill
- [x] T004 [US2] `tests/test_setup.py`: probe rules read in `AGENTS.md`; the generic agents name the repository's process and hold none of this repository's files
- [x] T005 [US3] Decisions and Done stated once in `_common.md`; reviewer and staleness are process fit in `_common.md` and `wuwei-rules`; "door" never means a decision
- [x] T006 [US4] Arch lens test, frameworks test, scanner and supply-chain test, steward deletion remit, planner numbering
- [x] T007 [US5] Every skill description has `Use` and `Not for`; `tests/fixtures/skill-triggers.json` covers every skill with near misses
- [x] T008 Run the new tests on `git archive origin/main` with the head's test files copied in: `32 failed, 85 passed` (the sentence test red on 11 of 19 files; the ceiling test red on none, it guards growth)

## Phase 2: Charters and skills

- [x] T009 [US3] `_common.md` Done section with the thresholds; `_way.md` and `planner.md` point to it; `wuwei-rules` points to it and drops the contradiction
- [x] T010 [US2] `AGENTS.md` "Testing the guards"; `.wuwei/standards.md` lines per gate; `_gate.md` rule 4, `builder.md` AUTH and VAL, `planner.md` 2 and 4, `sentinel-security.md` 6 made generic
- [x] T011 [US4] `sentinel-arch.md` rewritten; trust defect to security, open measure to goal
- [x] T012 [US4] Framework lines; security scanner and supply chain; quality test quality; lead capacity cap; steward rule 9
- [x] T013 [US5] Negative triggers in the five skill descriptions
- [x] T014 [US1] Every sentence over 35 words split or cut; planner numbering 1 to 10; issue numbers and dated conditions out
- [x] T015 `builder.md` SOLID and clean-code lines folded into one; `_common-authoring.md` list cut to the non-obvious items

## Phase 3: Build and docs

- [x] T016 `bin/wuwei agents build`; `setup.vendor('.')`; drift tests green
- [x] T017 `docs/design.md` section 9 and `docs/site/concepts/team.md` name the charter ceiling and the lesson placement
- [x] T018 Full suite green: `pytest -q -W error` gives `1682 passed, 2 skipped`; runtime 2,976 lines (`wc -l cli/wuwei/*.py`)

## Phase 4: Gate fixes at 7021905

- [x] T019 `sentinel-arch.md`: a trust defect the arch gate sees blocks under gate rule 5; the security gate may not run on the head (arch, security)
- [x] T020 Red-first and size counts re-derived from runs and named with their commands in spec, tasks, analysis and the PR body (quality, goal)
- [x] T021 `tests/test_charters.py`: dead branch removed, average pinned at the charter's 20 words, thresholds read from `evidence.py` constants, the wide-change threshold checked (quality)
- [x] T022 `_common.md` names the five-merge floor on the change failure rate; `sentinel-arch.md` names no file of this repository; `wuwei-rules` no longer says it does not restate Done (arch, goal notes)
