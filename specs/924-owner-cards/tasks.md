# Tasks: an owner-approved Owner step applies when run again

**Input**: [spec.md](spec.md), [plan.md](plan.md), [../856-card-binding/tasks.md](../856-card-binding/tasks.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_card_confirms.py`: `test_issue_924_a_yes_on_the_shortened_field_card_applies_when_run_again`
  (the field card through `main`); red: exit 1 with the same refusal.
- [x] T002 [US2] `tests/test_card_confirms.py`: `test_every_refusal_says_where_the_answered_command_applies`; red.
- [x] T003 [US3] `tests/test_card_confirms.py`: `test_a_pty_wrapped_run_without_an_answered_card_is_refused`;
  red against the first build's prompt (exit 0, applied).

## Phase 2: implementation (green)

- [x] T004 `owner.approved` on approval (FR-002); `signal.py` silent tier.
- [x] T005 the refusal clause (FR-003).
- [x] T006 review F1: no approval path other than the card (FR-004).
- [x] T007 design 9.1 amendment (for owner review), concepts.

## Phase 3: verification

- [x] T008 Changed modules' test files plus invariants and docs on the pipeline venv; card,
  session, config and pr_actions files on 3.11.
