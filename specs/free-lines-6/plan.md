# Implementation Plan: free runtime lines outside the guard, hook, board and evidence modules

**Branch**: `leone/free-lines-6` | **Spec**: `specs/free-lines-6/spec.md`

## Summary

Free 23 lines in three runtime modules: eleven trailing `return 0` lines carried by one `or 0` in
`main()`, a one-line wrapper with one caller (`plan.restore`), `ws.find`'s loop as the `next(...)`
form, and two `try/except/pass` blocks in `ws` as `contextlib.suppress`. Prove each with a
differential probe on main and the head and a mutant per rewrite.

## Technical Context

Python 3.11 stdlib, pytest. Runtime budget 3,400 lines in `cli/wuwei/`, at 3,396 on main bcdfc1b.

## Constitution Check

- I. Stdlib only: no import added (`contextlib` is already imported in `ws`).
- III. An auditor: no door added or removed; guards.py and hook.py untouched.
- V. Test first: the one function removed gets a CLI test that pins its behaviour, green on main
  before the removal and on the head after. The rest adds no behaviour; the suite and the
  differential probe hold it, and mutants show the probe sees each rewrite.
- VI. Budgets: no config key; runtime falls from 3,396 to 3,373.

## Design

| Module | Change | Lines |
|---|---|---|
| `__main__` | `main()` returns `args.func(args) or 0`; eleven commands drop their trailing `return 0` | -11 |
| plan | `restore` goes; `wuwei plan restore` calls `plan.mark(root, id, 'open', 'restored')` | -5 |
| ws | `find` returns `next((candidate ...), None)` over the same lazy sequence | -3 |
| ws | `cache_get` and `cache_prune` use `contextlib.suppress` with the same exception tuples | -4 |

`.claude/wuwei/cli/wuwei/` takes the three changed files byte for byte.

## Verification

- Full suite with `/root/.local/bin/pytest -q -p no:cacheprovider` on main and on the head.
- Differential probe: a pytest file dropped into `git archive` copies of bcdfc1b and of the head
  writes every output to JSON under a fixed clock and clone id: 73 CLI calls (every subcommand and
  its error paths, return value and type, stdout, stderr, the ledger rows and plan after), 72
  `cache_get` cases, 4 `cache_prune` rounds and 33 `find` cases. The two files must be
  byte-identical.
- Mutants of the head, each in its own archive: `main` without `or 0`, restore with a blank reason,
  `cache_get` suppressing OSError only, `cache_get` with `<`, `cache_prune` without the suppress,
  `find` defaulting to `''`, `find` returning the start. Each must change the probe output.
- Complexity: each rewrite keeps its loop shape (`find` stays a lazy walk up the parents that stops
  at the first match), so no timing run is needed.

## Rollback

Rollback: revert the commit.
