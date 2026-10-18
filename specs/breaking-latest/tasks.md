# Tasks: a breaking change is read from the latest arch verdict

## Phase 1: Tests first

- [x] T001 [US1] A later arch `Breaking: no` clears an earlier yes (tests/test_evidence.py)
- [x] T002 [US2] A later arch `Breaking: yes` raises the announcement gap (tests/test_evidence.py)
- [x] T003 [US3] A `!` title holds the gap though the latest arch verdict says no (tests/test_evidence.py)
- [x] T004 Boundaries: two verdicts at one head, a verdict at an older head attested last, file
  names and times against ledger order, an edited verdict without a Breaking field
- [x] T005 Run the new tests red

## Phase 2: Implementation

- [x] T006 Read Breaking from the last arch verdict that carries it (cli/wuwei/evidence.py)
- [x] T007 Re-vendor .claude/wuwei with setup.vendor('.')
- [x] T008 Run the full suite green, runtime at 3,000 or fewer
