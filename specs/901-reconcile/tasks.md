# Tasks: one re-entry command; no builder without a build record

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_reconcile.py`: three repositories, clean, missing build record and
  dirty, reconciled twice (FR-001 to FR-005).
- [x] T002 [US1] an unlaunched record with outside work keeps its start (US1-5).
- [x] T003 [US1] interruption halfway, then the rerun (US1-6).
- [x] T004 [US3] `--repo --branch`, `--pr` and the refusals (FR-007, US3).
- [x] T005 [US2] `test_build_next.py`: the guard refusal and its exit; `guards.enforce` off
  logs and registers (FR-006).
- [x] T006 run them, see each fail for the stated reason.

## Phase 2: implementation (green)

- [x] T007 `adopt_worktree(dirty=)` and `worktree.checkout`; `claim_pr` uses it (FR-004, FR-007).
- [x] T008 `build reconcile` and `reconcile()` (FR-001 to FR-003).
- [x] T009 `next_step` accepts a done build (FR-005).
- [x] T010 the guard refusal; the #892 tests launch with enforce off (FR-006).
- [x] T011 `pr act` adoption step names reconcile; message updates in existing tests (FR-007).
- [x] T014 `build next` waits past the day's CAP for a new build; `build check` with no record
  names reconcile; `record_pr(built=True)` for the claim (FR-009, US3-1).
- [x] T012 planner charter, `bin/wuwei agents build`, reference, daily and concepts (FR-008).

## Phase 3: verification

- [x] T013 every importing test file plus invariants, docs and charters under 3.12; the changed
  areas under 3.11.
