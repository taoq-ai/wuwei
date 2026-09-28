# Obligations contracts

`bin/wuwei sweep obligations` reads today's existing state and the union
of `raised_prs` and `claimed_prs` (canonical owner/repo#number strings). It prints
identifiers and reasons, never comment bodies. Returns 0 clean, 1 owed, 2 unreadable.
PR lists are append-only. An empty union requires readable state history and no
prior PR entries or positive sweep counts today. State-write events carry a
producer-owned `prs_seen` boolean.

One `watch: sweep` event has `sweep: obligations`, `exit`, `prs`, `reply_owed`,
`visibility_owed`, `unreadable`, and `owed` (sum of those three counts).

The existing `code_host.pr` adds `requested_reviewers: list[str]` and
`requested_teams: list[str]`. All comments and reviews add `is_bot: bool` derived
by the adapter from actor type. Missing or unknown types fail closed. Existing
`threads` contains PR comments and complete inline thread connections.

Day state additions:

- `channel_posts`: reserved list of `{pr, status: posted, url: https permalink,
  reviewers: [code-host login or team identity]}`. These reviewer identities assert
  actual mentions in the posted message, not prose names in a held draft. Mentions
  cover requested reviewers and teams, falling back to human review authors only
  when nobody is requested. No posting producer ships here; absent evidence stays owed.
- `reply_acks`: reserved object, keyed by canonical PR ref, then `comment:ID` or
  `review:ID`, with `{fingerprint, reply_id, reply_fingerprint, me}`. The fingerprint covers normalized
  target and reply evidence, so edited or deleted replies and changed target
  bodies or revisions cannot reuse an old ack.

Verdict evidence comes from today's linted `decisions/gate-*.md` files. Their
`Verdict:` is PASS, FIX, PARK or ESCALATE; their `Head:` matches the current PR head
(full or lint-valid abbreviated prefix). State `gate_verdicts` is ignored.

Both commands take identity from the sole non-Slack code-host login in
`owner.handles`; missing or ambiguous identity fails closed. `--me` is unsupported.
The generic event command refuses `watch: sweep` and `reply: acknowledged`.

`bin/wuwei reply REF --surface comment|review --id ID` reads the reply
body from stdin. It reads the target, posts via `code_host.comment`, then verifies
that the returned ID exists among fresh PR comments by the configured login with the submitted
body, and that the target did not change. Only then does it write `reply_acks`
through the dedicated state writer. Failure never records an acknowledgement.
It is the minimal shepherd reply path, not a general code-host write command.
