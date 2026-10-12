# Implementation Plan: free-memory percentage floor and live seat count

**Branch**: `898-memory-floor` | **Spec**: `specs/898-memory-floor/spec.md`

## Technical Context

Python 3.11 stdlib only. No new module. Touches: `adapters/host/local.py`, `adapters/host/none.py`,
`cli/wuwei/registry.py` (the host interface), `cli/wuwei/guards/agent_launch.py`
(`free_percent` beside `free_memory`), `cli/wuwei/dispatch.py` (`host`, `launch_set`, second
opinion), `cli/wuwei/brief.py` (`live`, `stuck` reads the tail), `cli/wuwei/commands/doctor.py`,
`cli/wuwei/workspace.py`, `templates/workspace/config.toml`, `docs/site/configuration.md`. The
design spec is the owner's; this rule is not written there.

## Constitution Check

- Stdlib only, test first, shortest diff at the shared spot: `dispatch.host` is already called by
  every launch decision; the floor goes there once. The seat count gets one helper used by all
  three counters.
- No new wall in the hook (#837).

## Design

1. `free_percent()` on the host port. Local: darwin runs `memory_pressure` and parses
   `System-wide memory free percentage: N%`; linux reads `MemAvailable` and `MemTotal`. None:
   `record_none`.
2. `agent_launch.free_percent(config, root)`: the validated int 0-100, else ValueError (the
   test seam, like `free_memory`).
3. `dispatch.host`: when `host.min_free_memory_pct` is set, read it; `held` is
   `held: free memory N% < F%` below the floor, `held: <the adapter's reason>; bin/wuwei doctor
   tests the host adapter` when it fails. Text gains `; free memory N% (floor F%)`.
4. `launch_set.add`: an entry with at least one seat launch while `held` becomes
   `{'action': 'wait', 'reason': held, 'until': now + 60 s}`; a planned item waits before
   `build next` runs, so a held item is never bound, moved or claimed (review F1). `next.resolve` already turns an
   all-wait set with an `until` into a background sleep (#845).
5. `brief.live(data)`: running, not adhoc (the only seats registered without a brief), not in
   `stuck(data)`. `stuck` reads the
   transcript tail (`tail_turn`) since it now runs on each launch.
6. Doctor's memory row adds `N% free (floor F%)` or `floor off`; below either floor fails.

## Tests

`tests/test_brief_adapters.py`, `tests/test_adapters.py`, `tests/test_dispatch.py`,
`tests/test_next.py`, `tests/test_doctor.py`, `tests/test_workspace.py`,
`tests/test_config_transition.py` (upgrade), `tests/test_agent_launch.py`. Readings are injected; no test reads the machine.
