# Implementation plan

## Technical context

Python 3.11 stdlib runtime. Reuse `last_text`, `guards.SECRETS`, `ws.record` and the day report's
`rows`. No new ledger kind, config key or file.

## Constitution check

Stdlib only, test first, runtime estimate +5 with a cap of +8: the diff adds 8 runtime lines
(3,881 to 3,889 against the 4,000 budget). The hook change touches `_seat_stop` only; no guard
parsing, so the route corpus and parser probes do not apply.

## Design

- `_seat_stop`: one comprehension builds `feedback`, `gap` and `change`, merged into the record
  only when non-empty.
- `report.day`: a list of (giver, line, role-and-sign) from the day's seat.stopped rows, a
  Counter for the counts, and the first ten `-` lines.
- `_common.md`: the Feedback line in the closing block; cuts in Decisions, Evidence, Boundaries
  and Report keep the word count at or under its old 808.
- `steward.md` rule 12 and `docs/site/concepts/learning.md` describe the loop.

No contracts directory: the record gains optional keys; no reader breaks on them.
