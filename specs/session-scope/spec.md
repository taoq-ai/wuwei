# Spec: open items reach only the planner session (#1276)

## In my words

Other sessions in a WUWEI workspace kept getting the Stop reminder and the full board, and the owner had to tell
the model to ignore them. After this change a session sees the open work only once it acts as the planner. A
session is a planner when it ran `wuwei plan pass` or launched a seat for an item. The Stop reminder fires only in
a planner session. A session that is not a planner keeps the CLI path, the way, Decisions and Done and the owner
answers at start, and gets `<n> open items; wuwei status lists them.` in place of the board. A resumed planner
session keeps its board. `wuwei status`, `/wuwei-run` and `/wuwei-watch` are unchanged in every session.

## Acceptance scenarios

1. A session with no plan pass and no seat launch gets no Stop block with open work.
2. The session that ran `wuwei plan pass` gets the Stop reminder as today.
3. A new session that is not a planner, with 5 open items, gets `5 open items; wuwei status lists them.` and no
   item line.
4. A resumed planner session, by plan pass or by a seat launch for an item, gets the board inlined.
5. `wuwei status` lists every item in any session; this diff does not touch it.

## Requirements

- FR-1: PostToolUse records a `plan.session` row with the session id when a Bash segment is `<path>/wuwei plan pass`
  (read with `guards.segments`), or when the Bash output starts with `plan pass recorded`. Output that only
  contains the phrase does not mark.
- FR-2: a session is a planner when it has a `plan.session` row, or a `seat.started` row with a nonblank `item`.
- FR-3: ledger rows are read with `r.get("kind")` and `r.get("data") or {}`, so a malformed row cannot hide work.
- FR-4: andon lines stay visible in every session, above the count line.
- FR-5: planner status has no time bound; a new session id starts as not a planner.

## How this fails

1. A new session id (after /clear or a fresh cloud session) starts as not a planner: no Stop reminder and only the
   count line until its next plan pass or seat launch for an item.
2. A session that prints `plan pass recorded` or launched a seat for an item counts as a planner and sees the whole
   board and the full reminder, not only its own items. No door or owner answer depends on the mark, so the cost
   is extra text, not a wrong refusal.
3. A plan pass run through a spelling the hook cannot read (a variable, a wrapper) is missed by command shape; the
   CLI reply catches it. A pass whose reply is lost leaves the session a non-planner until it launches a seat.

## Assumptions

See the PR body. The main one: the hook records the pass, not the CLI, because the CLI cannot see the session id.

Rollback: revert the commit.
