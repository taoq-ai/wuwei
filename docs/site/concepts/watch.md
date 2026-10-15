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

**Why:** people waiting on an answer are the work in progress that hurts most when forgotten, and
the easiest to forget, because no CI turns red when a question goes unanswered.
