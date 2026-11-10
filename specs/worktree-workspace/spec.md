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

Round 1 called 1 and 2 held. The gates proved both wrong and found 3 and 4. Round 2 closes each one (tasks.md
Phase 4).

1. A forged `.git` file whose commondir names a `.git` folder below it made the old recursive `find` loop until
   RecursionError, so PreToolUse exited 2 on every call. Held now: one pass, no recursion. The pass finds the
   nearest worktree `.git` file, then scans upward once from that main checkout.
2. A redirect to a main checkout with no workspace returned None, so every hook skipped its doors. The cases were
   a forged nested worktree, a `.git` file planted in a workspace subfolder, and another repository's worktree
   inside the workspace. Held now: the search goes on above the worktree and reaches the enclosing workspace.
3. A FIFO at `.git` or `commondir` hung `read_text`. Held now: each is read only when `is_file()`.
4. A `.wuwei/` in a worktree subfolder won over the redirect. Held now: the worktree `.git` file is found before
   any `.wuwei/` is checked.
5. A submodule's `.git` file (no `commondir`) or an unreadable `.git` raises out of `find`. Held: a missing file
   reads as empty, and OSError and ValueError fall through to the normal search.
6. Round 2 read `.git` files in every ancestor before it checked any `.wuwei/`. A `.git` file or a lone
   `commondir` planted above the workspace then sent its own sessions to None or to a seat-made workspace. A git
   workspace cloned inside another repository's worktree also resolved to None. Held now (round 3): the
   look-ahead ends at the nearest folder holding a `.git` entry of any kind or a `.wuwei/config.toml`.

Residual, as on main: a forged `.git` can still point at a workspace the seat made, or at another real
workspace. The name-based ledger and config guards still deny writes in both. A bare-repository worktree or a
separate-git-dir checkout keeps the old search, because its common dir is not named `.git`.

## Requirements

- FR-1: `find` reads `<candidate>/.git` and the gitdir's `commondir` only when each is a regular file, and spawns
  no git process.
- FR-2: the nearest candidate whose resolved common dir is named `.git` decides. The answer is the nearest
  `.wuwei/` at or above that main checkout. With none, the search goes on above the worktree. The look-ahead
  ends at the nearest folder holding a `.git` entry or a `.wuwei/config.toml`; nothing above it redirects.
- FR-3: with no worktree on the path, today's upward search for `.wuwei/` applies.
- FR-4: the runtime stays within +6 lines; the vendored copy matches.
