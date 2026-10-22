# Feature Specification: free runtime lines outside the guard, hook, board and evidence modules

**Feature branch**: `leone/free-lines-6`
**Item**: free-lines-6, tier full, goal G-2
**Input**: the runtime sits at 3,396 of its 3,400 lines on main bcdfc1b. Items 1223 (+1 to +2) and
1211-confirm (+3 to +5) are in flight; 1222 (+2 to +3), 1221 (+1 to +3) and flow-board (+8 to +12)
come next. This item frees the room on its own, outside the files those items edit.

## The promise in my words

Shrink `cli/wuwei/` by at least 16 lines, aiming for 20, without changing any CLI flag, message,
exit code, ledger row or other output, and without making any function slower in its order of
growth. `guards.py`, `hook.py`, `board.py` and `evidence.py` stay byte-identical to main: they are
owner paths or edited by parallel items. `wuwei evidence --record` stays, since the reference docs
and the README document it. The vendored copy under `.claude/wuwei/cli/wuwei/` changes with the
tree, byte for byte. If fewer than 16 lines go without golf, the item stops there and the budget
becomes the owner's decision.

The preferred sources, in order: dead code or a wrapper no second caller needs, repeated lines a
single place can carry, then idioms the modules already use (`contextlib.suppress`, `next(...)`).
No `;` joins and no squeezed lines.

The acceptance scenarios, restated:

1. On main and on the head, the full suite and a differential probe over each rewritten
   function's inputs give identical outputs, ledger rows and exit codes.
2. `wc -l cli/wuwei/*.py` at the head is at least 16 lines below main.
3. The diff touches none of `guards.py`, `hook.py`, `board.py` and `evidence.py`.

## How this fails

1. A command whose last statement used to be `return 0` now returns `None`, and some caller reads
   the function's value instead of `main()`'s. If a test or module called `cmd_*` directly, or
   `main()` passed `None` through, an exit code would change from 0 to `None` (still a zero exit
   from `SystemExit(None)`, but a different value for a Python caller). Guarded by `or 0` in
   `main()`, a grep showing `args.func(args)` is the only caller of any `cmd_*`, and the probe
   recording the value and its type for 73 CLI calls; a mutant without `or 0` changes the output.
2. `wuwei plan restore` loses the `restored` reason or the case-insensitive id match once
   `plan.restore` goes. Guarded by the CLI test (`plan restore i-1` prints `I-1 open again`, the
   ledger row reads `{'id': 'I-1', 'reason': 'restored'}`, an unknown id exits 2 with its message)
   and the probe; a mutant with a blank reason changes the output.
3. `contextlib.suppress` swallows a different set of errors than the `try/except/pass` it
   replaces, or `ws.find` returns a different value when no folder matches. Guarded by the probe's
   cache cases (fresh, stale, the 60 s boundary, bad JSON, binary, empty, `null`, a 100,000-deep
   array that raises RecursionError on both trees, a folder and a dangling link at the cache name,
   a missing file) and its find cases (`None`, relative, symlinked, a `.wuwei` file, no match);
   mutants that narrow the suppress, drop it, flip `<=` or change the `next` default each change
   the output.

## Requirements

- FR-001: `cli/wuwei/*.py` totals 3,380 lines or fewer (16 or more freed from 3,396).
- FR-002: `guards.py`, `hook.py`, `board.py` and `evidence.py` are byte-identical to main.
- FR-003: every probe output is byte-identical on main and on the head.
- FR-004: no rewritten function changes its order of growth.
- FR-005: `.claude/wuwei/cli/wuwei/` matches `cli/wuwei/` byte for byte.
- FR-006: no new line over 150 characters, no `;` join.

## Clarifications

### Session 2026-10-22

- Q: Is dropping the trailing `return 0` from eleven commands line golf? A: No. The lines are
  repeated boilerplate, not crammed logic: one `or 0` in the dispatcher carries them, and every
  command that still returns a code (`evidence`, `doctor`, `verify`, `agents`, the error branch of
  `sync`) keeps it. `hook.main` returns 0 on every path, so its value is unchanged.
- Q: Does the `plan.restore` test change count as changing a test of the old contract? A: Yes, and
  it is the point: the function goes, so its unit test moves to the public surface it served
  (`wuwei plan restore`) and pins more than before (message, reason, ledger row, error path).
- Q: Does `cache_get` read through `ws.read_json`, which already exists? A: No. `read_json` also
  catches RecursionError, so a deeply nested cache file would return `None` where main raises: a
  behaviour change. The probe pins that case on both trees.
- Q: Do `gh._author` (used once) and `plan.approve`'s two-pass loop go too? A: No. Inlining
  `_author` makes the thread count line harder to read and shifts a `None` edge; folding the
  approve loop changes the result for a hand-edited plan with a duplicated id. Neither is needed.

## Assumptions

- The cmd functions may end without a return when they succeed: `main()` documents that with a
  short comment. Overturned if the owner prefers an explicit code per command; the item then frees
  12 lines, and the budget question goes to the owner.
- Removing `plan.restore` from the module's Python surface is not a breaking change: the CLI is
  the declared interface, and no other module, skill or doc names the function (grep over the
  repository outside `.git` and `.claude`). Overturned if an external caller imports it.

## Rollback

Rollback: revert the commit. No data, config or contract depends on the refactor.
