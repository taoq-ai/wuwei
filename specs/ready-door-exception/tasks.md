# Tasks: the ready and reviewer doors honour an owner exception the way wuwei evidence does

## Phase 1: Tests first

- [x] T001 [US1] An exact ruling opens every READY route, at its head only (tests/test_guards.py)
- [x] T002 [US1] [US2] A partial gate list keeps the MCP routes shut; the full list opens them (tests/test_guards.py)
- [x] T003 [US2] Another PR, a ruling not approved, another head and a moved head keep the door shut (tests/test_guards.py)
- [x] T004 [US3] The not-counted lines go with the accepted gate gap, at the ready door and in evidence.gaps (tests/test_guards.py, tests/test_evidence.py)
- [x] T005 [US3] The excepted-exact probe's oracle names a not-counted line under an accepted gate gap (specs/excepted-exact/probe.py)
- [x] T006 Run the new tests red on 646e462's code

## Phase 2: Implementation

- [x] T007 `create_door` takes a PR reference and applies `evidence.excepted` at its head; `ready_door` passes it (cli/wuwei/guards.py)
- [x] T008 `excepted` drops the not-counted lines with a dropped gate gap (cli/wuwei/evidence.py)
- [x] T009 Copy the plugin into .claude/wuwei/ with `setup.vendor('.')`
- [x] T010 State the rule in docs/design.md sections 5 and 7, docs/site/concepts/doors.md and evidence.md
- [x] T011 Run the full suite, runtime within 5 lines

## Phase 3: Checks

- [x] T012 [US4] Route corpus through the guards at main and at the head under each ruling form (route_probe.py)
- [x] T013 Generated ruling probe and the corpus routes under real bash with a stub gh (ruling_probe.py)
- [x] T014 excepted-exact probe at main and at the head
- [x] T015 Mutants of each new condition on both copies, one at a time (mutants.py)
