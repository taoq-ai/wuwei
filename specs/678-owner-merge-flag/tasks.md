# Tasks: an item-level owner_merge flag

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real `gh`: merge tests use the `Fake` code host of
`tests/test_merge.py`, the adapter test uses the recorded `gh` replay. Run only the touched
test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: the hold in merge.check (FR-001, FR-002, US1)

- [X] T001 Test in `tests/test_merge.py`: `merge.owner_hold` on an item without the key, with
  `value` false, with `value` true (returns `('owner', '2026-09-29')`), and with malformed
  records (`'yes'`, `{'value': 'true', ...}`, missing `by`) raising `ValueError` with `damaged`.
- [X] T002 Test in `tests/test_merge.py`: with `items.item-7.owner_merge = {value: true, by:
  owner, at: 2026-09-29T...}` on the clean `case`, `check` exits 1 with `owner merges:
  owner_merge set by owner on 2026-09-29; clear it with bin/wuwei plan set item-7
  owner_merge=false`; with `merge.auto = false` too the reason is still the owner line (it runs
  first); `execute` exits 1 with the owner line, writes `merge.policy_blocked` and never calls
  the host `merge`; a malformed record is exit 2.
- [X] T003 Implement `LABEL`, `owner_hold` and the refusal at the top of `check` in
  `cli/wuwei/merge.py` (read the state once, moved up from line 231).

## Phase 2: the record and its writer (FR-003, FR-006, US2, US3)

- [X] T004 Test in `tests/test_plan.py`: `plan set item owner_merge=true` through `main` writes
  `{value: true, by: owner, at}` and a `plan.set` event `{item, owner_merge: true, by: owner}`;
  with `WUWEI_SEAT_ROLE=builder` `by` is `builder`, with only `WUWEI_SESSION_ID` it is
  `planner`; `owner_merge=false` keeps the record with `value: false`; an unknown item exits 1
  and `owner_merge=maybe` exits 2, both writing nothing; the unknown-assignment message names
  `owner_merge` (update the assertion at `tests/test_plan.py:554`); the gate widget's `Change
  something` description names `owner_merge=true`. No PR is linked, so no host call.
- [X] T005 Test in `tests/test_merge.py`: `state.set_state('items.item-7.owner_merge', ...)`
  raises `StateError` matching `reserved; written by wuwei plan set`.
- [X] T006 Implement `plan.set_owner_merge` and the `gate_widget` sentence in
  `cli/wuwei/plan.py`, the route and help text in `cli/wuwei/commands/plan.py`, and the
  `owner_merge` producer in `cli/wuwei/state.py`.

## Phase 3: who may set and clear (FR-004, US3)

- [X] T007 Test in `tests/test_owner_actions.py`, beside `test_seat_records_a_docs_value`: from
  a builder seat and from the planner, `bin/wuwei plan set X owner_merge=true` passes `bash`
  and the hook; `bin/wuwei plan set X owner_merge=false`, `... owner_merge=true spec=skipped`,
  `... owner_merge=true --reason x`, `... $A owner_merge=true`, `... X owner_merge=$V` and
  `echo owner_merge=true | xargs bin/wuwei plan set X` are refused.
- [X] T008 Implement `_seat_owner_merge` and the reason sentence in
  `cli/wuwei/guards/protect_state.py`.

## Phase 4: the PR record (FR-005, US4)

- [X] T009 Test in `tests/test_code_host.py` (and the recording in
  `tests/fixtures/code_host/recordings.json`, the contract row in `tests/test_adapters.py`):
  `label('acme/widget#7', 'owner-merge', True)` posts to `issues/7/labels` and returns
  `{'labels': ['owner-merge']}`; removal issues the DELETE and a `(HTTP 404)` reads as absent;
  `label(ref, 'other', True)`, `label(ref, 'owner-merge', 'yes')` and a bad ref never spawn
  `gh`; the write failure table covers `label`.
- [X] T010 Implement `label` in `adapters/code_host/github.py` (operation and `_run`
  allowlist) and `adapters/code_host/none.py`, the `registry.PARAMETERS` entry in
  `cli/wuwei/registry.py`, and the method on `tests/fakes/code_host.py`.
- [X] T011 Test in `tests/test_plan.py` (or `tests/test_merge.py` on its `case`, where item-7
  links `REF`): `plan set item-7 owner_merge=true` calls the fake `label(REF, 'owner-merge',
  True)`, clearing calls it with `False`; a failing `label` result exits 2 naming the rerun
  while the state holds `value: true`.
- [X] T012 Test in `tests/test_shepherd.py` (the existing `raise_pr` fixture): a flagged item's
  raise sends a body ending with `Owner merges: owner_merge set by owner on <date>` to
  `create_pr` and calls `label` once; an unflagged raise does neither.
- [X] T013 Implement the label call in `plan.set_owner_merge` (`cli/wuwei/plan.py`) and the body
  line and label call in `shepherd.raise_pr` (`cli/wuwei/shepherd.py`).

## Phase 5: the invariant (FR-007, US1, US2)

- [X] T014 Test in `tests/test_invariants.py`: `i36` (READS `()`, memoized) checks
  `merge.owner_hold` on a set, cleared, absent and malformed record; add it to `INVARIANTS`
  and `READS`, and a `BROKEN` row `owner_merge ignored` that patches `merge.owner_hold` to
  return `None`. Add `test_owner_merge_holds_on_every_path(case, path, flag)`, one table:
  path in `merge check` (`merge.check`), `wuwei merge` (`main(['merge', '7'])` from the repo
  dir), `pr act` (`pr_actions.act` with `pr_actions.evaluate` patched to one `approved` row),
  `pr guard` (`guards.pr.check` on `gh pr merge 7`) and `overnight shepherd`
  (`shepherd.overnight` with `pr_actions.evaluate` patched the same way and the real
  `merge.check`); flag in `set` and `cleared` (set, then `plan.set_owner_merge('item-7',
  'false')`). Set: every path's reason or `shepherd.overnight` event names `owner merges:
  owner_merge set by` and no host `merge` call happens, also with a `today` merge grant.
  Cleared: `check` exits 0, `wuwei merge` calls the host `merge` once, the overnight event
  reason is `merge cleared by policy; ...`, and no reason names the flag. Fails until the 9.2
  row exists (`test_table_matches_the_checks`).
- [X] T015 Add row I37 to design 9.2 in `docs/specs/2026-09-24-wuwei-design.md` (text in
  plan.md).

## Phase 6: docs and close

- [X] T016 Add the owner_merge paragraph to `docs/site/daily.md` near the `plan set`
  paragraphs (around line 344).
- [X] T017 Run the full suite; check every touched file for em-dashes and emojis.
