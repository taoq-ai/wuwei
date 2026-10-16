# Tasks: the routes seats run and the payloads the harness sends are fixtures the suite reads

## Phase 1: Tests first

- [x] T001 [US1] Every route in tests/fixtures/routes.json reads through guards.bash as recorded (tests/test_guards.py)
- [x] T002 [US3] The corpus names a source and a known verdict per route, and holds the review ping as pass (tests/test_guards.py)
- [x] T003 [US4] No fixture file matches guards.SECRETS, the workspace canary or a local path (tests/test_guards.py)
- [x] T004 [US1] Every payload replays through hook.handle without an error and writes the seat rows its table names (tests/test_hook.py)
- [x] T005 The payload table and the directory hold the same files (tests/test_hook.py)
- [x] T006 Run the new tests red (10 failed)

## Phase 2: Fixtures

- [x] T007 Collect the commands from charters/, skills/, charters/_pr.md and docs/site/ with their source lines
- [x] T008 Collect the gh api commands from the 2026-10-16 traces, local paths dropped
- [x] T009 Write tests/fixtures/routes.json with the verdict main gives each route
- [x] T010 Write the seven payloads under tests/fixtures/payloads/
- [x] T011 Run the full suite green, runtime unchanged at 2,999

## Phase 3: Checks

- [x] T012 [US2] In a scratch copy, a guard that refuses the review_threads route fails the test naming it
- [x] T013 In a scratch copy, a canary in a fixture file fails the scan

## Phase 4: Fix round (arch)

- [x] T014 Merge origin/main (1620583) into the branch
- [x] T015 tests/fixtures/payloads/README.md gives each payload its provenance, transcript or reconstructed with its source
- [x] T016 Rename the payload tests to claim only what they show (fixture payloads, listed shapes)
- [x] T017 A test that every payload file has a provenance line, and only the two accepted Agent payloads say transcript
- [x] T018 Every merge route naming PR 5 passes on a gap-free PR; in a scratch copy a door that refuses every merge fails it
