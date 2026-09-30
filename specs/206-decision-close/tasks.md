# Tasks: An answered owner decision clears close, and Stop never traps the session

Test first: run each test task and see it fail for the stated reason before its
implementation task. Test command: `python -m pytest -q` from the worktree root with the
pipeline interpreter; use `-k` for the focused runs.

## Shared reader

- [X] T001 [US1] In `tests/test_decision.py`, add a parametrized test for
  `decision.answered(data, 'D-1')`: no `decision_outcomes`, no record, `{}` record, a
  seat record and a non-dict record give `None`; an owner record
  `{'option': 'defer', 'decided_by': 'owner'}` gives `'defer'`. Fails: no `answered`.
- [X] T002 [US1] Add `answered` to `cli/wuwei/decision.py` as in plan.md section 1.

## Day close (acceptance: close no longer lists it, report and close agree)

- [X] T003 [US1] In `tests/test_stop.py::test_close_owner_decision_table`, add modes:
  `answered` (route D-1, patch `wuwei.integrity._host_confirm` to True, run
  `main(['decision', 'outcome', 'D-1', 'A'])`) expecting 0 on the non-retry column, and
  assert `wuwei.report.build(root)` contains `- D-1: A` while the Stop reason and
  `closing.unresolved(root, [])` name no `D-1` (if `report.build` cannot run in the
  `case` fixture, put the report-and-close agreement assertion in
  `tests/test_decision.py::test_owner_outcome_resumes_linked_item_and_report` instead); `legacy_answered` (write an owner record into
  `decision_outcomes` with `state._write_state(..., reserved=False)` and leave the file at
  `Outcome: pending`) expecting 0; `seat_ledger` (route D-1 as owner, then write a
  `decided_by: 'seat'` record into `decision_outcomes`) expecting 1. Until T014 the
  retry column expects the same codes as the non-retry column. Fails: `answered`
  and `legacy_answered` return 1 with `D-1: pending owner decision`.
- [X] T004 [US1] In `cli/wuwei/closing.py` `unresolved`, skip answered owner decisions
  as in plan.md section 2.

## PR act (acceptance: pr act stops returning owner_decision)

- [X] T005 [US1] In `tests/test_pr_actions.py`, extend the scope-disagreement flow of
  `test_scope_disagreement_creates_decision` into a parametrized test over the owner's
  option: after the first `pr act` creates D-n, route it, record the owner outcome with
  the confirmation patched, then run `pr act` again. `defer`: exit 1 and the JSON is
  `{'action': 'reply', ...}` with `decision` equal to the recorded path and
  `option == 'defer'`. `change` (with `completed_build(root, tree)` first): exit 1 and the
  fix-round prompt contains the reviewer's text. In both, `action != 'owner_decision'`.
  Also assert an unanswered decision still returns `owner_decision` (existing test).
  Fails: both return `owner_decision`.
- [X] T006 [US1] In `cli/wuwei/pr_actions.py` `_thread`, route an answered scope
  decision as in plan.md section 3 and make the fix-request branch `elif`.

## PR disposition (acceptance: disposition accepts an owner-answered decision)

- [X] T007 [US1] In `tests/test_stop.py`, add
  `test_disposition_accepts_owner_answered_decision`: own the PR, write the owner-routed
  D-1, route it, record the owner outcome (confirmation patched), then post the owner
  comment `WUWEI parked {REF} D-1 {DAY} <fingerprint of the current D-1 text>` in the
  fake host and call `pr_actions.record_disposition(root, REF, 'parked', 'D-1', 10)`.
  Expect 0 and a `pr_dispositions` record. Keep
  `test_disposition_requires_owner_routed_decision` `seat_outcome` rejecting. Fails:
  `ValueError ... owner-routed decision without a seat outcome`.
- [X] T008 [US1] In `cli/wuwei/pr_actions.py` `_verify`, reject only a non-owner outcome
  as in plan.md section 3.

## Record shows the outcome

- [X] T009 [US1] In `tests/test_decision.py::test_owner_outcome_resumes_linked_item_and_report`,
  assert the D-3 record now has the line `Outcome: A` and still passes
  `decision.lint`. In `test_owner_outcome_rejects_bad_choice_and_declined_confirmation`,
  assert the record text is byte-identical after the bad choice and the declined
  confirmation. Fails: the record still reads `Outcome: pending`.
- [X] T010 [US1] In `cli/wuwei/commands/decision.py` `owner_outcome`, rewrite the
  `Outcome:` line after the state write as in plan.md section 4, with its `ponytail:`
  comment.

## Cockpit and steward

- [X] T011 [US1] In `tests/test_dashboard.py`, add a test from the
  `test_cockpit_snapshot_reads_pending_records_and_optional_lanes` fixture where
  `state.json` also holds `decision_outcomes: {'D-3': {'option': 'A', 'decided_by': 'owner'}}`
  and the file keeps `Outcome: pending`; expect only `C-2` in `decisions`. Fails: D-3 is
  listed.
- [X] T012 [US1] In `cli/wuwei/commands/dashboard.py` `cockpit_snapshot`, skip answered
  decisions as in plan.md section 5.
- [X] T013 [US1] In `tests/test_steward.py`, add a regression test: with D-1 and D-2
  records and an owner outcome for D-1 in state, `steward.decision_queue(root)` lists only
  D-2. Expected to pass on main (no code change); it pins the steward reader.

## Stop blocks once (acceptance: Stop blocks once, retry exits 0)

- [X] T014 [US2] In `tests/test_stop.py`, update the tests listed in plan.md "Tests
  changed": `test_stop_table` `active_retry` expects 0 and `bad_retry` still 2;
  `test_close_owner_decision_table` expects 0 for every mode when `retry` is True;
  `test_close_command_and_hook_retry` runs `main(['hook', 'Stop'])` first with
  `stop_hook_active: false` (exit 2, stdout JSON `decision == 'block'` and the reason
  names the unresolved PR) and then with `true` (exit 0, empty stdout). In
  `tests/test_pr_ownership.py::test_poll_produces_deadline_stop_and_signal`, pass
  `stop_hook_active=False`. Fails: the retry cases return 1 or 2.
- [X] T015 [US2] In `cli/wuwei/guards/stop.py` `check`, return `(0, '')` when
  `stop_hook_active` is `True` and delete the retry comment, as in plan.md section 6.

## Docs and verification

- [X] T016 Update the "Day close" section of `docs/site/concepts.md` as in plan.md
  section 7.
- [X] T017 Run the full suite; everything passes. Grep the changed files for em-dashes,
  emojis and absolute local paths and remove any.
