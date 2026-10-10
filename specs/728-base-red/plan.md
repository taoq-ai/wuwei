# Implementation Plan: base_red, a red check the base shares is not the PR's

**Branch**: `728-base-red` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

In `pr_actions.observe`, when `classify` says `ci_red`, read the checks at the PR's
`base_sha` with the existing `merge.checks_at` (#668) and, when every red head check is red
there too, make the row `base_red` with a reason naming the checks and the base commit.
`base_red` has no `ACTIONS` entry, so the existing "no action" path already drops the episode,
sets exit 0 and keeps `pr act`, the headless shepherd and the stop check from asking for a fix
round. One shared test fake learns to answer checks per commit.

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, port operation, config key, state
key or event kind. One extra code host read, only for a PR that is `ci_red` at its head.

## Constitution Check

- I stdlib only: yes.
- II exits: a failed or damaged base read raises inside `observe`; `evaluate` already turns it
  into the row's exit 2 `PR state unmeasured:` reason, and the watch poll already logs it as
  `watch: read-failed`. Never cleared without evidence.
- III one behaviour, one function: the comparison lives in one helper in `pr_actions.py`,
  called only from `observe`, which every PR state consumer goes through.
- IV test first: tasks put each test before its code.
- V ponytail: reuse `merge.checks_at` and `merge.sha`; no new port, no new ledger, no ACTIONS
  row, no change to `classify`.
- VII: no guard, refusal or merge rule changes. `merge.green` still refuses a red check, so a
  `base_red` PR never merges until its checks are green.

## Changes, by file

### `cli/wuwei/pr_actions.py`

- New helper next to `classify` (about eight lines):

  ```python
  def _base_red(host, ref, measured, root):
      """#728: the base_red reason when every red head check is red at the base commit too."""
      from wuwei import merge
      red = lambda checks: {c['name'] for c in checks if c['state'] == 'completed'
                            and c['conclusion'] not in ('success', 'neutral', 'skipped')}
      base = merge.sha(measured['pr']['base_sha'])
      names = red(measured['checks'])
      if names and names <= red(merge.checks_at(host, ref, base, root)):
          return f'base_red: {", ".join(sorted(names))} fails at {base} too'
      return None
  ```

  The red predicate is the one `classify` uses (`pr_actions.py:126-136`); keep it identical.
  `merge.checks_at` validates every base row (sha equals the base, known state and
  conclusion) and raises `ValueError` otherwise; `merge.read` refuses an error body.
- `observe` (`pr_actions.py:151`): right after `current = classify(...)` (line 153):

  ```python
  reason = _base_red(host, ref, measured, root) if current == 'ci_red' else None
  current = 'base_red' if reason else current
  ```

  and after the `row = {...}` line (line 160): `if reason: row['reason'] = reason`.
  Setting `current` before `row` and `event` are built makes the row state, the `pr.action`
  event payload state and the ACTIONS lookup (line 195) all `base_red`; the lookup returns
  `('', {})`, so the existing `else: actions.pop(ref, None)` drops any earlier `ci_red`
  episode and `row['exit']` is 0. Nothing else in `observe` changes.

### `cli/wuwei/shepherd.py`

- `overnight` (`shepherd.py:584`): `current == 'waiting'` becomes
  `current in ('waiting', 'base_red')`, so the sweep neither queues the PR with an empty reason
  nor reads reply evidence for it.

### `tests/fakes/code_host.py`

- `Fake.checks` answers per commit: `self.results[('checks', sha)]` when the test set one;
  otherwise, for the current `pr` result's `base_sha` when it differs from its `head`, an empty
  list (no checks at the base, so an existing `ci_red` test stays `ci_red`); otherwise
  `results['checks']` as today. Record the call in `self.calls` in every branch. Verified
  during spec work in a scratch copy: with this fake and the `observe` change the full suite
  passes; without the fake change 15 existing `ci_red` tests (in `test_pr_actions.py`,
  `test_pr_ownership.py`, `test_headless_shepherd.py`, `test_watch.py`,
  `test_worktree_command.py`) turn exit 2, because the base read gets rows for the head. Keying
  the default on a fixed `b * 40` instead breaks two `test_watch.py` tests that move the head
  to `b * 40`; key it on the `pr` result.

### `docs/specs/2026-09-24-wuwei-design.md`

- 4.2.1 state list (line 205) and actions (line 210): add `base_red` (every red check also
  fails at the PR's base commit: no action, the item waits; `pr state` names the checks and the
  base commit; #728).

## Shared helpers reused

- `merge.checks_at` (`cli/wuwei/merge.py:106`): the validated checks read at any commit.
- `merge.sha` (`cli/wuwei/merge.py:32`): fails closed on a missing or malformed base SHA.
- The existing no-action path in `observe` (`ACTIONS.get(..., ('', {}))`, `actions.pop`).
- `evaluate`'s per-PR `watch.ERRORS` handling for the unmeasured row.

## What must not change

- `classify` and its signature; `ACTIONS`, `shepherd.HEADLESS`, `listen.notify`.
- `ci_red` behaviour whenever any red head check is not red at the base, including the fix
  round feedback in `_fix` (it lists every red head check).
- `watch.evidence`, `watch.snapshot` and `watch.facts`: the watch's change summaries
  (`check ci failed`) stay factual.
- `merge.execute`, `merge.green`, `merge.fixes_base` and the #668 soak skip.
- `check()` and day close: a `base_red` PR is treated as `waiting` is (not overdue; must still
  be merged, parked or carried at close).
- No read of the base for any state other than `ci_red`.

## Test files

- `tests/test_pr_actions.py`: the new behaviour, through `main(['pr', 'state' | 'act', REF])`
  with the `linked` and `completed_build` helpers and `host.results[('checks', 'b' * 40)]`.
- `tests/test_shepherd.py` or `tests/test_headless_shepherd.py`: the overnight skip, next to
  the existing `test_model_work_is_queued_with_its_evidence` case.
- `tests/fakes/code_host.py`: the per-commit answer (exercised by the tests above and by the
  existing suite).
