# Implementation plan: worktree-workspace

**Spec**: `specs/worktree-workspace/spec.md`
**Item**: 1293, tier smart, goal G-2

## Technical context

- `cli/wuwei/ws.py` `find(start)`: the first folder from start upward holding `.wuwei/`. Callers:
  `__main__._root`, `__main__` doctor, `hook.main` (payload cwd), `sync.py`.
- A linked worktree's `.git` is a file `gitdir: <main>/.git/worktrees/<name>`; that folder's `commondir` holds
  `../..`, the main `.git`.
- Runtime at the base: 3,949 lines; budget +6.

## Design

1. One pass up from start. At each candidate, read `.git` and the gitdir's `commondir` only when each is a
   regular file, under `contextlib.suppress(OSError, ValueError)`.
2. At the first candidate whose resolved common dir is named `.git`, the scan starts at the nearest `.wuwei/` at
   or above the main checkout. With none, it starts at the worktree's parent. The pass stops there.
3. Return the nearest `.wuwei/` from that point upward, or None. No recursion.
4. Copy to `.claude/wuwei/cli/wuwei/ws.py`. One sentence in SECURITY.md under Hooks.

## Tests

`tests/test_ledger.py`, real git worktrees made under the pytest base temp:
- the worktree and a subfolder resolve to the workspace; `plan show` via `__main__.main`; `hook.main` with the
  worktree as payload cwd hands `handle` the workspace root and its `owner_paths`;
- a worktree whose main checkout has no workspace and nothing above, and a plain folder, resolve to None;
- round 2: a planted `.git` in a workspace subfolder, another repository's worktree inside the workspace, a
  forged commondir loop, FIFO `.git` and `commondir`, and the nearest of two worktrees.
