# Tasks: WUWEI names an orchestration gap

## Phase 1: Tests first

- [x] T001 [US1] Three open PRs owing gates on green heads, no seat: the team row lists both lines, and `board.text` prints it (tests/test_watch.py)
- [x] T002 [US3] A shepherd seat in this session clears the shepherd line; a sentinel seat clears the gate line (tests/test_watch.py)
- [x] T003 [US3] A seat of a dead session, a stopped seat, an unconfirmed seat, this session's seat from yesterday, a seat with no session, and no session known: none runs (tests/test_watch.py)
- [x] T004 [US3] Two open PRs: no shepherd line (tests/test_watch.py)
- [x] T005 [US2] CI running or failing on the owing heads: no gate line (tests/test_watch.py)
- [x] T006 [US5] The lines are duties: visible, never blocking (tests/test_watch.py)
- [x] T007 [US4] A seat another session left running never silences the Stop; the same state reminds once while the PR count moves from 4 to 3 (tests/test_hook.py)
- [x] T008 Run the new tests red on main's code: tests/test_watch.py 5 failed, 13 passed; the two Stop tests 2 failed

## Phase 2: Implementation

- [x] T009 `board.running` and the team row in `board.compute` (cli/wuwei/board.py)
- [x] T010 `DUTY` matches `orchestration:` (cli/wuwei/evidence.py)
- [x] T011 `hook.stop` reads `board.running` with the payload's session (cli/wuwei/hook.py)
- [x] T012 The link tests in tests/test_watch.py and the two cold-board tests in tests/test_status_perf.py expect the team row
- [x] T013 [US6] Planner charter rule 9 and `/wuwei-run` step 3, with the .claude copies (charters/planner.md, skills/wuwei-run/SKILL.md)
- [x] T014 Docs: the duties section of docs/site/concepts/evidence.md, the Stop paragraph of docs/site/concepts/hooks.md
- [x] T015 Re-vendor .claude/ with setup.vendor('.'); `bin/wuwei agents build` reports the agents match

## Phase 3: Checks

- [x] T016 Full suite green apart from four tests that fail at main 0f6572e6 too on this machine (bash 3.2: three push shapes in tests/test_guards.py and the harness shell test in tests/test_codex.py)
- [x] T017 Route corpus differential at main and the head, with its sha256 (plan.md, Measurements)
- [x] T018 Fifteen mutants in fresh copies, both trees, one at a time: 15 killed
