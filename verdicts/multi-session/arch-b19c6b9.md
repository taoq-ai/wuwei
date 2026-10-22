Verdict: PASS
Gate: arch
Item: multi-session
PR: taoq-ai/wuwei#1238
Head: b19c6b928b0ee15c22cffa8e9b99fbe0e30e80a6
Confidence: medium
Breaking: no (minor: board rows gain a non-actionable "<role> running in session <id>" gap, plan.json items gain a `changed` key, board.running is internal and both callers move with it)

## Findings
- [low] cli/wuwei/board.py:66 blocks: no. A session that dies with a seat running holds its item for up to 6 hours: another session's launch for that item is refused, and the refusal says "launch after its seat stops", which never happens for a dead seat. There is no release command. The 6-hour bound and the missing release are recorded under the PR's Assumptions, so this is a known trade-off. Candidate follow-up: a release path, or name the bound in the refusal text.
- [low] docs/design.md:248 blocks: no. The design's PreToolUse hook row and its section 10 state paragraph (docs/design.md:289) do not mention the cross-session hold or the plan's merge by item. docs/site/concepts/hooks.md and cloud.md were updated, but the design document was not.
- [low] cli/wuwei/plan.py:41 blocks: no. Merge stamps use each clone's wall clock, so clock skew decides which copy of an item wins. A clone on an older vendored plugin (one that does not stamp) can edit an item and keep the old stamp, and then that edit loses on merge.
- [low] cli/wuwei/plan.py:48 blocks: no. The merge keys ids case-sensitively, but plan.find is case-insensitive. Probe: local `a` merged with branch `A` keeps both items.
- [low] cli/wuwei/plan.py:48 blocks: no. Merging an identical plan can reorder items with equal scores, ordering them by stamp, so the file bytes change and one extra state commit follows. The merged result is the same whichever clone merges, so the two clones do not keep swapping the order.
- [low] blocks: no. Two local sessions in one workspace, which this item now supports, still use the unlocked read-modify-write in plan.save. Concurrent plan changes on one machine can drop each other. This was already true before this PR, and it is a candidate item.
- [low] cli/wuwei/hook.py:121 blocks: no. The Stop hook's "Left out: N waiting on CI, the owner, plan approval or an andon" now also counts other sessions' running seats, and the wording does not name them.
- [low] blocks: no. origin/main (1bcefca) has moved hook.py and evidence.py since the merge base da48f374, so the branch needs a rebase before merge. The runtime budget holds after that too (3,399 on main + about 12).

## Probes
- Diff read: `git diff origin/main...b19c6b92` (14 files, +233/-53). The runtime changes are in board.py, hook.py, plan.py and sync.py.
- Budget: `cat cli/wuwei/*.py | wc -l` at the head gives 3402 (<= 3,600). Main's tree gives 3399, and the merge base gives 3390 per the PR (+12).
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei -x __pycache__` in the head worktree shows no difference.
- Dependencies: sync now imports plan, plan imports only ws, and hook already imported board. No cycle and no core-to-host edge. guards.py is unchanged, and the hold sits in hook.pre_tool beside seat.started's own parser (asked), as the Assumptions record.
- Per-session vs workspace state: live seats are derived from the workspace ledger (every clone's file), and the session id is read only from seat.started rows and the hook payload. No new per-session state file or cache.
- Callers of board.running: board.compute, hook.pre_tool and hook.stop are all updated (grep). Gap consumers: the merge door (guards.py:342) reads evidence.gaps directly, not board rows, so the new non-actionable gap only changes the board text and the Stop hook's waiting count.
- Merge rule: drops are status marks, not deletions (plan.mark), so a union by id cannot bring back a dropped item. Newest stamp per id wins, and this clone wins a tie. This is the simplest rule that meets acceptance 3. Field-level merge is not needed for the promise.
- Probe in a git archive copy (scratch sentinel-arch-multi-session): unstamped items on both sides gives the union. A newer branch stamp wins. Bad JSON, a list items, a non-dict item and an id-less item each return None and fall back to last writer. Identical input gives reordered bytes (ties). Case `A`/`a` keeps both.
- Hold probe through hook.pre_tool: a seat.started row for x1 in session A refuses session B's `Item: x1` launch and names A. Session A's own launch passes (null). asked() picks the line-start `- **Item:** x1` over an earlier inline `Item:`.
- Hot path: board.running on this workspace's real ledger (3,515 rows) takes 0.08 s, read-only, and runs only on Agent/Task launches and Stop. The item regex takes 0.15 s or less on 2 MB adversarial prompts (no catastrophic backtracking).
- Route corpus and guard differential: not re-run by this gate, since guards.py is unchanged. The PR reports 288 routes with 0 moved (sha256 de377966...).
- Confidence medium: the design fit, budget, vendoring and merge semantics were checked directly. The full suite and the mutants were not re-run, per the brief.

## Residual risk
Detecting a live seat is a heuristic (a start row with no stop row, at most 6 hours old). A crashed session can block its item for hours, and two launches at the same moment can both pass. Both are recorded in the PR.
