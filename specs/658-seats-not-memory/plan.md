# Implementation Plan: the seat limit is not read from host memory when seats are subagents of one process

**Branch**: `658-seats-not-memory` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

One shared spot: `calibrate.host` (`cli/wuwei/calibrate.py:477`), which every capacity
caller already routes through. It learns which rule applies from the day's seat runtimes:
the subagent rule (`host.seats`, else one per core, no memory read) or the memory rule (the
existing estimate, smoothed as the `median_low` of today's last four recorded readings plus
the current one). The sweep records each reading on the `cap.derived` event it already
writes. The status line's seats token names the bound. `pace.seats` is untouched: it already
passes `cap` and `bound` through.

## Technical Context

Python 3.11+, stdlib only (`statistics.median_low` is already imported in `calibrate.py`);
pytest for tests. The launch guard runs on the hook path (#346): it passes the seat policy
it already holds, so no state read is added there. Under the subagent rule `host` does less
work than today (no free-memory port call, no seat-cost scan of past days).

## Constitution Check

- I (stdlib), II (exits): unchanged failure paths; free memory unreadable stays
  `unmeasured` under the memory rule, cores unreadable stays `unmeasured` under both.
- III (one behaviour, one function): the rule lives in `calibrate.host` and its one helper
  `processes`; callers only pass the policy they hold.
- IV (test first): every behaviour in `tasks.md` has its failing test before its code.
- V (ponytail): no new config key, no new event kind, no new state key. The readings ride on
  the reserved `cap.derived` event; the median is one stdlib call.
- VII (security): the free-memory floor refusal stays for every runtime. `cap.derived` is
  already reserved to `wuwei dispatch next --all` (`commands/event.py:44`), so a seat cannot
  forge readings that raise the cap.
- Invariant rule (Workflow): the launch guard's ceiling rule changes, so I20 (design 9.2 and
  `tests/test_invariants.py:665`) is amended to cover both rules.

## Design

### `cli/wuwei/calibrate.py`

New helper next to `host`:

```python
def processes(config, policy):
    """#658: True when a seat runtime of the day launches its own process: any runtime but
    the Claude subagent, and none launches nothing. policy: the seat policy, role to row."""
    rows = policy.values() if isinstance(policy, dict) else ()
    names = {config['adapters']['runtime'], *(row.get('runtime') for row in rows if isinstance(row, dict))}
    return bool(names - {'claude', 'none', None})
```

`host(root, config, running=0, free=None, policy=None)`:

1. Inside the existing `try` (so a damaged day state reports `unmeasured` with its reason,
   as an unreadable host does): `policy = state.read_state(root)['seat_policy']` when
   `policy is None`; `separate = processes(config, policy)`; read free memory only when
   `separate and free is None`; cores as today.
2. Memory rule (`separate`): the seat-cost scan and `seat_mib` as today, then

   ```python
   reading = max(1, min(running + max(0, (free - config['host']['free_memory_mb']) // seat_mib), cores))
   try:
       readings = [row['payload']['reading'] for row in metrics._events(workspace.day_dir(root)) or []
                   if row['kind'] == 'cap.derived' and type(row['payload'].get('reading')) is int][-4:]
   except ValueError as exc:
       readings, damaged = [], damaged or exc
   readings.append(reading)
   fit, rule = statistics.median_low(readings), 'memory'
   measured = ((f'median of {", ".join(map(str, readings))}; ' if len(readings) > 1 else '')
               + f'{_gb(free)} free, {_gb(seat_mib)} per seat, {cores} cores')
   ```

   and the result keeps `free_mib`, `seat_mib`, `seat_source` and adds `reading`.
3. Subagent rule: no seat-cost scan, no memory term:

   ```python
   fit, rule = owner_seats or cores, 'host.seats'
   measured = 'subagent runtime, free memory not read' + (
       '' if owner_seats else f'; host.seats unset, {cores} cores')
   ```

   The configured value is not repeated: `plan.md` already prints `; host.seats N` after
   the text, and the owner text prints the fit.

   and the result has no `free_mib`, `seat_mib`, `seat_source` or `reading`.
4. Shared tail, unchanged in shape: `seats = owner_seats or max(fit, len(ROLES))`;
   `cap, bound = (owner_cap, 'owner') if owner_cap else (min(fit, seats), rule)`; the owner
   text and `f'cap {cap} ({bound}): {measured}'`; the budget block, the `warning:` clause
   and the load average as today.

Check of the rule against the spec: subagent with `host.seats = 6` gives fit 6, seats 6,
CAP 6; unset on 10 cores gives 10, 10, 10; unset on 2 cores gives fit 2, seats 3, CAP 2
(the gate still fits, `test_host_seat_ceiling_holds_one_gate_on_a_two_core_host` stays
green unchanged). Memory with readings 8, 4, 6, 8 and a current 4 gives
`median_low([8, 4, 6, 8, 4]) == 6`.

`report` (`calibrate.py:869`): print the `free memory` and `seat cost` lines only when
`'free_mib' in host`; cores and `derived:` stay.

### Callers: pass the policy they already hold

| File and line | Change |
|---|---|
| `cli/wuwei/dispatch.py:396` (`launch_set`) | `policy=data['seat_policy']` |
| `cli/wuwei/dispatch.py:736` (`opinion`) | `policy=data['seat_policy']` |
| `cli/wuwei/guards/agent_launch.py:185` | `policy=data['seat_policy']` (the locked `data` of `reserve`; no extra read on the hook path) |
| `cli/wuwei/commands/pace.py:15` | `policy=data['seat_policy']` |
| `cli/wuwei/plan.py:189` (`propose`) | `policy=data.get('seat_policy')`: the proposal's policy is the day's before approval; `_proposal` validates it right after |
| `cli/wuwei/commands/plan.py:61`, `cli/wuwei/commands/calibrate.py:49` | unchanged: `host` reads today's state |

### `cli/wuwei/dispatch.py` `launch_set` (lines 400 to 402)

Record the reading at every approved sweep under the memory rule:

```python
if data['gate_approved'] and ((data['cap'], data['cap_bound']) != (cap, bound) or 'reading' in limits):
    state._write_state(lambda fresh: fresh.update(cap=cap, cap_bound=bound), root, reserved=False,
                       kind='cap.derived', payload={'cap': cap, 'bound': bound, 'text': limits['text'],
                                                    **{key: limits[key] for key in ('reading',) if key in limits}})
```

Under the subagent rule nothing changes: one `cap.derived` only when CAP or the bound moves.

### `cli/wuwei/commands/status.py`

`_groups` line 379, the seats token carries the bound:

```python
work.append(f'seats {len(roles)}/{data["cap"]}' + (f' by {data["cap_bound"]}' if data.get('cap_bound') else '')
            + (f' ({", ".join(names)})' if names else ''))
```

`full` lines 416 and 417: delete the separate `bound X` token (the seats token carries it).
`line`'s cutting is unchanged: roles first, then whole tokens.

## Must not change

- `pace.seats`, `pace.advise` (they read `cap`, `bound`, `cores`, `load` as today).
- The free-memory floor refusal in `guards/agent_launch.py:123` to `126`, the heartbeat
  `memory` probe (`heartbeat.py:114`), the remote session floor (`remote.py:373`).
- `metrics.seat_cost` and the `seat launched` payload (`free_mib`, `running`).
- The budget bound, the `unmeasured` fallback dict, the `load` key and the `held by load`
  attention token.
- `state.RESERVED` and the reserved event kinds (no new key or kind).
- `status --json` (`cap_bound` stays a field).

## Docs and design spec

- `docs/specs/2026-09-24-wuwei-design.md`: an `Amended (owner, 2026-10-10, #658)` sentence
  after the #528 CAP paragraph (line 562 to 571): the memory estimate applies only when a
  seat runtime of the day launches its own process, smoothed as the median of today's last
  five readings, bound `memory`; Claude subagent seats take `host.seats`, else one per core,
  bound `host.seats`, and free memory is not read; the floor still refuses. Line 571's bound
  list becomes `memory`, `host.seats`, `budget`, `owner`, `unmeasured`. Line 597:
  `host.seats` derives "per the #658 rule". Status line (line 1024): the seats token reads
  `seats 4/1 by host.seats (lead, arch, +2 more)`. 9.2 I20 (line 1975): both rules.
- `docs/site/concepts.md` lines 246 and 352: the two rules, the example text
  `cap 4 (memory): median of 4, 5, 4; 16 GB free, 1.5 GB per seat, 8 cores` and the status
  line `seats 3/4 by memory` or `by host.seats`.
- `docs/site/configuration.md` line 27 (`cap`) and line 128 (`host.seats`): under the Claude
  subagent runtime `0` means one per core and free memory is not read; the memory estimate
  applies only to process runtimes.

## Files

| File | Change |
|---|---|
| `cli/wuwei/calibrate.py` | `processes`; `host` two rules, readings, `policy`; `report` memory lines optional |
| `cli/wuwei/dispatch.py` | pass `policy` (two calls); `cap.derived` carries `reading` each memory sweep |
| `cli/wuwei/guards/agent_launch.py` | pass `policy` |
| `cli/wuwei/commands/pace.py` | pass `policy` |
| `cli/wuwei/plan.py` | pass the proposal's `policy` |
| `cli/wuwei/commands/status.py` | seats token `by <bound>`; `full` drops `bound X` |
| `tests/test_calibrate.py` | new rule tests; memory tests pass a process policy |
| `tests/test_parallel_dispatch.py` | subagent and memory sweep tests; memory tests on a process runtime |
| `tests/test_agent_launch.py` | subagent launch at the floor admitted; memory-based cases on a process runtime |
| `tests/test_signal_status.py` | seats token with the bound; `full` without `bound X` |
| `tests/test_invariants.py` | I20 both rules |
| `tests/test_pace.py`, `tests/test_e2e_day.py`, `tests/test_board_mcp.py` | only where the line or bound text moved |
| `docs/specs/2026-09-24-wuwei-design.md`, `docs/site/concepts.md`, `docs/site/configuration.md` | as above |

## Existing tests that pin the old behaviour

They assumed the memory rule on the default `claude` runtime. Each one either moves to a
process runtime (unit tests: pass `policy=PROCESS` with
`PROCESS = {'builder': {'runtime': 'codex', 'model': 'm'}}`; day tests: `approved` with a
`codex` builder in `seat_policy`, or `[adapters]\nruntime = "codex"` in config, which loads
clean) to keep testing the memory rule, or keeps the default runtime and asserts the
subagent rule. Do not delete a memory assertion without moving it.

- `tests/test_calibrate.py`: `test_host_derives_cap_and_seats` (process; bound `memory`;
  the owner `host.seats = 2` case gives bound `memory`), `test_host_falls_back_when_a_past_day_log_is_damaged`
  and `test_token_budget_bounds_cap` (process, texts keep `GB free`),
  `test_calibrate_measures_the_host_and_never_proposes_cap` (process config so the report
  keeps the memory lines). `test_host_seat_ceiling_holds_one_gate_on_a_two_core_host` stays.
- `tests/test_parallel_dispatch.py`: `test_fresh_workspace_derives_cap_from_the_host_and_starts_four`
  (default runtime: `cap 4 (host.seats): subagent runtime, free memory not read; host.seats
  unset, 4 cores`, bound `host.seats`, `seats 0/4 by host.seats`),
  `test_owner_cap_names_what_the_host_fits` (owner text with the subagent clause),
  `test_cap_follows_free_memory_at_each_sweep` (process runtime; with smoothing the second
  sweep's CAP is `median_low([2, 4]) == 2`, so the test now shows the median holding and a
  `reading` on every sweep's `cap.derived`), `test_token_budget_fitting_two_seats_starts_two`
  (`seats 0/2 by budget`; `bound budget` leaves `wuwei status`),
  `test_launch_guard_compares_with_the_cap_derived_at_launch` (default runtime: D now
  launches; the memory refusal moves to a process-runtime variant).
- `tests/test_agent_launch.py`: cases that monkeypatch `free_memory` to drive CAP or the
  ceiling (`test_build_cap_and_host_seat_ceiling`, `test_stale_reservation_is_named`,
  `test_default_capacity_fits_builder_and_three_gates`, `test_builder_cap_is_derived_at_launch`):
  run them and keep the floor ones as they are; move only those whose expectation came from
  the memory fit.
- `tests/test_signal_status.py:966` to `968`: `budget` leaves the moved list (the line now
  shows `by budget`), `bound` stays in it; `:1063`: `seats 4/1 by budget (lead, arch,
  quality, security) · builders G-1 2`.
- `tests/test_invariants.py:665` `i20`: pass `policy=PROCESS` for the memory cases (the
  `seat_mib` lookup too) and add the subagent cases (`policy={}` on the default runtime):
  for every free value, CAP is `cap or cores` (`host.seats` is 0 in the base config), the
  same across free values, and the budget never raises it.
