# 360 feedback between seats

Promise, in my words: each seat already says what the work it used cost or gave it, in Gap and
Change lines, and the stop record drops them. Seats now add one `Feedback: <role> +|-: <evidence>`
line per seat whose work they used. The SubagentStop hook keeps the Feedback lines, the last Gap
and the last Change line on seat.stopped. Each is masked for secrets, then cut to 200 characters,
and a `none` is not kept. `wuwei report` prints a Feedback line under Seats and gates: counts by
named role and sign, then up to ten cost lines with the giving role. The steward reads 14 days of
that block; a cost two or more seats name against one role becomes a charter proposal.

Acceptance, in my words:

1. A builder report with a cost line on sentinel-quality and `Gap: none` stops with that feedback
   line on seat.stopped and no gap key.
2. A secret in a kept line is masked before the cut, so no partial token survives.
3. Stops with feedback on sentinel-goal -, builder + and planner - give counts by role and sign
   and the cost lines with the giving role, at most ten.
4. A report with no Feedback line records the same keys as before; the day report prints
   `Feedback: none.`
5. Every generated agent keeps 100 words of room under the 2,250-word ceiling.

## User scenarios

### US1: the stop keeps the feedback (P1)

A seat stops with Feedback, Gap and Change lines. seat.stopped holds the Feedback lines as a list
and the last Gap and Change as strings. A `none` value, blank value or absent line adds no key.

### US2: the report shows it (P1)

The day report lists, under Seats and gates, `Feedback: <role> <sign> <n>, ...` ordered by count,
and `- <giver> on <line>` for up to ten cost lines. A line without the `<role> +|-:` shape counts
as `unnamed`.

### US3: the steward acts on it (P2)

The steward charter's rule 12 reads 14 days of the block and turns a cost two seats name against
one role into a charter proposal naming the line it replaces.

## Requirements

- FR-001: hook.py `_seat_stop` reads `^Feedback:`, `^Gap:` and `^Change:` lines from the report it
  already reads for Confidence.
- FR-002: each kept value is masked with `guards.SECRETS` (as traces are), then cut to 200.
- FR-003: no new ledger kind, no rating, no outward send.
- FR-004: `_common.md` gains the Feedback line with an equal word cut; arch keeps 100 words of room.

## How this fails

1. A seat quotes a `Gap:` line inside its report body, and the record keeps the quote. The last
   match wins, so the closing block is the one kept.
2. Seats write `Feedback: none` or free text with no role; the counts fill with `unnamed` and the
   steward has nothing to act on. The report shows that, so the retro can tighten the line.
3. A secret straddles the 200-character cut. Masking runs first, so the cut never leaves a
   partial token.

## Assumptions

- The giving role is the seat.stopped `role`, so no role is parsed from the line for the giver.
  A seat type outside the agent table would overturn it.
- Gap and Change keep the last line, Feedback keeps every line, matching the report block order.
- The report reads one day, as the rest of the report does; the steward reads 14 days with
  `--day`. A need for a 14-day block in one call would overturn this.
- The canary is not masked here: the promise says "masked as traces are", and traces mask only
  `guards.SECRETS`.

Rollback: revert the commit.
