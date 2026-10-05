# Implementation Plan: CAP and host.seats come from the measured host and a token budget

**Branch**: `528-cap-from-host` | **Date**: 2026-10-05 | **Spec**: `spec.md`

## Summary

Extend the existing `calibrate.host` (#474) into the one capacity function, make `cap` and
`host.seats` default to 0 (derived), add `[budget] tokens_per_day`, and call that function at
the three enforcement points (launch set, launch guard, opinion) and at plan propose. The day
state keeps a snapshot (`cap`, new `cap_bound`) for the status line and `next`. Calibrate stops
proposing `cap` into config. No new refusal; refusal texts and posture handling unchanged.

## Technical Context

Python 3.11 stdlib only; pytest for tests. Run `python -m pytest -q` from the repository
root. The CLI is the only writer of state; writes go through `state._write_state`.

## Constitution Check

- Stdlib only: yes (`os.cpu_count`, `statistics.median`).
- Three-state exits: unchanged; an unmeasured host is labelled, never counted as measured.
- One behaviour, one function: capacity lives only in `calibrate.host`; every caller uses it.
- Test first: every behaviour below has a test task before its implementation task.
- Ponytail: no new module, no new port; one new config key, one new state key, one new event
  kind.
- Autonomy (#530): no new refusal under observe or guarded.
- Telemetry constraint ("aggregation runs only in CLI commands", design 5.13): not touched.
  The token reading is the budget path of design 5.3 (`seat.usage` per iteration) and 15.8
  ("a launch that would cross the cap is refused by the agent-launch guard"), which places
  budget enforcement on `seat.usage` in the launch guard; the bound applies the owner's own
  `tokens_per_day`, and the hook adds no record. The guard already reads the day's events for
  briefs, so the extra read is of the same order (#346 latency).

## Design

### 1. The shared helper: `calibrate.host` (cli/wuwei/calibrate.py:442-465)

Change the signature to `host(root, config, running=0, free=None)`; `free` is MiB when the
caller already measured it (the guard), else measured through
`agent_launch.free_memory` as now.

- `fit = running + max(0, (free - floor) // seat_mib)`, then `min(fit, cores)`, at least 1.
  `seat_mib` and `seat_source` exactly as today (latest day with a measured
  `metrics.seat_cost`, else `SEAT_MIB`).
- `seats = config['host']['seats'] or fit`.
- `cap, bound = (config['cap'], 'owner') if config['cap'] else (min(fit, seats), 'host')`.
- Budget, only when `config['budget']['tokens_per_day']`: per-seat tokens = median of
  `metrics.seat_tokens(events)` on the newest day directory that has any; used = sum of
  `seat_tokens` for today's day directory; `fits = max(1, (tokens_per_day - used) //
  per_seat)`; when `fits < cap`: `cap, bound = fits, 'budget'`. Per-seat unmeasured: no
  bound, the text says so.
- Returns the existing keys (`cores`, `free_mib`, `seat_mib`, `seat_source`, `cap`) plus
  `seats`, `bound` and `text`. Text shape, GB rounded with `:g` to one decimal:
  `cap 4 (host): 16 GB free, 1.5 GB per seat, 8 cores`; owner below the host:
  `cap 1 (owner): config cap; the host fits 4 (16 GB free, 1.5 GB per seat, 8 cores)`;
  budget suffix `; budget 200000 tokens a day, 0 used, 100000 per seat`.
- Unmeasured (memory read raises, or cores None): return `{'unmeasured': reason, 'cap':
  config['cap'] or 1, 'seats': config['host']['seats'] or 4, 'bound': 'unmeasured',
  'text': f'cap {n} (unmeasured): {reason}'}`. `commands/calibrate.py:67` keeps working
  (`'unmeasured' in host`).
- `# ponytail:` comment: the budget counts tokens already spent today, not what running
  seats will still spend; a per-seat reservation if this overshoots.

### 2. Per-seat tokens: `metrics.seat_tokens(events)` (cli/wuwei/metrics.py, next to `seat_cost` at :488)

Returns the list of `input_tokens + output_tokens` for each `seat.usage` row where both are
ints (rows with `unmeasured` skipped). The caller takes the median or the sum. Reuse
`metrics._events(day)` to read a day, as `calibrate.host` does for `seat_cost`.

### 3. Config schema and template

- `cli/wuwei/workspace.py:82`: `"cap": (int, 0, 0)`.
- `cli/wuwei/workspace.py:112`: `"seats": (int, 0, 0)` inside `host`.
- New top-level `"budget": {"tokens_per_day": (int, 0, 0)}` in `SCHEMA`.
- `templates/workspace/config.toml`: line 2-3 become a comment saying 0 derives CAP from the
  host and the token budget at every sweep and a number pins it, then `cap = 0`; `[host]`
  `seats = 0 # 0 derives the seat ceiling from free memory and cores; a number pins it.`;
  a commented `# [budget]` / `# tokens_per_day = 0` block naming 0 as no budget.

### 4. Plan (cli/wuwei/plan.py, cli/wuwei/commands/plan.py)

- `propose` (plan.py:137): before `_proposal`, `limits = calibrate.host(root, config)`;
  `data = {**data, 'cap': limits['cap'], 'capacity': {'bound': limits['bound'], 'text':
  limits['text'], 'seats': limits['seats']}}`. The `## Gate proposal` block (plan.py:202-203)
  writes `CAP: {text}; host.seats {seats}` in place of `CAP: {cap}`.
- `gate_widget` (plan.py:218-240): the `Approve` description gets the capacity text after
  the seats line; `Change something` says `CAP (derived; a changed CAP is recorded as config
  cap)`. Read `data.get('capacity')` so a proposal written before this change still renders.
- `approve` (plan.py:319): also `cap_bound=data.get('capacity', {}).get('bound', '')`.
- `commands/plan.py:59` (`template`): print `calibrate.host(root, config)['cap']` instead of
  `config['cap']`.

### 5. Day state (cli/wuwei/state.py)

- `DAY_DEFAULTS` (:40): add `'cap_bound': ''`.
- `STATE_PRODUCERS` (:233): `'cap': 'wuwei plan approve or wuwei dispatch next --all'`,
  `'cap_bound'` the same.

### 6. Launch set (cli/wuwei/dispatch.py:245-304)

- After `running` is computed: `limits = calibrate.host(root, config, running=len(running))`;
  `cap, ceiling = limits['cap'], limits['seats']` replace `data['cap']` and
  `config['host']['seats']`.
- When `data['gate_approved']` and `(data['cap'], data['cap_bound']) != (cap, bound)`: one
  `state._write_state(..., reserved=False, kind='cap.derived', payload={'cap', 'bound',
  'text'})` setting both. Unchanged values write nothing.
- Return value adds `'bound'` and `'capacity'` (the text). The `wait` reasons keep naming
  `CAP` and `host.seats=` with the derived numbers.

### 7. Launch guard and opinion

- `cli/wuwei/guards/agent_launch.py:174-179`, inside `reserve`: `limits =
  calibrate.host(root, config, running=len(running), free=available // 2**20)` (lazy import,
  hook path); compare builders with `limits['cap']` and `len(running)` with
  `limits['seats']`. Messages unchanged apart from the numbers.
- `cli/wuwei/dispatch.py:506-507` (`opinion`): ceiling from `calibrate.host(root, config,
  running=<that count>)['seats']`.

### 8. Status line (cli/wuwei/commands/status.py)

- `snapshot` (:247): add `'cap_bound': data['cap_bound']`.
- `line` (:349-351): `seats {n}/{cap}` followed by `({bound}; {goal split})`, each part only
  when present, e.g. `seats 3/4 (host; G-1 2, G-2 1)`, `seats 0/4 (host)`.

### 9. Calibrate stops proposing cap

- Delete `calibrate.py:494-495` and the `host` parameter of `calibrate.proposal` and
  `calibrate.propose`; drop `host=` at `commands/calibrate.py:55`, `commands/config.py:209`
  and `:270` (and the `host` parameter of `commands/config.proposal`).
- `calibrate.report` (:680-684): the last host line becomes `- derived: {host['text']}`.

### 10. Event kind

- `cli/wuwei/commands/event.py`: reserve `'cap.derived': 'wuwei dispatch next --all'`.
- `cli/wuwei/signal.py:10-28`: add `'cap.derived'` to the quiet kinds.

### 11. Docs

`skills/wuwei-plan/SKILL.md` (lines 23, 29, 59: the lead does not set `cap`; CAP and
`host.seats` derive; the override keys; no "default cap of one"), `charters/lead.md:10`,
`charters/planner.md:11` (CAP at the gate is derived, a change is config `cap`),
`docs/site/configuration.md` (rows `cap`, `host.seats`, new `budget.tokens_per_day`; keep the
words `calibrate` and `morning gate` in the `cap` row, a test reads them),
`docs/site/concepts.md:227,329`, `docs/site/reference.md:89`, and design 5.3
(`docs/specs/2026-09-24-wuwei-design.md:471` and `:496-497`) with a dated line
`Amended (owner, 2026-10-05, #528)`.

## What must not change

- The memory floor check (`agent_launch.py:123-126`) and its message.
- The refusal texts for CAP and `host.seats` (only the numbers come from the derivation),
  the posture handling of the `seats` area, and the records floor.
- `state._validate` requiring `cap >= 1`.
- `metrics.seat_cost`, `launch_set` ordering, goal shares and the `wait` entries' shape.
- Every refusal under observe and guarded stays what it was; no new refusal.

## Test fallout to expect

The defaults move from 1 and 4 to derived, so tests that assumed them need an explicit value
or pinned inputs. Prefer pinning `os.cpu_count` (to 4) in the `Day` fixture
(`tests/fakes/day.py`) and keeping its host fake (8 GiB free) reachable as `day.memory`; add
`cap = 1` to a fixture config only where a test's assertions depend on one builder. Expect
updates in `tests/test_workspace.py` (defaults), `tests/test_calibrate.py` (no cap in the
config proposal; `raw = 'cap = 1...'` cases), `tests/test_signal_status.py` and
`tests/test_parallel_dispatch.py` (status line text), `tests/test_agent_launch.py`.

## Project Structure

No new files outside tests. Tests go in existing files: `tests/test_calibrate.py`,
`tests/test_metrics.py`, `tests/test_parallel_dispatch.py`, `tests/test_workspace.py`.
