# Feature Specification: the board links every item a PR names, closes a just-merged item, and shows uncounted verdicts

**Feature branch**: `claude/board-links`
**Item**: board-links, tier standard, goal G-2
**Input**: #1076 named `WUWEI-Item: X-1` and `WUWEI-Item: X-2`, but only X-1 linked. vendored-drift
(#1079), seat-count (#1084), sync-note (#1086) and others stayed "no pull request yet" after merge
until closed by hand.

## The promise in my words

`board.compute` linked a PR to one item only: `evidence.item_for` takes the first `WUWEI-Item`
match. `evidence` gains `items_named(body)`, which returns every item id a PR body names. The board
links a PR to each of those items, and once the PR merges it closes each of them. A PR whose body
names no item still links through `item_for` (the plan's `prs` list or the branch name).

The merged list was cached for 300 seconds, so an item whose PR had just merged showed "no pull
request yet" until the cache expired, and the board cache could then hold that answer longer. Now,
when any open item of a repository has no open PR, the board reads that repository's merged list
fresh. When every open item has an open PR, the 300-second cache still serves.

An item with no PR now also lists its verdict files that do not count (`evidence.uncounted`). So a
verdict written while the hooks were down shows on the board before the create door refuses.

The acceptance scenarios, restated:

1. Open PR #9 names items A and B: the rows for A and B both show `acme/app#9`. Once #9 merges, A
   and B are both marked done.
2. Item C's PR merged 30 seconds ago and the merged-list cache is 2 minutes old: the board marks C
   done instead of "no pull request yet".
3. Approved item D has no PR and a well-formed, unattested verdict
   `.wuwei/verdicts/D/quality-abc1234.md`: D's row names that file as not counted.
4. The runtime stays at 3,000 lines or fewer.

Out of scope: naming missing gates for a pushed branch with no PR, and which item's gates a
two-item PR reads (`evidence.gaps` still uses `item_for`).

## Assumptions

- Ids from a body match plan ids case-insensitively, as `plan.find` does. Overturned if plan ids
  are meant to be case-sensitive.
- A fresh merged read when any item is unlinked costs one GitHub call per repository per board
  compute. The board itself is cached for 60 seconds, so this is at most one call a minute per
  repository. Overturned if rate limits bite on large plans.
- Uncounted verdicts are listed on every no-PR row, whatever the first gap says (andon, run,
  awaiting approval). Such items rarely have verdicts; when they do, the file is worth showing.
- The item estimated +3 runtime lines. The change adds 10 (`items_named` and the `names` helper
  carry the blank lines PEP 8 asks for). The runtime is 2,949 of 3,000.
