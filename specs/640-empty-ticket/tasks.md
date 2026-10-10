# Tasks: an empty ticket field is absent, not a rejected proposal

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the fixtures in `tests/test_plan.py` (`root`, `proposal`, `two`, `tracked`) and
neutral item names; no test reaches git or the network. Run `tests/test_plan.py`, then the
full suite with `python -m pytest -q`.

## Phase 1: an empty optional field is absent (FR-001; US1)

- [X] T001 Test in `tests/test_plan.py`, `test_empty_optional_fields_are_absent`:
  `plan.propose(two(A={'ticket': '', 'tier': None, 'docs': ''}, B={'ticket': None,
  'tier': '  '}), root)` succeeds; the saved `.wuwei/days/2026-09-28/proposal.json`
  candidates carry none of `ticket`, `tier`, `docs`; then `plan.approve(['A', 'B'], root,
  goals_confirmed=True)` succeeds, `state.read_state(root).get('tickets', {}) == {}` and neither item has a
  `tier`. Fails today with `A: invalid ticket`.
- [X] T002 Test in `tests/test_plan.py`, `test_add_discovery_candidate_with_empty_ticket`:
  following `test_intraday_budget_counts_morning_rank_size`, write a discovery candidate `B`
  with `'ticket': ''`, call `plan.add('B', root)`; it is admitted and
  `state.read_state(root).get('tickets', {})` has no `B`. Fails today with `B: invalid
  ticket`.
- [X] T003 Implement the normalisation loop in `_proposal` in `cli/wuwei/plan.py` (plan,
  Design), popping in place. T001 and T002 pass.

## Phase 2: the ticket refusal names the form (FR-002; US2)

- [X] T004 Test in `tests/test_plan.py`, `test_invalid_ticket_names_item_field_and_form`:
  `plan.propose(two(A={'ticket': 'not a ticket!'}), root)` raises `ValueError` whose `str()` (checked with `in`, not `match`, since it holds a regex)
  contains `A: invalid ticket 'not a ticket!'`, `plan.TICKET` and `owner/repo#12`; no
  `plan.md` is written. Fails today on the missing value and pattern.
- [X] T005 Replace the ticket refusal message in `_proposal` in `cli/wuwei/plan.py` (plan,
  Design). T004 and the existing `test_invalid_candidate_ticket_is_unrun` pass.

## Phase 3: reference and full suite (FR-004, SC-002)

- [X] T006 Add the `ticket` sentence to the candidate paragraph of the Lead plan JSON section
  in `docs/site/reference.md` (plan, Design).
- [X] T007 Run `python -m pytest -q`; all green. Check the changed files for em-dashes and
  emojis.
