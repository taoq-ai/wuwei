# Tasks: next and every refusal carry one executable action

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US3] `tests/test_one_action.py`: missing initial receipt in delta, driven through
  dispatch next, seat brief, the Agent guard and receive (FR-005).
- [x] T002 [US3] changed verdict file after its receipt: merge's gate check (FR-006).
- [x] T003 [US3] stale gate receipt at gate: the offered seat passes the Agent guard (FR-007).
- [x] T004 [US3] lost delta seat: a fresh seat is offered and received (FR-007).
- [x] T005 [US3] failed shepherd: retried, then parked for the owner (FR-008).
- [x] T006 [US3] Blocked builder in strict spec mode: the stop passes and the owner is asked
  before its checks; Yes continues it (FR-009).
- [x] T007 [US3] broken config: `config check` and `doctor --fix` pass the hook (FR-010).
- [x] T008 [US3] docs on owner_actions and integrity (FR-011).
- [x] T009 [US1] next and dispatch next agree on polish, a moved checked head and a build not
  done (FR-001, FR-002).
- [x] T010 [US2] next keeps the resolved action; an owner card is the decision (FR-003, FR-004).
- [x] T011 run them, see each fail for the stated reason.

## Phase 2: implementation (green)

- [x] T012 `dispatch.decide`, `next_step` executes it, derive maps it, `_gated_push` reads it.
- [x] T013 `_seats` fresh path; `receive` late initial; fix and delta stop refusing.
- [x] T014 `gate_step`, `build.step`, `resolve_offer` keeps the action, next promotes the card.
- [x] T015 merge reads the receipt.
- [x] T016 `raise_action` shepherd retry.
- [x] T017 `specmode.named` Blocked stop; `build.step` Blocked card.
- [x] T018 hook config failure; docs; ENFORCE sentence.

## Phase 3: polish

- [x] T019 update the existing tests whose expectations encoded the old behaviour; full runs.
