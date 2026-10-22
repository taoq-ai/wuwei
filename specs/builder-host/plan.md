# Implementation Plan: builder-host

**Spec**: `specs/builder-host/spec.md` | **Tier**: standard | **Runtime budget**: +14 lines (3,800 limit)

## Technical context

Stdlib Python 3.11+ under `cli/wuwei/`. The plan lives in `.wuwei/plan.json` through `plan.add`
and `plan.mark`; the board's live seats come from `board.running`, which reads `seat.started`
rows written by the SubagentStart hook. A `create_session` builder writes no such row.

## Design

1. `plan.HOSTS = ('agent', 'session')`. `plan.add(..., host='agent')` refuses any other value and
   stores `host` on the item; `add_from` passes a candidate's `host`. The CLI takes `--host` with
   `choices=plan.HOSTS`, default `agent`.
2. `wuwei plan session <id> <session id>` stores `session` on an item whose host is `session`,
   through `plan.mark` (status stays open, one `item.open` ledger row). It refuses an item with
   host `agent`, an unknown item, or a missing session id, and records nothing.
3. `board.running(root, hours=6, hosted=False)`: with `hosted=True` it appends one builder seat
   per open `session` item with a recorded session id. `board.compute` (team row and holder gaps)
   and `board.flow` (stale) pass `hosted=True`. The hook's held check and Stop keep the default, so
   `hook.py` does not change and the planner's gate launches on that item are not refused.
4. Charters: planner rule 1 gains the `create_session` paragraph; builder standard 7 says to
   commit and push after every green step and hand back the pushed head. `bin/wuwei agents build`,
   then `setup.vendor('.')` for the vendored copy.
5. Docs: `docs/site/reference.md` (`--host`, `plan session`) and `docs/design.md` section 6.

## Constitution check

Stdlib only; reuses `plan.add`, `plan.mark` and `board.running`; no new config key (the six-key
budget holds: the host is a plan field). No guard or hook code changes, so no route differential is
owed.
