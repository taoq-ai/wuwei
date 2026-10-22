# Work in progress

Open work should keep moving without you nudging it: PRs with a red check or an unanswered review,
a question in a Slack thread, a stale branch. WUWEI does this with a watch pass and owed replies.

## The watch pass

`/wuwei-watch` is one pass over everything in flight:

1. Owed replies, oldest due first, answered in their own thread.
2. New asks from the connected chat and tracker tools, recorded as owed replies.
3. Open PRs, as the shepherd charter says: CI, conflicts, threads, reviewers, stale branches, merges
   (or auto-merge while only CI runs).
4. One line recorded (`wuwei watch --record`). Nothing changed means nothing is said.

**Why:** a team that only moves when you ask is not autonomous. The watch is the habit of checking
on your own work, done on a clock instead of on your memory.

## Flow: finish before starting

Starting work feels like progress; finishing it is progress. Too many items open at once means
none of them closes, and too many seats at once slows every turn. So the planner works a Kanban
limit, as advice:

- **WIP limit, default 4.** An item is in progress while it has an open PR, a running builder or a
  registered Codex job. A new item starts only while fewer than four are in progress across the
  workspace. Fix rounds, gates, shepherd work and merges on open PRs always come first.
- **Seat ceiling, default 8.** At most eight seats run at once in a session.
- **You decide.** Ask for more and the planner tells you the cost once (slower turns, rate limits
  sooner, more notifications in the session), then does it. It records your number as a dated
  `WIP limit: <n>` or `Seat ceiling: <n>` line in `.wuwei/standards.md`, which holds until you
  change it. WUWEI advises; it never refuses a start.
- **The numbers learn.** At each close the steward measures peak live seats, peak items in
  progress, starts against merges per day, and tool-call duration by live seat count. It
  re-derives the WIP limit by Little's law (merges per day times PR lead time) and the ceiling
  from where tool calls slow down, and proposes a change with those numbers.

`/wuwei-close` also does housekeeping for what the session started: it removes clean worktrees of
finished items, stops its own background tasks, clears finished seats' scratch folders, and
reports the cache size. A process the session did not start is named to you once, never killed.

**Why:** a smaller batch in flight finishes sooner, and a limit you can see is one you can change.

## Who runs it

The plugin runs no background process; Claude Code's own scheduling does:

| Where | How |
| --- | --- |
| Your machine | `/loop 20m /wuwei-watch` in the session |
| Claude Code cloud | an hourly routine running `/wuwei-watch` in the workspace repository, and a GitHub PR subscription on each open PR so reviews and CI wake the session between passes |

Hooks cannot wake an idle session: they fire only on events inside a running one. They still do
their part: the Stop hook does not let a turn end while someone waits on a reply, and a send closes
the reply it answers.

## Owed replies

`wuwei owe <thread link> "<what was asked>" --who <name> --within 4h` records that someone is
waiting. It sits on the board as `reply owed to <name> in <thread>, due <time>`, and as `overdue`
once past due. When the team sends a message into that thread through a connected tool, the
PostToolUse hook closes the reply by itself: the evidence is the send, not someone remembering to
tick a box.

The report shows replies owed, closed, open and overdue, and the median response time.

## Review requests

When `.wuwei/standards.md` names where the team asks for reviews (`Review requests: Slack
#eng-reviews`), every ready PR the team raises owes one post there with its link. Until a send
naming the PR is recorded, or someone other than the author has reviewed it, the PR carries
`review not requested in <place>` on the board, and the Stop hook does not let the turn end on it.
It is a duty, not a safety gap: it never holds the merge. A post made outside the session is
recorded with `wuwei sent owner/repo#n <link to the post>`. A 0.34 workspace's `review_channel`
becomes that line on upgrade.

PRs raised by hand count too. An open PR by the session's identity on a configured repository,
opened in the last seven days with no plan link, shows on the board as `unplanned` with its gaps,
so it is shepherded like any other.

**Why:** a PR nobody was asked to review waits silently; asking is part of raising it.

**Why:** people waiting on an answer are the work in progress that hurts most when forgotten, and
the easiest to forget, because no CI turns red when a question goes unanswered.
