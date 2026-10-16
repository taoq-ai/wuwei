# Implementation Plan: the board links every item a PR names, closes a just-merged item, and shows uncounted verdicts

**Branch**: `claude/board-links` | **Spec**: `specs/board-links/spec.md`

## Summary

Add `evidence.items_named(body)`. In `board.compute`, match PRs to items through every named id,
read the merged list fresh when an open item has no open PR, and append `evidence.uncounted` to
no-PR rows.

## Technical Context

Python 3.11 stdlib, pytest with the `FakeGh` fixture. The runtime is at 2,939 of 3,000 lines.

## Constitution Check

- I. Stdlib only: yes.
- II. Evidence over steps: the board reads the merged list and the verdict files themselves.
- III. An auditor: no new door; the board reports gaps, never commands.
- V. Test first: three new tests in `tests/test_watch.py` ran red before the change.
- VI. Budgets: runtime 2,939 to 2,949; no config key.

## Design

- `evidence.items_named(body)`: `ITEM.findall(body or '')`.
- `board.names(root, pr, repo, item_id)`: true when the body names the item, or, when the body names
  none, when `item_for` resolves to it.
- `board.compute`: `linked` and `done` use `names`. The merged list's cache age is -1 (always
  fresh) when any open item in the repository has no open PR, else 300 seconds. A no-PR row's gaps
  are the first gap plus `evidence.uncounted(root, item_id)`.
- Re-vendor `.claude/` with `setup.vendor('.')`.

## Rollback

Revert the commit; the board returns to first-item linking and the 300-second merged cache.
