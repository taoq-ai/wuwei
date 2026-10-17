# Implementation Plan: free runtime lines with no behaviour change and no complexity change

**Branch**: `claude/free-lines-5` | **Spec**: `specs/free-lines-5/spec.md`

## Summary

Free 21 lines in ten runtime modules outside `guards.py`: a merged cache helper, two reused
expressions, three loops as comprehensions, one counter as a set-size difference, one misplaced
import, one single-use path, and nine `x = f()` / `if x is None:` pairs as walrus tests. Prove each
with a differential probe on main and the head and a timing run at 125 KB and 500 KB.

## Technical Context

Python 3.11 stdlib, pytest. Runtime budget 3,000 lines in `cli/wuwei/`, at 2,996 on main d1c3d79.

## Constitution Check

- I. Stdlib only: no import added.
- III. An auditor: no door added or removed; guards.py untouched.
- V. Test first: a refactor with no behaviour change has no new failing test; the suite and the
  differential probe hold it, and mutants show the probe sees each rewrite.
- VI. Budgets: no config key; runtime falls from 2,996 to 2,975.

## Design

| Module | Change | Lines |
|---|---|---|
| board | `rows` reads through `evidence._cached(root, 'board', ..., TTL)`, the same get-or-put | -1 |
| board | `compute` reuses `mine` in the unreadable path and the item loop; the cache key is built in place | -2 |
| report | `import hashlib` joins the sorted stdlib block | -1 |
| report | `learning`'s exception loop is one comprehension | -2 |
| agents | `stale` is one comprehension | -2 |
| upgrade | `items` counts imports as `len(known) - before` | -2 |
| evidence | `verdicts` reads the path in place | -1 |
| hook | walrus in `handle`, `subagent_stop`, `_verdict_problem` | -3 |
| plan | walrus in `mark` | -1 |
| verdict | walrus for the Findings section and each finding | -2 |
| `__main__` | walrus in `_root` and `plan show` | -2 |
| setup | walrus for `.codex/agents` in `doctor` | -1 |

`.claude/` is rewritten by `setup.vendor('.')` from the worktree root.

## Verification

- Full suite with `/root/.local/bin/pytest -q -p no:cacheprovider` on main and on the head.
- Differential probe: a pytest file dropped into `git archive` copies of d1c3d79 and of the head
  writes every output (return values, CLI stdout, stderr and exit codes, workspace files, ledger
  rows) to JSON under a fixed clock and clone id; the two files must be byte-identical.
- Mutants of the head (board `open_items`, board without `TTL`, report without `approved`,
  upgrade on `>=`, agents with `and`) each change probe output.
- Timing: each rewritten function at its worst shape at 125 KB and 500 KB, best of 3 or 5, two
  alternating runs per tree; the head's best over its base's best stays at or under 1.20.

## Rollback

Revert the commit.
