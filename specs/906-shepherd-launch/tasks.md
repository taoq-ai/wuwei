# Tasks: the shepherd duty is an executable launch

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: tests first (red)

- [X] T001 [US1] `tests/test_derive.py`: a due shepherd duty on a raised item (claimed or not) is one
  seated `shepherd` launch; none once `shepherd-<item>-<revision>` is registered; a newer activity
  launches again; replace the claimed `pr` arm test.
- [X] T002 [US3] `tests/test_derive.py`: `as_of` on `duty.done` decides the due test; the duty
  command refuses `--evidence` for shepherd and keeps `--skipped`.
- [X] T003 [US1] `tests/test_next.py`: three `next --json` calls on one revision give the brief
  command, the seat launch, then no shepherd launch; the duty list has no shepherd entry.
- [X] T004 [US2] `tests/test_pr_actions.py`: replies to questions holding "change", "scope" and
  "instead" post; plain `pr act` opens nothing; `--fix` opens a round with the thread and reason;
  `--scope` asks the card, Yes opens the round, No prints the defer reply; two threads by
  `--thread`; a comment landing before the reply leaves the named thread's reply in place; a thread
  no longer owed is refused.
- [X] T005 [US3] `tests/test_pr_actions.py`: a read with nothing owed records the due shepherd
  duty once, with `as_of`.
- [X] T006 Run the new tests and see each fail for the right reason.

## Phase 2: implementation (green)

- [X] T007 `derive.revision`, the shepherd record and prompt, `as_of`, the offers arm, `seated`.
- [X] T008 `dispatch._seat`, `raise_action` on it, `shepherd_action`, `resolve_offer`.
- [X] T009 `pr_actions`: delete `SCOPE` and `FIXES`; `launch`; `_owed` list; `_thread`; `act`
  flags; `observe` completion; `evaluate` passes `as_of`.
- [X] T010 `commands/pr.py` flags; `commands/duty.py` refusal; `commands/next.py` duty filter.

## Phase 3: docs and agents

- [X] T011 Shepherd charter (answers through `pr act --thread`), `wuwei agents build`.
- [X] T012 `docs/site/reference.md` (pr act flags, duty), `concepts.md` duties, `agent.md`,
  `daily.md`.

## Phase 4: verify

- [X] T013 Every test file importing a changed module, plus `test_invariants`, `test_docs`,
  `test_charters`; the derive, next, pr_actions and code_host files under Python 3.11.

## Phase 5: review fix round (906-findings F1 to F7)

- [X] T014 F1: tests first (a moved head relaunches, a stopped seat leaves the duty row, a running
  seat hides it); revision key carries the head; next keeps the duty row unless a shepherd launch
  is offered or a shepherd seat runs.
- [X] T015 F3: tests first (no second seat beside a running one, the viewer's comment is not
  activity); `derive.shepherding`; `viewer{login}` in `_PULLS`.
- [X] T016 F4: test first (a P1 bot thread replied to and fixed by id); `_owed` includes `bot-p1`.
- [X] T017 F5: test first (a merge on the host wakes pr wait); merged or closed PR items are steps.
- [X] T018 F6: test first (a replayed scope Yes asks again); the card token carries the round count.
- [X] T019 F7: planner charter stays 2.5.0; the coordinator bumps it at rebase after #901.
- [X] T020 Delta D1 to D3: tests first (a fix round with due activity waits; a teammate author's follow-up counts; a reply to a P1 bot thread is refused); duty row only for a raised item with nothing offered or in flight.
