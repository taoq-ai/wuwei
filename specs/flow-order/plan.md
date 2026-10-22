# Implementation plan: flow-order

**Spec**: `specs/flow-order/spec.md`
**Item**: flow-order, tier standard, goal G-1

## Technical context

- `cli/wuwei/board.py` `compute` builds one row per item or PR; the Stop hook (`hook.stop`) and
  SessionStart read `board.rows` in order, so ordering the rows orders both.
- `cli/wuwei/plan.py` `score` holds the WSJF and RICE formulas; `save` ranks the plan file.
- `board.running` reads live seats from `seat.started` rows, which already carry the item.
- Runtime at the base: 3,401 lines; budget for this item: +80.

## Design

1. `plan.CLASSES`; `plan.delay` (the numerator) and `plan.score(..., waiting)`; `plan.cost(item,
   rows, days)` ages WSJF time criticality and adds open waiters' cost of delay. `save` stores
   `cost` as the score, so `plan show` ranks with waiters too. `add` takes `cls` and `after`,
   refuses an unknown class, a second open expedite item and an unknown `after` id.
2. `board.flow` after the per-repo loop: class, score, last event, waiting and stale per row, then
   the sort. Owed replies stay first, the `team` row stays on top. `board.text` shows
   `[class, last event Nh ago]`.
3. `running(root, session, key='role')` also reads the items of live seats.
4. CLI `--class` and `--after` on `plan add`; the lead file's `class` and `after`.
5. docs/design.md, docs/site/concepts/the-day.md, docs/site/reference.md.

## Verification

- tests/test_flow.py red on main, green at the head; full suite green.
- Main-versus-head route differential over tests/fixtures/routes.json through hook.pre_tool and
  guards.bash.
- Runtime 3,481 lines.

## Constitution check

Stdlib only, test first, no new config key, no new door, runtime within the cap and the item's
budget.
