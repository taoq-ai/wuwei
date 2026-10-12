# Implementation Plan: seats and pauses follow each runtime's usage window

**Branch**: `845-window-budget` | **Date**: 2026-10-12 | **Spec**: `specs/845-window-budget/spec.md`

**Input**: the spec, `research.md`, the code at v0.28.0 (`89f7a579`).

## Summary

The day budget becomes a window budget per runtime, at the spot that already owns it:
`dispatch.host`. One function, `dispatch.windows`, turns `seat.usage` tokens, the saved
readings and the config budgets into room per runtime. `dispatch.launch_set` holds a seat
launch whose runtime has no room (a `wait` with `until`) and routes a builder start to the
policy row's `alternate` when that has room. `next.resolve` turns a set held only by windows
into one timed wait row. Two small readers feed the readings: `wuwei status --line` (Claude,
stdin) and the codex adapter's `result` (the seat thread's rollout file). Nothing else moves.

## Technical Context

Python 3.11+, stdlib only at runtime; pytest for tests. Run the touched test files with
explicit paths; CI runs the suite. `next.step` and the hooks are not touched, so the hook
latency budget (#346) is unchanged: window room is computed only in `launch_set`,
`build.next_action` and `host`, none of which runs on a hook.

## Constitution Check

- I stdlib only: yes. The rollout read is a file read inside the codex adapter.
- II three-state exits: no new exit path. A damaged log or cache file never blocks a launch
  (as today's budget code); it is named in the capacity text.
- III one behaviour, one function: room is `dispatch.windows`, routing is `dispatch.route`,
  saving a reading is `dispatch.save_windows`. Each has one table test.
- IV test first: every implementation task in `tasks.md` follows its red test.
- V simplicity: no new module, no new event kind, no new command. The timed wait reuses the
  `background` then line. CAP keeps its day meaning; the window bound is applied where launches
  are counted.
- VII security: no guard loosens. The Agent guard reads the build record's runtime, which only
  the CLI writes. The codex thread id is validated before it names a file.

## Design

### Config (FR-001, FR-012)

`cli/wuwei/workspace.py` SCHEMA:

```python
"budget": {"claude": {"five_hour": (int, 0, 0), "seven_day": (int, 0, 0)},
           "codex": {"five_hour": (int, 0, 0), "seven_day": (int, 0, 0)}},
```

`workspace.RETIRED` gains `'budget.tokens_per_day'`; `init --upgrade` already removes and
reports a retired key (`commands/init.py` `_unread_keys`), so `init.py` does not change.
`templates/workspace/config.toml`: the commented `[budget]` block becomes commented
`[budget.claude]` and `[budget.codex]` blocks with the two keys each.

### Readings cache (FR-010, FR-011)

`.wuwei/windows.json`, a cache like `prs.json`, never an event:

```json
{"claude": {"five_hour": {"used_percent": 42.0, "resets_at": "2026-10-12T14:00:00+00:00"},
            "seven_day": {"used_percent": 18.0, "resets_at": "2026-10-16T09:00:00+00:00"}},
 "codex":  {"seven_day": {"used_percent": 88.0, "resets_at": "2026-10-18T11:09:27+00:00"}}}
```

`dispatch.save_windows(root, runtime, readings)`: keep each entry whose window is in
`WINDOWS`, whose `used_percent` is a finite non-negative number and whose `resets_at` parses
(`derive.when`); merge into the runtime's entry; write with `workspace.atomic_write` only when
the content changed. Invalid input is dropped, never raised: it is data from outside.

Writers:

- `commands/status.py` `run`: before the snapshot, when `sys.stdin` is not a tty, read it,
  `json.loads`, take `rate_limits.five_hour` and `rate_limits.seven_day`
  (`used_percentage`, `resets_at` epoch seconds, converted to ISO UTC) and call
  `save_windows(root, 'claude', ...)`. The whole read sits in one `try` catching
  `(OSError, ValueError, TypeError, AttributeError)`; the printed line is built as today.
- `adapters/runtime/codex.py` `result`: after the text, `output['windows'] = _windows(result_data.get('threadId'))`
  when it finds any. `_windows(thread)`: refuse a thread id that is not
  `[0-9A-Za-z-]+`; glob `$CODEX_HOME/sessions/*/*/*/rollout-*-<thread>.jsonl`
  (`CODEX_HOME` from `os.environ`, else `Path.home() / '.codex'`); scan its lines from the
  end for the first `"token_count"` event with a `rate_limits` object; map `primary` and
  `secondary` by `window_minutes` (300 to `five_hour`, 10080 to `seven_day`) to
  `{used_percent, resets_at ISO}`. Any `OSError`/`ValueError` gives `{}`.
- The CLI saves the Codex readings where it records a Codex result:
  `commands/build.py` `record_result` (when `result.get('windows')`, with the record's
  runtime) and `dispatch.opinion` (with `second['runtime']`).

### seat.usage names its runtime (FR-002)

- `commands/build.py` `record_result`: payload adds `'runtime': record['runtime']`.
- `dispatch.opinion`: the `seat.usage` payload adds `'runtime': second['runtime']`.
- `metrics.seat_tokens(events, runtime=None, default=None)`: when `runtime` is given, keep
  only rows whose `payload.get('runtime', default) == runtime`. Callers without `runtime`
  are unchanged.

### Room per runtime (FR-003, FR-004)

In `cli/wuwei/dispatch.py`, beside `host`:

```python
WINDOWS = {'five_hour': 300, 'seven_day': 10080}  # minutes; the two windows both runtimes share
```

`windows(root, config, runtimes)` returns `{runtime: {'room': int | None, 'until': iso | None,
'text': str}}` for each name in `runtimes` that has a `config['budget']` table (`claude`,
`codex`); any other name is absent (no bound). For each window:

1. reading = `windows.json[runtime][window]` when its `resets_at` is after `workspace.now()`.
2. start = reading reset minus the window length, else now minus the window length.
3. rows = `seat.usage` rows of this runtime (`payload.get('runtime', config['adapters']['runtime'])`)
   with `ts >= start`, read from the day directories whose date is on or after start's date
   (`metrics._events(day)`); counted = sum of their input plus output tokens.
4. used = `max(counted, budget * used_percent // 100)` when there is a reading, else counted.
5. per_seat = median of `metrics.seat_tokens(..., runtime, default)` over the newest day with
   such rows, else the median over all measured rows (today's rule in `host`).
6. room = 0 when the reading's `used_percent >= 100`; else `max(0, (budget - used) // per_seat)`
   when budget and per_seat; else None.
7. until = the reading's reset, else (the earliest counted row's `ts`, else now) plus the
   window length.

The runtime's room is the minimum over windows with a room (None when none has one); its
`until` is the `until` of a window with room 0 (the latest such, so the wait outlasts every
spent window), else the `until` of the window with the smallest room. `text`: `claude five_hour 250000 of 300000 used (reported 42%), room 0 until
2026-10-12T14:00:00+00:00`. A `ValueError` from a day log or the cache makes that runtime's
room None (a reading of 100 percent still gives 0) with the warning in `text`.
`ponytail:` comment: room counts only measured seats; gate sentinels on Claude are
unmeasured, so a reading is what catches them.

### CAP per runtime (FR-005)

Fix round (review F10): `host` keeps no `runtimes` flag and no per-runtime `cap`; `launch_set`
calls `windows(root, config, names)` itself and appends each row's text to its capacity. The
paragraph below is the original design.

`dispatch.host(root, config, running=0, free=None, policy=None, runtimes=False)`: delete the
`budget = config['budget']['tokens_per_day']` block (the `budget` bound; this also takes the
past-day log scan off the Agent guard's hook path). When `runtimes` is true, after CAP is set,
`found = windows(root, config, names)` where `names` is `adapters.runtime`, every seat policy
`runtime` and `alternate`, less `none`; return
`'runtimes': {name: {**row, 'cap': cap if row['room'] is None else min(cap, row['room'])}}`
and append each row's `text` to `text`. Only `launch_set` passes `runtimes=True`; the Agent
guard (`guards/agent_launch.py`, a PreToolUse hook), `dispatch.opinion` and `plan.propose`
keep their calls. `cap`, `seats`, `bound` keep their meaning, so `plan.propose`,
`state._validate` (cap at least 1) and the status line do not change.

### Routing (FR-008)

`dispatch.route(row, default, left)`: pure. `primary = row.get('runtime') or default`;
`alternate = row.get('alternate')`. Returns `primary` when `left.get(primary)` is None or
above 0, else `alternate` when it is set and `left.get(alternate)` is None or above 0, else
`primary`.

`cli/wuwei/plan.py` proposal validation: a seat policy row's optional `alternate` must be a
non-empty string, a valid runtime name (`registry.validate('runtime', name)`) and differ from
its `runtime`; else the existing `seat_policy` refusal.

`brief.seat_action(role, brief_path, worktree, root, runtime=None)`: `runtime` overrides the
`registry.runtime_config` lookup. `commands/build.py` `next_action(item, brief=None,
worktree=None, *, root=None, runtime=None)`: on the path that creates a new build record,
`runtime = runtime or dispatch.route(policy_row, config['adapters']['runtime'],
{name: row['room'] for name, row in dispatch.windows(root, config, ...).items()})` and pass it
to `seat_action`. An existing record keeps `record['runtime']` (fix rounds included, through
`open_fix`, which already copies `record['runtime']`).

### Holding and routing launches (FR-006, FR-009)

`dispatch.launch_set`:

- `left = {name: row['room'] for name, row in limits['runtimes'].items()}`; `until` likewise.
- In `add()`, count launches per runtime: each `seats` entry's `runtime`, else the value's
  `runtime` for an `action` in `launch`, `continue`, `start` or a `run` that carries a
  `runtime`. When any counted runtime has `left` below its count, the entry becomes
  `{'action': 'wait', 'reason': '<runtime> <window> window has no room for a seat; it resets
  at <until>', 'until': <until>}`; else `left` drops by the count. This sits beside the
  existing `host.seats` check and runs before it.
- Builder starts (the `first + rest` loop): `runtime = route(data['seat_policy'].get('builder',
  {}), config['adapters']['runtime'], left)`. A briefed item calls
  `build.next_action(name, root=root, runtime=runtime)`; an unbriefed `start` entry carries
  `'runtime': runtime` so `add()` counts it.

Built (deviation, 2026-10-12): the conversion below sits in `launch_set`'s `add()`, not in
`resolve_offer`, so a derived build step and a briefed planned item share it. When the resolved
action is `launch` or `continue` and its `runtime` is neither `claude` nor None, it becomes `{'kind': ..., 'action': 'run', 'runtime': runtime,
'command': 'wuwei build ' + ' '.join(map(shlex.quote, (item, brief, worktree)))}` with the
action's own `brief` and `worktree`. The planner runs `run` entries through Bash in the
background (THEN `set`, unchanged); the loop then runs in `build.run_loop`.

`commands/build.py` `run_loop`: the runtime is the build record's `runtime` when a record
exists, else `registry.runtime_config('builder', ...)`; the Claude refusal and
`registry.load` use that value.

`guards/agent_launch.py` (the `runtime = registry.runtime_config(role, ...)` line): for role
`builder`, `data['builds'][logged['item']]['runtime']` when that record exists wins.

### Timed wait (FR-007)

`commands/next.py` `resolve`, set branch: after `launches` is built, when every launch has an
`until` and the row has no duty and no decision, return

```python
_row('wait', f'{reasons}; running seats finish. wuwei next offers them again after the reset.',
     f'sleep {seconds}', 'background', until=until)
```

with `until` the earliest `until` and `seconds = max(60, ceil(until - now) + 60)`. THEN
`background` already says "run the command through Bash in the background; run wuwei next
when it exits". `next.step` does not change: SessionStart still shows the set.

### What must not change

- `next.step`, `derive.offers` and every hook path.
- The day CAP's meaning, `state._validate` (cap at least 1), `plan.propose` and the gate card,
  apart from the capacity text that now names windows instead of a day budget.
- The status line's printed bytes (SC-005).
- Running seats: no window rule stops, resumes or signals one (FR-013).
- Launches that are not seats: `pr act`, `merge`, `seat stop`, finding and park entries.
- The lead and steward rows of `next.step`.

## Files

Code (10): `cli/wuwei/workspace.py`, `cli/wuwei/metrics.py`, `cli/wuwei/dispatch.py`,
`cli/wuwei/brief.py`, `cli/wuwei/plan.py`, `cli/wuwei/commands/build.py`,
`cli/wuwei/commands/next.py`, `cli/wuwei/commands/status.py`,
`cli/wuwei/guards/agent_launch.py`, `adapters/runtime/codex.py`.

Templates and docs (4): `templates/workspace/config.toml`, `docs/site/configuration.md`
(`budget.*` rows, the `cap` row), `charters/lead.md` (CAP line: windows; seat policy
`alternate`), `docs/specs/2026-09-24-wuwei-design.md` 5.3 (an "Amended (owner, 2026-10-11,
#845)" line under the CAP bullet).

Tests (11): `tests/test_dispatch.py`, `tests/test_metrics.py`, `tests/test_parallel_dispatch.py`, `tests/test_next.py`,
`tests/test_signal_status.py`, `tests/test_runtime.py`, `tests/test_build_next.py`,
`tests/test_agent_launch.py`, `tests/test_plan.py`, `tests/test_workspace.py`,
`tests/test_config_transition.py`.

## Risks

- A Codex builder started from `next` is new: before this feature a Codex builder policy
  reached the planner as an Agent launch the guard refused. The `run` conversion is the
  smallest wiring; its test covers the command, and `run_loop` keeps its existing tests.
- Status line stdin: a pipe that never closes would block the line. Claude Code writes the
  JSON and closes stdin; a tty is skipped.
- The rollout format may change; the read degrades to no reading.
