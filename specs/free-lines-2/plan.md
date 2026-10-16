# Implementation Plan: the test-only replay helper leaves the runtime and two cache copies fold into evidence._cached

**Branch**: `claude/free-lines-2` | **Spec**: `specs/free-lines-2/spec.md`

## Summary

Move `replay.replay` into `tests/test_replay.py`, fold `board._list` and the cache read in
`guards._default` into `evidence._cached`, inline `evidence.items_named` at its one caller, and
re-vendor `.claude/`.

## Technical Context

Python 3.11 stdlib, pytest. The runtime is at 2,996 of 3,000 lines on main 8ea4192.

## Constitution Check

- I. Stdlib only: yes; no import added to the runtime.
- II. Evidence over steps: the push door still reads the default branch from the code host.
- III. An auditor: no new door, no route change; `tests/fixtures/routes.json` reads as recorded.
- V. Test first: the new structural test ran red on main; the behaviour pins ran green on main
  and stay green after.
- VI. Budgets: runtime falls from 2,996 to 2,962; no config key.

## Design

- `cli/wuwei/replay.py`: delete `replay()` and `import datetime`.
- `tests/test_replay.py`: add `replay_case()` (the old body), import `datetime`, `json`, `shutil`,
  `evidence` and `gh`; call sites use `replay_case`. Add a test that no runtime module defines the
  removed helpers, and a test that `wuwei evidence --record DIR` writes `DIR/case.json`.
- `cli/wuwei/board.py`: delete `_list`; `compute` calls
  `evidence._cached(root, f'prs-{key}', lambda: gh.open_prs(repo), TTL)`; `names` calls
  `evidence.ITEM.findall(pr.get('body') or '')`.
- `cli/wuwei/evidence.py`: delete `items_named`.
- `cli/wuwei/guards.py`: `_default` returns the cached default branch through `evidence._cached`
  when a repository is known, else `{'main', 'master'}`, and `{'main', 'master'}` on `GhError`.
- `tests/test_guards.py`: a lookup error refuses a push to main and caches nothing; a cached
  `trunk` refuses its push with no gh call.
- `.claude/`: rewritten by `setup.vendor('.')`.

## Rollback

Revert the commit. Cache names and ages are unchanged, so cached files stay valid either way.
