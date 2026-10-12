# Implementation Plan: the gate seats that fit; one build slot count

**Branch**: `910-gates-that-fit` | **Spec**: `specs/910-gates-that-fit/spec.md`

## Technical Context

Python 3.11 stdlib only. No new module. Touches `cli/wuwei/commands/next.py` (`building`,
`slot`), `cli/wuwei/dispatch.py` (`launch_set` only; `next_step`, `resolve_offer` and
`derive._gate` belong to #902 and are not touched), `cli/wuwei/derive.py` (`offers` free count),
`cli/wuwei/commands/build.py` (the new-build CAP check), `cli/wuwei/guards/agent_launch.py` and
`cli/wuwei/guards/__init__.py` (capacity text). The design spec is the owner's; the proposed
amendment is in the spec's Assumptions.

## Constitution Check

- Stdlib only, test first, shortest diff. One helper replaces four sums and the guard's own
  count; the seat subset is a loop in the one function that already sizes the set.
- No new wall: the guard's CAP refusal stays a log-only capacity refusal (#837).

## Design

1. `next.building(data)`: approved items in `state.BUILD_PHASES`, not `state.held`, plan order.
   `next.slot(data, item, cap)`: item in `building(data)[:cap]` or fewer than `cap` hold one.
2. `launch_set.add`: for an action with `seats`, after the memory hold, take seats in order
   while a host seat is free and the seat's runtime window has room; launch those, set
   `deferred` and a reason for the rest. None fit: host wait when no host seat is free, else
   the window hold of the first blocked runtime. Other actions unchanged, plus: a build or fix
   kind that launches a seat waits with the CAP reason when `slot` fails.
3. `gate_waits` reads `deferred` too, and an initial gate whose batch runs with fewer gate seats
   registered than its gate set. The slot count is read fresh after the offers resolve.
4. `derive.offers`, `launch_set`, `build.next_action`, `next` use `len(building(data))`.
5. Guard: a builder is refused with `build slots N at CAP C: <holders> hold them` when `slot`
   fails; the live builder count goes. `CAPACITY` names `build slots`.

## Tests

`tests/test_dispatch.py` (day_set: three gates on two seats; a second opinion on a spent
runtime; a stopped builder awaiting checks and a fix round past CAP), `tests/test_parallel_dispatch.py`
(end to end: three gates on two seats reach raise, never over two seats; a head move refuses the
deferred seat), `tests/test_agent_launch.py` (a Codex loop holds a slot; plan-order holders;
existing CAP tests set their items building), `tests/test_enforce.py` (capacity text).
