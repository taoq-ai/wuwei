# Feature Specification: WUWEI names an orchestration gap

**Feature branch**: `1180-orchestration-gap`
**Item**: 1180, tier full (the brief raised it from standard: `cli/wuwei/hook.py` is an owner
path), goal G-2. Issue taoq-ai/wuwei#1180.
**Input**: on a resumed day with 29 open PRs and owed gates on several heads, the planner ran no
shepherd and no gate seat and did the shepherd's work itself, one PR at a time, for about 30
minutes. Nothing WUWEI printed said that nobody was working the PRs. Probe 1180-probe measured
the rule to build at 646e4625.

## The promise in my words

The board gets one more row, `team`, after every item row. It holds up to two duty lines:

- `orchestration: open PRs with no shepherd seat running`, when the board shows more than two
  distinct open PRs and no shepherd seat runs;
- `orchestration: gates owed on green heads with no gate seat running`, when some PR row carries a
  gate gap (`gates missing at head ...` or a delta review owed) and no CI gap (`CI running`,
  `CI failing`, `CI not started`, a required check not run),
  and no `sentinel-*` seat runs.

A seat runs when the current session started it today (its `seat.started` row carries the
session id) and no `seat.stopped` or `seat.unconfirmed` row names the same agent id. The status
command reads the session from `CLAUDE_CODE_SESSION_ID`; the Stop hook reads it from its payload.
No session known means no seat runs. A Codex job writes no seat row, so it never counts.

The lines are duties: they never hold a merge, and they reach `wuwei status`, the watch pass, the
Stop reminder and the session start through the board. They carry no count, so the same state
gives the same text and a Stop reminds once per session while it holds.

The Stop hook stayed silent while any seat started today had no stop. It now reads the same rule,
so a seat a dead session left behind no longer silences every reminder on a resumed day.

The planner charter says a Codex handoff's network steps (push, PR body, thread replies,
re-gate) go to the shepherd seat. `/wuwei-run` step 3 says a resumed day with open PRs starts the
shepherd and the owed gate wave before any resume list or finished Codex round.

The acceptance scenarios, restated:

1. Three open PRs, no running shepherd: `wuwei status` shows the team row with the shepherd line.
2. A PR owing `quality` at a head with green CI and no running sentinel: the gate line shows; with
   CI running or failing on that head, it does not.
3. A running shepherd, or only two open PRs: no shepherd line. A running sentinel: no gate line.
4. The same orchestration state at two Stop events: the second adds no reminder, even when the
   number of open PRs moves.
5. The merge door reads any PR: nothing new holds the merge.
6. The charter and the skill route a resumed day's network steps to the shepherd and start the
   shepherd and the gate wave first.

## How this fails

1. The session id is missing where the board is computed. `wuwei status` reads
   `CLAUDE_CODE_SESSION_ID`; if a harness (Codex, an older Claude Code) does not set it, no seat
   counts and both lines show while seats do run. The lines are duties with no merge hold, so the
   cost is a false nudge, never a block. The Stop path does not depend on it: it reads the
   payload's session and stays silent while a seat of its session runs.
2. The shared board cache (60 seconds) carries a team row computed in one session into another
   session's Stop or status. A Stop never shows it while its own seat runs (the guard runs before
   the board read); `wuwei status` computes fresh. The session start reads the cache, and a new
   session has no running seat, so the row it shows is true for it.
3. Codex work runs as a background job with no seat row, so a day run only on Codex jobs always
   shows both lines. That is the intended reading (the issue's case: the planner did the
   shepherd's work by hand), and the charter now tells the planner to launch the shepherd.

## Clarifications

### Session 2026-10-20

- Q: Which liveness rule? A: The probe's: started in the caller's current session and not
  stopped. "Started today" hid the gap when a dead session's shepherd never stopped; the session
  rule shows it. The today filter stays as a bound, so a session id that lives across days does
  not keep yesterday's dead seat alive.
- Q: Why no count in the lines? A: The probe measured two reminders across two Stops when the
  count moved (29 to 28), and one with a constant text. Counts already sit in the item rows the
  board lists.
- Q: Why change `hook.py` when the item put it out of scope? A: The probe found `hook.stop`
  returns early while any seat started today has no stop, so on a resumed day the new line would
  never reach a Stop. The brief puts the guard in scope. Once #1172 merged, `hook.running` had no
  runtime caller left, so the merge round removed it and pointed its tests at `board.running`.
- Q: What counts as an open PR? A: The distinct PRs the board lists (linked to an open item, or
  adopted as unplanned), drafts included. A PR the board does not list is not WUWEI's to shepherd.
- Q: What is a green head? A: A PR row with no gap starting `CI ` (running, failing, not
  started) or `required check` (a check the base requires with no run at the head, from #1176). A head with no CI at all in a repository that runs none reads as green, as the merge
  door reads it.

## Composition with open work

PR #1172 (merged) made `hook.running` subtract `seat.unconfirmed`; `board.running` already did,
and the merge of main at 1877565 removed `hook.running` with its last caller gone. Its tests now
read `board.running` with a session. PR #1176 (merged) added `AUTO` beside `DUTY` in `evidence.py`;
the merge keeps both lines. Items 1168, 1178, 1179, 1181 edit `evidence.py`; this item changes only
the `DUTY` line. Items 1169, 1177, 1178 edit `board.py`; this item adds a
function after `adopted` and lines at the end of `compute`. This PR rebases after those ahead of it.

## Requirements

- FR-001: `board.compute` appends a `team` row whose gaps are the lines above, only when one holds.
- FR-002: `board.running(root, session)` returns the roles of the seats the session started today
  with no stop or unconfirmed row under the same agent id; no session gives the empty set.
- FR-003: `hook.stop` returns early only when `board.running` names a seat of the payload's session.
- FR-004: `evidence.DUTY` matches `orchestration:`, so the lines are duties: visible, never blocking.
- FR-005: runtime lines grow by at most 12 (the item's budget).
- FR-006: the planner charter and `/wuwei-run` say what the promise says.

## Assumptions

- `CLAUDE_CODE_SESSION_ID` holds the planner's session id in a Bash call, also inside a subagent
  (measured in this builder seat: it equals the session in the scratchpad path). Overturned if a
  Claude Code version stops setting it; then the lines show while seats run, a duty only.
- An item row named `team` cannot be confused with a plan item: plan ids in this workspace are
  numbers or `I-n`. Overturned if a plan adds an item with the id `team`.

Rollback: revert the merge commit of this PR; the board loses the team row and `hook.running` comes
back as the Stop guard, counting every seat started today again.
