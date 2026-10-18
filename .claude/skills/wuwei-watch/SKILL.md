---
name: wuwei-watch
description: One WUWEI watch pass over work in progress, so nothing waits on the owner's nudge. Use on a schedule (/loop 20m /wuwei-watch locally, or an hourly routine in the cloud), when a PR or chat event wakes the session, or whenever open work may have moved. Not for adding, dropping or re-ranking work (/wuwei-run) or the checkpoint and retro (/wuwei-close); a watch pass only moves what is already planned.
---

# /wuwei-watch

One pass. Act on what the team can close; record it; say nothing when nothing changed.

1. Run `wuwei watch` (last pass, replies owed) and `wuwei status --all` (every open item's gaps,
   process fit included).
2. Owed replies first, oldest due first. Answer each within the mandate, in its own thread, through
   the connected tool. A send into that thread closes the reply by itself. A question only the owner
   can answer goes to the owner once, with its class and your recommendation.
3. Inbound asks: read the connected chat and tracker tools (Slack, Linear, issue and PR comments)
   for mentions of the owner or the team and direct questions since the last pass. Record each one
   not yet owed: `wuwei owe <thread link> "<what was asked>" --who <name> [--within 4h]`. Skip what
   is already answered.
4. Open PRs, as the shepherd charter says: red CI; conflicts; unanswered review threads; a missing
   reviewer; a review request not yet posted where the team asks (`review not requested in ...`); a
   PR open three days or more (finish, rebase or close it); process gaps that are cheap to close.
   `unplanned` rows are PRs raised by hand: follow them the same way. Merge what has no safety
   gaps; arm auto-merge where only CI is running.
5. Keep the flow going: an approved item with no pull request and no running seat gets its builder,
   highest score first. A pushed branch whose builder handed back gets its draft PR and its gates.
   A draft whose gates passed turns ready with reviewers. An operations item (`run:` on the board)
   gets its run checked and its evidence recorded with `wuwei plan run <id> --reason "..."`. When
   the queue is empty, run a plan pass from the goals (`/wuwei-run`).
6. Record the pass: `wuwei watch --record "<one line: what you did>"`. If you did nothing, record
   `nothing changed` and end the turn without a message to the owner.

## Scheduling

The plugin runs no background process; Claude Code's own scheduling runs the watch.

- Local session: `/loop 20m /wuwei-watch`.
- Cloud: a routine that runs `/wuwei-watch` hourly in the workspace repository, and a GitHub PR
  subscription on each open PR so reviews and CI wake the session between passes.
- Cheaper passes, an option and not a default: a watch pass mostly reads and records, so it may run
  on Sonnet 5.5 at medium effort. To choose it, set `model: claude-sonnet-5-5` and
  `effort: medium` in this skill's frontmatter. Claude Code then runs the rest of that turn on them.
