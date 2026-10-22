# Feature Specification: in-progress work flows by Kanban policy

**Feature branch**: `leone/flow-order`
**Item**: flow-order, tier standard, goal G-1
**Input**: the owner on 2026-10-22: "in-progress work is handled like a pile: first in, last out.
Can't we use another prioritisation framework? It is not only PR age, but also how urgent it is and
how it relates to the rest." Attention goes to the last event, so an old draft starves
(A-Teams-Network/ai-stacks#3386). The owner approved this Kanban flow scope.

## The promise in my words

1. Each plan item has a class of service: `expedite`, `fixed-date`, `standard` or `intangible`.
   Without one it is `standard`, or `fixed-date` when its goal in `goals.md` has a `Date:`.
2. At most one open item is `expedite`: `plan add --class expedite` for a second item is refused.
3. The board, and so the Stop reminder that reads it, lists work by class, then right to left
   (ready to merge, owner review, gates, fix round, building), then age, oldest first. Each board
   row shows its class and the hours since its last event.
4. A WSJF item's time criticality rises one Fibonacci step per day in progress.
5. An item can wait on other items (`plan add --after <id>`). While one of them is open, the board
   shows it `waiting on <id>`, the Stop leaves it out, and the item waited on adds the waiting
   item's cost of delay to its own score.
6. A PR idle 4 hours with no live seat on its item shows `stale` with its last event, first in its
   class.

The acceptance scenarios, restated:

1. An old draft with no recent event and a newer PR that just got its CI result, both standard:
   the one closer to done lists first; age orders ties.
2. An expedite item lists above every other class; a second expedite item is sent back.
3. B added with `--after A`: B shows waiting on A, the Stop leaves B out, A's score includes B's
   cost of delay.
4. An in-progress item idle 5 hours with no live seat shows stale with its last event.

## Definitions

- Last event: the latest of the PR's creation and update times, the item's `added` date, and any
  ledger row whose `id`, `item` or `pr` names the item or its PR (seat starts, verdicts, rulings).
- Days in progress: whole days since the item's PR was created.
- Cost of delay: the score's numerator (WSJF value + time + risk; RICE reach x impact x confidence).
- Live seat: a seat `board.running` counts live in any session (started within its bound, no stop row) whose brief names the item.
- Stage: from the row's safety gaps. No PR is building; an actionable safety gap that is not a gate
  gap is a fix round; a gate gap is gates; an owner gap is owner review; else ready to merge.

## Out of scope

- The Stop reminder lines keep their text: they name only what changed (#1099), so a moving age
  in them would remind every time. They follow the board order.
- No charter change: the planner reads the board order; `--class` and `--after` are in the reference.
