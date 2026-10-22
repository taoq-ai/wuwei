Verdict: PASS
Gate: arch
Item: flow-board
PR: taoq-ai/wuwei#1252
Head: 23ba522d1e991f335bf0bd88c94b8d8aaac24110
Confidence: medium
Breaking: no (minor: new board gap texts, a new team-row line and an advisory PreToolUse note; no documented element removed or reshaped, no exit code moves)

## Findings
- [medium] cli/wuwei/board.py:129 blocks: no. The seat-ceiling duty is actionable and names the busiest session's count, but hook.stop returns early for any session with a live seat (hook.py:119), so the only Stop that can show this line belongs to a session that is not the crowded one, and each change in the other session's seat count is a new line that blocks that Stop again. The promise says "this session's live seats"; the PR records the busiest-session reading as an assumption (the board is cached across sessions). Passing actionable=False keeps it on the board and session start and out of every Stop, at zero lines.
- [low] cli/wuwei/board.py:123 blocks: no. The comment "duties with no count, so a Stop reminds once while they hold" is now false: both new duties carry a count ({busy}, {crowd}), so a Stop reminds again whenever the count moves. The promise mandates the counts; the comment should say so, or the WIP duty should be actionable=False like the queued rows.
- [low] cli/wuwei/board.py:145 blocks: no. Defaults have two sources: charters/planner.md:26 states 4 and 8 in prose, and the code states 4 (board.py:145) and 8 twice (board.py:124, hook.py:85). The owner's override has one source (the standards.md lines both read), but a steward proposal that changes the default in the charter would not move the code. tests/test_charters.py:495 checks only the key names; a one-line assertion that the planner text holds the code's defaults, and one shared constant for the 8, would pin them.
- [low] cli/wuwei/board.py:147 blocks: no. Liveness now has two windows: WIP counts builders under STALE_HOURS (4h, as the promise and acceptance 3 ask), while running() (6h) feeds the row's "builder running" gap, the ceiling count and flow's stale check. A 5-hour builder row can show "builder running in session S" and "queued" at once. Follows the promise; worth one window in a later item.
- [low] blocks: no. Runtime +34 (3,697 to 3,731 of 3,800) against the item's own "estimate +8, budget 12". The repository budget holds (headroom 69; about 55 after builder-host's +14). The size buys five behaviours (WIP count and queue, a hardened limit reader, two team duties, the launch note, the Stop text), so it is in proportion; at most a few lines are deletable (board.py's new `from pathlib import Path` where os.path.join already serves; the three `context('PreToolUse', note) if note else None` returns in hook.advise could fold into one at the caller). The PR body reports +34 but not the overrun against the item budget.

## Probes
- Read `wuwei plan show flow-board` (promise, 5 acceptance scenarios) and `git diff origin/main...23ba522d` (merge base = origin/main 1b8ef2b8); copies via git archive under the arch scratch folder.
- Conformance: docs/design.md board section and PreToolUse row updated to the behaviour; constitution "no config key" honoured (standards.md lines, the same channel as `Review requests:` and `Generated (...)` lines in evidence.py:91 and :378); charters/planner.md:22-30 already defines in progress, the WIP limit, the seat ceiling and where the owner's numbers live, so no charter change is needed and the code follows it.
- Composition with flow-order (#1243): queue() runs after flow(), sorts by flow's score, and only rewrites rows whose first gap is "no pull request yet", so "waiting on", andon, awaiting approval, run items and unlinked-PR rows keep their own gap; queued gaps are actionable=False and the Stop counts them under "Left out". No second ordering mechanism.
- Composition with multi-session (#1238): WIP builders, the team-row ceiling and the launch note all read board.running; no new seat registry. Counting builders from every session matches planner.md:26 "across the workspace"; the promise's "this session started" wording conflicts with its own first sentence and the PR's Assumptions records the choice.
- Dependencies: hook.py already imports board (hook.py:14); board imports no new wuwei module; no cycle. hook.crowded reads the ledger (3 ws.rows passes) on each Agent/Task launch with no door decision; a raise there falls into handle()'s existing PreToolUse handling, same as advise's existing reads.
- Vendored copy: `diff -r cli/wuwei .claude/wuwei/cli/wuwei` identical at head.
- Runtime: `cat cli/wuwei/*.py | wc -l` main 3697, head 3731; tests/test_setup.py budget and vendored tests pass (4 passed).
- Targeted tests at head: `pytest -q tests/test_watch.py tests/test_hook.py -k "wip or ceiling or limit or builder_seat or queue or free_slot or ten_lines"`: 13 passed. Full suite not run (brief).
- Guard differential: not re-run; the PR reports 0 of 294 decision moves at 0 and 9 seats with the route corpus sha256 unchanged, and security passed at a38050d; the fix round touched board.limit only.
- Confidence medium: design fit read in full, behaviour checked by targeted tests and code reading; the Stop interplay of the count-bearing duties is reasoned from hook.stop, not probed with a running session.

## Residual risk
The two new team duties can re-block Stops as counts move, most visibly for a session that is not the crowded one; and the default numbers can drift between planner.md and the code.
