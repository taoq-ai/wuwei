# Implementation Plan: 864-governed-by-file

**Spec**: `specs/864-governed-by-file/spec.md` | **Branch**: `864-plan-admit` (shared with #868)

## Summary

One rule, one check. `specmode.governing` learns the directory rule; `plan.governed(name,
reference, tree)` is the one governed_by check (shape, then resolution through
`specmode.governing` when the checkout is known); `plan.checkout(root, repos, repo, worktree)`
names that checkout. Propose, set and `dispatch._start` call them.

## Technical Context

Python 3.11+, stdlib only; pytest dev-only. Files: `cli/wuwei/specmode.py`,
`cli/wuwei/plan.py`, `cli/wuwei/commands/plan.py`, `cli/wuwei/dispatch.py`; tests in
`tests/test_plan.py`, `tests/test_dispatch.py`.

## Constitution Check

- I stdlib only: yes. II exits: a shape or resolution failure is a ValueError (exit 2, as
  propose already does); a missing owner Yes is exit 1 (StateError). III one behaviour, one
  function: `plan.governed` is the only governed_by check. IV test first: every change starts
  with a failing test. V ponytail: no new module; the park reuses the #603 park path.
  VII: the owner's card guards `plan set governed_by=`.

## Design

1. `specmode.governing`: after `path = tree / name`, a directory becomes `path / 'spec.md'`.
2. `plan.governed`: replaces the shape check at `plan.py:110` (tree None) and, with a tree,
   calls `specmode.governing(tree, {'governed_by': reference})`, re-raising its first clause
   with the item name and the plan-side fix.
3. `plan.checkout`: the worktree when it is a directory, else the configured repository the
   item names, else the single repository, else None.
4. `plan.propose`: after the repository loop, each candidate with governed_by is checked in
   `checkout(root, repos, row.get('repo'))`.
5. `plan.set_governed_by(item, value)` and `plan set` routing: check first (exit 2), then
   `_owner_confirm`, then record with a `plan.set` event.
6. `dispatch._start`: read the state item; check its governed_by in its checkout; on failure
   return the park command with the fix in the reason.

## Risks

- A brief that once worked with a directory reference now resolves to `<dir>/spec.md`; that is
  the intended rule.
