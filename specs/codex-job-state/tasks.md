# Tasks: the board shows a registered Codex job's state

## Phase 1: Tests first

- [x] T001 [US1] [US2] [US3] Each job status, a HANDOFF path in markdown and backtick form, and a question ending show on the board (tests/test_plan.py)
- [x] T002 [US4] A missing, malformed, list, empty, null-status or bad-result file reads `job state unreadable`, never done; a later `--reason` keeps the job (tests/test_plan.py)
- [x] T003 Run the new tests red: 14 failed, 24 passed (`--job` unrecognised)

## Phase 2: Implementation

- [x] T004 `plan run --job` stores the path on the item (cli/wuwei/__main__.py)
- [x] T005 `board.job` reads the registered file and the run row shows its state (cli/wuwei/board.py, cli/wuwei/upgrade.py)
- [x] T006 Copy the three files into .claude/wuwei/cli/wuwei/
- [x] T007 Run the suite green, runtime at 3,357 (+6)

## Phase 3: Docs

- [x] T008 charters/planner.md (and its vendored copy), docs/design.md, docs/site/reference.md; `bin/wuwei agents build`

## Fix round 1 (quality FIX at e84f228)

- [x] T009 A 200 KB nested-array job file reads `job state unreadable` (red: RecursionError); a failed or cancelled job ending in `?` keeps its status (red against the mutant that drops the completed check) (tests/test_plan.py)
- [x] T010 Move the reader to `ws.read_json`, catching RecursionError; the board no longer imports upgrade (cli/wuwei/ws.py, board.py, upgrade.py and copies); runtime at 3,356 (+5)

## Fix round 2 (quality FIX at 7ba5f67)

- [x] T011 A list status, and arrays nested 100,000 deep in `status` or `result.rawOutput`, read `job state unreadable` or the plain status, never a crash; red on Python 3.14.5 (RecursionError in repr), which parses that depth (tests/test_plan.py)
- [x] T012 The board takes `status` and `rawOutput` only when they are str (cli/wuwei/board.py and copy); runtime +5 over main at 40b5fb5
