# Tasks: base_red, a red check the base shares is not the PR's

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests are in-process: `main(['pr', 'state', REF])` and `main(['pr', 'act', REF])` with
the `case` fixture from `tests/test_stop.py` and the `linked` and `completed_build` helpers in
`tests/test_pr_actions.py`; head `'a' * 40`, base `'b' * 40` (the recorded fake PR). A base
answer is set with `host.results[('checks', 'b' * 40)] = Result(0, [...])`, rows carrying
`'sha': 'b' * 40`. Neutral fixtures only. Run the touched test files after each pair, then the
full suite (`python -m pytest -q`).

## Phase 1: the fake answers per commit (keeps every existing ci_red test as it is)

- [X] T001 Test in `tests/test_pr_actions.py`: with the `case` fixture's host and
  `results['checks']` set to one head row (`'sha': 'a' * 40`, `tests` `failure`),
  `host.checks(REF, 'b' * 40)` returns `Result(0, [])` while `results['pr']` has base
  `'b' * 40` and head `'a' * 40`; after `host.results[('checks', 'b' * 40)] = Result(0, rows)`
  it returns `rows`; `host.checks(REF, 'a' * 40)` returns `results['checks']`; both calls are
  in `host.calls` as `('checks', (REF, sha), None)`. Fails today: the fake returns
  `results['checks']` for every commit.
- [X] T002 Implement the per-commit answer in `Fake.checks` in `tests/fakes/code_host.py`
  (plan: per-commit key first, then an empty list for the `pr` result's `base_sha` when it
  differs from its `head`, then `results['checks']`; record every call).

## Phase 2: base_red (FR-001 to FR-004, US1, US2)

- [X] T003 Test in `tests/test_pr_actions.py`, `test_check_red_at_base_too_is_base_red`:
  head check `audit` `failure`, base check `audit` `failure`. `main(['pr', 'state', REF])`
  returns 0; the printed row has state `base_red`, reason
  `base_red: audit fails at bbbb...b too` (full 40 characters), action `''`, deadline `None`,
  exit 0; `state.read_state(root)['watch']['actions']` has no `REF`. Then
  `main(['pr', 'act', REF])` returns 0, prints nothing, item `A` stays in phase `raised` and
  `state.read_state(root).get('builds', {})['A']` is unchanged (no fix round opened, as
  `build.open_fix` would set phase `fix`); `shepherd.pending(root)` is empty. Fails today: the
  state is `ci_red` and `pr act` opens the fix round.
- [X] T004 Test in `tests/test_pr_actions.py`, `test_base_red_drops_the_ci_red_episode`: run
  `pr state` with the base answer `[]` (state `ci_red`, an episode for `REF` is recorded), then
  set the base answer to `audit` `failure` and run `pr state` again: state `base_red`, no
  episode for `REF`. Fails today: the episode stays `ci_red`.
- [X] T005 Test in `tests/test_pr_actions.py`, parametrized
  `test_a_check_of_the_prs_own_stays_ci_red`: head `audit` `failure` with base answers
  (a) `audit` `success`, (b) `[]`, (c) `audit` `in_progress` with conclusion `None`; and
  (d) head `audit` and `lint` both `failure` with base `audit` `failure` and `lint` `success`.
  Each: state `ci_red`, action `start a fix round`, no `reason` key. Plus: a PR with all head
  checks green (`waiting`) makes no checks call at `'b' * 40` (`host.calls`). Cases (a) to (d)
  pass today; they guard FR-004 and must stay green after T007.
- [X] T006 Test in `tests/test_pr_actions.py`, parametrized
  `test_unreadable_base_is_unmeasured`: head `audit` `failure`; base answer (a)
  `Result(2, None, 'timeout')`, (b) rows with `'sha': 'c' * 40`, (c)
  `Result(0, {'message': 'Not Found'})`; and (d) `results['pr'].data['base_sha'] = None`.
  Each: `main(['pr', 'state', REF])` returns 2 and the row has exit 2 with a reason starting
  `PR state unmeasured:`. Fails today: the state is `ci_red` with exit 1.
- [X] T007 Implement `_base_red` and the two `observe` lines in `cli/wuwei/pr_actions.py`
  (plan). T003 to T006 pass.

## Phase 3: the overnight sweep (FR-006)

- [X] T008 Test in `tests/test_headless_shepherd.py`, next to
  `test_model_work_is_queued_with_its_evidence`, using its `night` fixture: head `tests`
  `failure` and `host.results[('checks', 'b' * 40)]` with `tests` `failure`.
  `shepherd.overnight(root)` returns 0 and writes no `shepherd.overnight` event. Fails after
  T007 without T009: the sweep queues the PR with an empty reason.
- [X] T009 Implement the skip in `overnight` in `cli/wuwei/shepherd.py`
  (`current in ('waiting', 'base_red')`).

## Phase 4: docs and the full run (FR-007)

- [X] T010 Add `base_red` to the 4.2.1 state list and actions in
  `docs/specs/2026-09-24-wuwei-design.md` (plan wording).
- [X] T011 Run `python -m pytest -q`; all pass. Check every file written for em-dashes and
  emojis.
