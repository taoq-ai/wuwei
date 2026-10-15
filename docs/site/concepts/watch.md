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
