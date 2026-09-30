# Implementation Plan: The loop's joints between build, gates, delta and push

**Branch**: `208-loop-joints` | **Date**: 2026-09-30 | **Spec**: `specs/208-loop-joints/spec.md`

## Summary

Five small fixes, each at the one shared function every caller already routes through:
the build step loop moves the item's phase, `wuwei brief` maps gate role aliases and takes
its body from options, the Agent launch guard accepts a resume of a stopped seat by its
recorded agent id, and `build check` records through the existing fast-check producer.
No new modules, no new state keys, no new configuration.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest, in-process with existing fakes (`tests/fakes`, `test_build.setup`,
`test_build_next.seat`, `test_brief.day`, `test_agent_launch.launch`,
`test_fast_checks.workspace_case`)
**Constraints**: three-state exits; fail closed; no guard loosened beyond FR-004 and FR-006

## Constitution Check

- One behaviour, one function: phase moves live in `commands/build.py`, push evidence stays
  in `fast_checks.record`, continuation stays in `agent_launch.reserve`.
- Reuse: `state.transition`, `fast_checks.record`, `dispatch.ROLES`, `brief.read`.
- Test first for every behaviour (tasks.md orders each test before its change).
- Seats remain written only by the PreToolUse and SubagentStop producers.

## Changes by file

### `cli/wuwei/commands/build.py` (joint 1 and joint 4)

- `next_action`: after `_save(item, record, root, 'build.started', previous)` (a new build
  record, not the idempotent early return), if the item phase read at the top is
  `planned`, call `state.transition(item, 'implement', root)`.
- `complete_checks`: replace the `fix_rounds == 1` block (lines 361-364) with: when there
  are no failures, read the item phase and call `state.transition` with
  `{'implement': 'gate', 'fix': 'delta'}.get(phase)` when it maps. Keep `fix_rounds` as is
  (still set by `open_fix`, still reset by `state.transition` on `delta -> raised`).
- `check`: replace the direct `checks.run` loop with
  `fast_checks.record(record['worktree'])`, then build the per-command results from the
  written `state['fast_checks'][record['repo']]` rows, exactly as `stopped` already does:
  `registry.Result(row['exit'], row.get('data'), row.get('reason') or '')` for each of
  `record['commands']`. A missing row raises `ValueError('incomplete fast checks')`
  (exit 2). Pass them to `complete_checks(..., expected=record)` unchanged. Lazy-import
  `wuwei.fast_checks` inside `check` (it imports `commit_push`, which `build` already
  imports lazily).

Must not change: `build next` idempotence (no state write on a repeated call), the
running-seat refusal, signature, stuck and iteration parking, the environment park, the
`open_fix` path, Codex `run_loop` semantics (it calls `check` and gains the record).

### `cli/wuwei/commands/brief.py` (joint 2 and joint 5)

- Parser: add a mutually exclusive group `--body TEXT` and `--file PATH`.
- `run`: body is `args.body`, or `sys.stdin.read()` when `args.file == '-'`, or
  `Path(args.file).read_text(encoding='utf-8')`. With neither, raise
  `ValueError('brief body required: pass --body TEXT or --file PATH (--file - reads stdin)')`
  (existing handler prints it and exits 2). Never touch stdin otherwise.
- Map the role before `brief.write`: `role = 'sentinel-' + args.role if args.role in
  dispatch.ROLES else args.role` (import `dispatch` from `wuwei`; no cycle, `dispatch`
  imports `brief`, not `commands.brief`). `pack` and `answer` are not affected.

Must not change: `brief.write` refusals, the logged payload shape, `pack` and `answer`.

### `cli/wuwei/state.py` (joint 3)

- `stop_seat(name, root=None, *, directory=None, agent_id=None)`: when `agent_id` is a
  non-empty string, also store it on the seat (`data['seats'][name]['agent_id']`).

### `cli/wuwei/guards/agent_launch.py` (joint 3)

- `stop`: pass `agent_id=payload.get('agent_id')` to `state.stop_seat` (non-builder path;
  builders keep recording through `build.stopped`).
- `reserve`: `continuing` becomes
  `resume and existing and existing['status'] == 'stopped' and (build-record condition if
  role == 'builder' else existing.get('agent_id') == resume)`. The builder condition is the
  current one, unchanged.
- Measure HEAD once whenever the logged brief has a worktree: load `vcs`, read
  `head = brief.read(vcs.head, tree, root=root)['sha']`; refuse `worktree HEAD changed since
  brief was written` only when not continuing and `head != logged['head']` (as today). This
  also binds `vcs` for the gate dirty-tree check that a continuing gate seat reaches today
  with `vcs` unbound. Store `'head': head` (the measured HEAD, or `logged.get('head')` when
  there is no worktree) on the seat record.

Must not change: refusal of a used brief without a matching resume, the builder resume
rule, role/name/digest/runtime/memory/capacity/gate-ready/dirty-tree checks.

### `cli/wuwei/dispatch.py` (joint 3)

- `receive` line 146: accept the verdict Head when it is in the brief text (as today) or
  when `str(seat.get('head') or '').lower().startswith(head.lower())`. The current worktree
  HEAD check and the sibling HEAD check below it are unchanged and still bind.

### `cli/wuwei/brief.py`

- `gate_ready` refusal text: replace the stale hint `then run wuwei state transition {item}
  gate` with `finish the build loop (build next returns done) first`. Tests match on
  `phase`, not on this hint.

### Docs, skill and the headless prompt

- `skills/wuwei-plan/SKILL.md`: brief commands take `--body` or `--file`; gate briefs may
  use the role names `dispatch next` returns; `done` leaves the item in `gate` (or `delta`
  after a fix build), so drop "move the item to `gate`" and "Transition to `delta`"; the
  planner still transitions to `fix` on `action: fix`; a delta continues the same sentinel
  with `wuwei runtime continue` and Agent `resume` set to the stopped seat's agent id;
  `build check` records the fast-check evidence the push guard reads.
- `docs/site/reference.md`: add a short "Seat briefs and the build loop" section with the
  same facts (body options, aliases, automatic phases, continuation, push evidence).
- `docs/site/concepts.md`: the seat launch contract line gains `--body TEXT` or
  `--file PATH`.
- `scripts/headless_e2e.py`: step 3 writes the brief with `--body`; step 4 drops
  `state transition A gate`; gate briefs use `--body`.

## Tests to update (behaviour changed on purpose)

- `tests/test_build.py`: `setup` load gains a `vcs` fake with `commit_context`, `head`
  and `status` so `build check` can record; `test_green_on_second_iteration_records_two_usages`
  expects phase `gate`.
- `tests/test_build_next.py`: `seat` fixture vcs gains `commit_context`.
- `tests/test_brief.py`: the `brief` helper passes `--file -` (or `--body`).
- `tests/fakes/day.py`: `brief` passes `--file -`; the vcs fake also uses the real
  `commit_context`, and the local git stub accepts calls that set `cwd` inside the day root
  (`commit_context` runs Git with `cwd`, not `-C`).
- `tests/test_templates_errors.py`: the `stand_down` cue is now `wuwei build next`.
- `tests/test_headless_e2e.py`: the brief step passes `--file -`.
- `tests/test_e2e_day.py`: drop `transition('implement')`, `transition('gate')` and
  `transition('delta')` in both tests; the recorded transitions list is unchanged.

## Deferred

- Spec-done gate for FULL items; `runtime dispatch` role aliases.
