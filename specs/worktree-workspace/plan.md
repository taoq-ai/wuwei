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

1. In the upward loop, before the `.wuwei/` check, read the `.git` file and the gitdir's `commondir` under
   `contextlib.suppress(OSError, ValueError)`.
2. When the resolved common dir is named `.git` and is a folder, return `find(common.parent)`.
3. Copy to `.claude/wuwei/cli/wuwei/ws.py`. One sentence in SECURITY.md under Hooks.

## Tests

`tests/test_ledger.py`, real git worktrees made under the pytest base temp:
- the worktree and a subfolder resolve to the workspace; `plan show` via `__main__.main`; `hook.main` with the
  worktree as payload cwd hands `handle` the workspace root and its `owner_paths`;
- a worktree whose main checkout has no workspace, and a plain folder, resolve to None.
