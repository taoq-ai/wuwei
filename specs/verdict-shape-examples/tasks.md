# Tasks: the gate charter shows each finding shape

## Phase 1: Tests first

- [x] T001 The not-counted lines name only the gates the gap names (tests/test_evidence.py)
- [x] T002 A delta review gap names only its gate's uncounted verdicts (tests/test_evidence.py)
- [x] T003 The charter's example finding lines parse and the issue's three shapes are refused (tests/test_charters.py)
- [x] T004 A sub-bullet under a finding denies the hand-back naming the line (tests/test_hook.py)
- [x] T005 Run T001 and T003 red

## Phase 2: Implementation

- [x] T006 `uncounted` takes the gates and `gate_gaps` passes them (cli/wuwei/evidence.py)
- [x] T007 The three rules with examples in charters/_gate.md, words held
- [x] T008 `bin/wuwei agents build`, re-vendor .claude/

## Phase 3: Checks

- [x] T009 Full suite, agents check
- [x] T010 Mutants of the filter and of both calls, each killed by a behavioural test
- [x] T011 Route differential at main and head (route_diff.py)
