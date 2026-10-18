# Tasks: a breaking change is read from the latest arch verdict

## Phase 1: Tests first

- [x] T001 [US1] A later arch `Breaking: no` at a descendant clears an earlier yes (tests/test_evidence.py)
- [x] T002 [US2] A later arch `Breaking: yes` raises the announcement gap (tests/test_evidence.py)
- [x] T003 [US3] A `!` title holds the gap though the latest arch verdict says no (tests/test_evidence.py)
- [x] T004 Boundaries: a yes at an older head attested last, file names against ledger order, an
  edited verdict without a Breaking field
- [x] T005 Run the new tests red
- [x] T006 Security round: a `no` at an older ancestor (F1), at a non-ancestor head (F2), from
  another PR or repository (F3) and at the same head clears nothing; run red

## Phase 2: Implementation

- [x] T007 Read Breaking from the latest arch verdict on the PR's line (cli/wuwei/evidence.py)
- [x] T008 Re-vendor .claude/wuwei with setup.vendor('.')
- [x] T009 Run the full suite green, runtime at 3,000 or fewer
