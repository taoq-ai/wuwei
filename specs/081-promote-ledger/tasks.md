# Tasks: Proposal promotion and ledger

## Phase 1: Promotion

- [X] T001 [US1] Write failing tests for proposal target, duplicate, evidence, patch, fold, archive and ledger in `tests/test_promotion.py`; run and confirm failure.
- [X] T002 [US1] Implement proposal handling and `promote` command in `cli/wuwei/promotion.py` and `cli/wuwei/commands/promote.py`; run T001 tests.

## Phase 2: Payload

- [X] T003 [US2] Write failing last-run payload tests in `tests/test_promotion.py`; run and confirm failure.
- [X] T004 [US2] Add last-run rendering in `cli/wuwei/memory.py`; run T003 tests.

## Phase 3: Adherence and safety

- [X] T005 [US3] Write failing probation, trace-load, capacity and archive candidate tests in `tests/test_promotion.py`; run and confirm failure.
- [X] T006 [US3] Implement candidate selection and `consolidate` command, plus probation config; run T005 tests.
- [X] T007 [US1] Write failing symlinked `.wuwei` and reserved ledger tests in `tests/test_promotion.py`; run and confirm failure.
- [X] T008 [US1] Refuse symlinked `.wuwei` in writers and reserve ledger writes; run T007 tests.

## Phase 4: Verification

- [X] T009 Run the full issue interpreter pytest command and inspect written files for em-dashes and emojis.

## Phase 5: Review fixes

- [X] T010 Add failing guard tests for protected memory containers and archives, then protect them.
- [X] T011 Add a failing replay test, then rename proposals after ledger append.
- [X] T012 Update the refusal tier test, classify routine refusals as silent, and remove unused checks.
