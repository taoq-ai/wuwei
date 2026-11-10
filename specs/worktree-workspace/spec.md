# Feature Specification: a linked git worktree resolves to its workspace

**Feature branch**: `fix/1293-worktree-workspace`
**Item**: 1293, tier smart (complex), goal G-2
**Input**: issue #1293. `wuwei plan show <id>` from a git worktree says the item is not in the plan, so gates
launched there judged without the plan record. Lead probe at 8fc0d49b: `ws.find` from two worktrees returns the
worktree (0 plan items, `owner_paths` []), from a third it returns None.

## The promise in my words

`ws.find` is the one function that picks the workspace root for the CLI and every hook. When the search meets a
linked git worktree, it must answer with the workspace of that worktree's main checkout. A `.wuwei/` inside the
worktree (verdicts or scratch a gate left) is never the answer. Outside any workspace the answer stays None.

The acceptance scenarios, restated:

1. A linked worktree holds only `.wuwei/verdicts`. `wuwei plan show <id>` run there prints the workspace's item.
2. A hook payload's cwd is that worktree. The hook gets the workspace root, so the merge door reads the
   workspace's `owner_paths` and ledger rows land in the workspace's ledger.
3. A folder outside any workspace and its worktrees: `wuwei` says "no .wuwei/ here or above", as today.

Outside: a `WUWEI_ROOT` variable, importing rows from a worktree's stray ledger, worktrees of other repositories.

## How this fails

1. A forged `.git` file sends the search to a folder that redirects back, and the hook recurses until it crashes.
   Held: only a common dir that is a folder named `.git` redirects, and a main `.git` is a folder, so one step.
2. A worktree whose main checkout has no workspace silently picks an enclosing, unrelated `.wuwei/`. Held: it
   resolves to None.
3. A submodule's `.git` file (no `commondir`) or an unreadable `.git` raises out of `find`. Held: OSError and
   ValueError fall through to the normal search.

## Requirements

- FR-1: `find` reads `<candidate>/.git` as a file, its `gitdir:` path, and that gitdir's `commondir`, with no git
  process.
- FR-2: a resolved common dir named `.git` that is a folder restarts the search at its parent.
- FR-3: every other case keeps today's upward search for `.wuwei/`.
- FR-4: the runtime stays within +6 lines; the vendored copy matches.
