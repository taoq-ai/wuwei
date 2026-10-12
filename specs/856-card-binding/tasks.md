# Tasks: an Owner step answer binds by the card's question, not its option text

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_card_confirms.py`: `test_issue_856_a_shortened_option_counts`
  (replaces the #831 F6 test); red.
- [x] T002 [US2] `tests/test_card_confirms.py`: `test_issue_856_adjacent_keys_answer_in_one_round`;
  red: the second key refuses.
- [x] T003 [US3] `tests/test_card_confirms.py`: `test_issue_856_a_reworded_question_names_the_mismatch`; red.

## Phase 2: implementation (green)

- [x] T004 `owner_topic(question, reply='')`, `owner_answer(root, command, token='')` and their
  callers (FR-001, FR-004).
- [x] T005 `record_gate` records the question-and-reply topic and the token topic (FR-001, FR-003).
- [x] T006 `needs_owner` mismatch line (FR-003).
- [x] T007 `config.offer(identity=)`; `_edit` passes the command (FR-002).
- [x] T009 review F2: `owner_answer` spends a Yes after `owner.approved`; the close hold reads
  without spending (`test_a_yes_is_spent_once`, `test_a_config_yes_never_undoes_a_later_owner_change`,
  the hold line in `test_close_parked.py`; FR-005).
- [x] T010 review F4: the command-part topic and hint
  (`test_issue_856_a_reworded_card_without_a_token_names_the_mismatch`; FR-006).

## Phase 3: verification

- [x] T008 Existing card, sessions, answers and config tests updated to the new signatures; the
  pipeline venv and 3.11 runs.
