# Implementation Plan: the day starts in parallel

**Branch**: `474-parallel-dispatch` | **Spec**: `specs/474-parallel-dispatch/spec.md` |
**Issue**: #474

## Summary

Six small changes at the shared spots, no new module, key, adapter or dependency:

1. The launch guard records free memory and the running seat count on `seat launched`, and
   refuses builders at the day's approved CAP instead of `config['cap']`.
2. `metrics.seat_cost` turns those records into MiB per seat; `calibrate.host` turns cores,
   free memory and that cost into a proposed `cap`, which rides calibrate's existing config
   proposal rule.
3. `plan` derives a `seats` map per goal from the ranked queue (or takes the lead's), shows it
   in plan.md and the gate question, and records it as `goal_seats` on approval.
4. `dispatch.launch_set` loops the existing single-item functions over the approved items and
   returns the turn's launch set; `wuwei dispatch next --all` prints it.
5. `next` and `status --line` show running seats per goal and N of CAP; `next` names the seat
   that frees first when CAP is reached.
6. The plan skill says to emit a set's Agent launches in one message; lead charter and docs.

## Technical Context

Python 3.11+, stdlib only at runtime; pytest for tests. Run `python -m pytest -q` from the
repository root. The CLI is invoked only as `bin/wuwei` or `python3 -P -m wuwei`.

## Constitution Check

- I Stdlib: `os.cpu_count`, `statistics.median`, `collections.Counter`. Pass.
- II Three-state exits: an unmeasured host proposes nothing and `calibrate` exits 2 with the
  reason; `dispatch next --all` exits 1 when an entry is `refused` or `escalate`, 2 when the
  set cannot be computed. Pass.
- III One behaviour, one function: the launch set calls `next_step` and `build.next_action`;
  it does not re-implement gate or build logic. Pass.
- IV Test first: every task pair in tasks.md is test then implementation. Pass.
- V Ponytail: no new config key (`host.seats` is the issue's `max_seats`), no new module, the
  seats map is one `Counter`. Pass.
- VII Security: `goal_seats` is producer-owned (`plan approve` only); `cap` is producer-owned
  after approval; `host.seats` and the memory floor stay owner config read at every launch.
  Pass.

## Design

### 1. Launch guard: `cli/wuwei/guards/agent_launch.py` `_check`

- Build the event payload before `reserve` as a named dict
  (`payload = {'name': logged['name'], 'item': logged['item']}`) and, inside `reserve`, after
  `running` is computed, `payload.update(free_mib=available // 2**20, running=len(running))`
  (the pattern `plan.dispose` uses). Pass `payload=payload` to `state._write_state`.
- Line 182-183: `builders >= data['cap']` and the message names `data["cap"]`. `data` is the
  locked fresh state inside `reserve`. Keep the message text otherwise as is ("running build
  seats N at CAP M; wait for a build seat to finish, then retry").
- Nothing else in the guard changes: `host.seats`, the memory floor and the stale note stay.

### 2. Seat cost: `cli/wuwei/metrics.py`

```python
def seat_cost(events):
    """MiB one running seat takes: the median free-memory drop per running seat against the
    free memory at zero running seats, from `seat launched` records; unmeasured without both."""
    # ponytail: free-memory deltas include other processes; a per-seat probe if this misleads.
```

Read rows of kind `seat launched` whose payload has int `free_mib` and int `running` (older
rows have neither and are skipped). Baseline is the max `free_mib` at `running == 0`;
samples are `(baseline - free_mib) / running` for `running > 0`; return the rounded median
when it is above 0, else `UNMEASURED`. In `collect`, add `'seat_cost_mib'` to the
events-missing list and `seat_cost(events)` to `event_metrics`.

### 3. Host profile and CAP proposal: `cli/wuwei/calibrate.py`, `cli/wuwei/commands/calibrate.py`, `cli/wuwei/commands/config.py`

`calibrate.py`:

- `SEAT_MIB = 1024` with a `ponytail:` comment (default seat cost until a seat has run; the
  default memory floor).
- `host(root, config)`: free MiB through `guards.agent_launch.free_memory(config, root)` (the
  existing host-port reader; `ValueError` or `OSError` is `{'unmeasured': reason}`); cores
  from `os.cpu_count()` (None is unmeasured, with a reason that names a next step); seat MiB
  from `metrics.seat_cost(metrics._events(day) or [])` over `.wuwei/days/*` newest first, the
  first measured value wins, else `SEAT_MIB` with `seat_source = 'default'`. Return
  `{'cores', 'free_mib', 'seat_mib', 'seat_source', 'cap'}` with
  `cap = max(1, min((free_mib - host.free_memory_mb) // seat_mib, cores, host.seats))`
  (a negative fit counts as 0, so the result is still 1).
- `proposal(raw, targets, host=None)`: when `host` has `cap`, append `((), 'cap', host['cap'])`
  to `wanted`. The existing loop then adds it when absent and lists it as a hand edit when
  present and different. `propose(raw, results, settings=(), host=None)` passes it through.
- `report(..., host=None)`: a `## Host` section before `## Proposed config.toml changes`:
  `- cores: 8`, `- free memory: 10240 MiB (floor 1024 MiB)`, `- seat cost: 3072 MiB
  (measured)` or `(default, unmeasured until the first seats run)`, `- proposed cap: 3
  (host.seats 4)`; or `- unmeasured: <reason>`.

`commands/calibrate.py` `run`: compute `host = calibrate.host(root, config)` after `survey`,
pass it to `calibrate.propose(raw, results, host=host)` and to `record` (which passes it to
`report`). Print the host line; when `host` is unmeasured, print `wuwei calibrate: host
unmeasured: <reason>` to stderr and return `UNRUN` (same rule as an unmeasured commit
style).

`commands/config.py`: `proposal(root, raw, base, config, results, extra=(), host=None)`
passes `host` to `calibrate.propose`; `promote` passes `calibrate.host(root, config)`.
`setup` keeps calling `proposal` without `host` (no change to the setup flow).

### 4. Seats per goal: `cli/wuwei/plan.py`, `cli/wuwei/state.py`, `cli/wuwei/commands/plan.py`

`state.py` (light module, already imported by status and next):

```python
def running_by_goal(data):
    """{goal: running builder seats}, goals sorted; an item without a goal is unplanned."""

def goal_split(counts):
    return ', '.join(f'{goal} {count}' for goal, count in counts.items())
```

Add `'goal_seats': 'wuwei plan approve'` to `STATE_PRODUCERS`. Do not add it to
`OWNER_FIELDS`: everything not listed there is producer-owned by default.

`plan.py`:

- `goal_seats(candidates, cap)`: `dict(Counter(item.get('goal', 'unplanned') for item in
  candidates[:cap]))` (insertion order follows the queue).
- `seats_text(seats, cap)`: `'3 seats: G-1 2, G-2 1 (CAP 3)'`, or `'0 seats (CAP 3)'` when
  empty.
- `_proposal`: when `'seats' in data`, require a dict whose keys are in `data['goals']` or
  `'unplanned'`, whose values are `int` (not bool) of at least 1, and whose total is at most
  `data['cap']`; else `ValueError(f'seats must map confirmed goals to seat counts within cap;
  {PLAN_JSON}')`. Absent stays valid (`plan add` and older lead JSON).
- `propose`: after `rank.rank`, `data['seats'] = data.get('seats') or goal_seats(
  data['candidates'], data['cap'])`; in `## Gate proposal` add
  `'Seats per goal: ' + seats_text(data['seats'], data['cap'])` after `CAP:`.
- `gate_widget`: replace `f'CAP {data["cap"]}'` with `seats_text(data.get('seats') or
  goal_seats(data['candidates'], data['cap']), data['cap'])` (a proposal.json written before
  this change has no `seats`); the Change something text becomes "goals, queue, seat policy,
  CAP and seats per goal, envelope and carry-over".
- `approve`: add `goal_seats=data.get('seats') or goal_seats(data['candidates'],
  data['cap'])` to `current.update(...)`.

`commands/plan.py` `template`: `'cap': workspace.load_config(root)['cap']`.

### 5. Launch set: `cli/wuwei/dispatch.py`, `cli/wuwei/commands/dispatch.py`, `cli/wuwei/commands/next.py`

`commands/next.py`: extract the approved, not-disposed list `step` already computes into
`approved(data)` (same code, lines 70-75) and use it in `step`; `launch_set` reuses it.

`dispatch.py`:

```python
def launch_set(root=None):
    """The turn's launch set: each open approved item's next action, gates first, builders
    within CAP, launches within the free host.seats."""
```

- `data`, `config`; `running` = running seats (`brief.seats`); `free = config['host']['seats']
  - len(running)`; `building` = approved items in `state.BUILD_PHASES`; skip items with a
  running seat and items in `('raised', 'merged', 'parked', 'escalated')`.
- Gate group (`gate`, `delta`, in `approved` order): `value = next_step(item)`; a `Refused` is
  `{'action': 'refused', 'reason': str(exc)}`. Launch count = `len(value.get('seats', []))`
  (launch, continue and run alike). If the count is above `free`, the entry is
  `{'action': 'wait', 'reason': f'{n} gate seats do not fit the {free} free of host.seats=
  {config["host"]["seats"]}; they launch together next turn'}`; else `free -= n`.
- Build group (`state.BUILD_PHASES`): `build.next_action(item, root=root)`; `ValueError` or
  `PortExit` is `refused`; a `launch` or `continue` takes one free seat (`wait` when none).
- Planned group: order the planned items so that those within their goal's share of
  `data.get('goal_seats', {})` (counting items of that goal already building or started in
  this set) come first, the rest after, each in queue order. Take up to
  `data['cap'] - building` of them and one free seat each; for each, when a builder brief is
  logged (`brief.events`, kind `brief written`, role `builder`, this item) call
  `build.next_action` (it returns `launch` and moves the item to `implement`), else
  `{'action': 'start', 'commands': [f'wuwei worktree add {item}', f'wuwei brief builder
  {item} <name> --worktree <path>']}`. The rest are `{'action': 'wait', 'reason': f'CAP
  {cap} reached ({building} building); next names the seat expected to free first'}`.
- Every entry carries `item` and `goal`. Return `{'action': 'set', 'cap': data['cap'],
  'building': building, 'free_seats': free_at_start, 'entries': entries}`.
- Every new reason names a next step (the #362 ratchet in `tests/test_reasons.py`).

`commands/dispatch.py`: `step.add_argument('item', nargs='?')`,
`step.add_argument('--all', action='store_true')`; in `run`, `args.all == bool(args.item)`
raises `ValueError('pass one item or --all: bin/wuwei dispatch next <item> or bin/wuwei
dispatch next --all')` (exit 2). `--all` prints `json.dumps(dispatch.launch_set())` and
returns `FINDINGS` when any entry's action is `refused` or `escalate`, else `CLEAN`.

### 6. next and status: `cli/wuwei/commands/next.py`, `cli/wuwei/commands/status.py`

`next.step`:

- `dispatch` row (line 100): `startable = min(queued, data['cap'] - building)`; text
  `f'{startable} planned item(s) can start, {building} of CAP {cap} building; run the launch
  set, brief each start and launch the set in one turn.'`, command `wuwei dispatch next
  --all`.
- At CAP: remember the first planned item skipped because `building >= cap`. In the `wait`
  row, when one was remembered, name it and the running builder seat with the earliest
  `started_at`: `f'{label} waits: {building} of CAP {cap} building; {seat} started first
  ({started_at}) and is expected to free first; SubagentStop records each result.'`.
  Without a waiting item the row stays as today.

`status.snapshot`: `result['seats'] = state.running_by_goal(data)`. `status.line`: when
`data['gate_approved']`, append `f'seats {n} of CAP {cap}'` plus `f' ({state.goal_split(
seats)})'` when any run, where `n = sum(seats.values())`. Use `data.get('seats', {})` in
`line` so a cockpit snapshot built elsewhere still renders. The board needs no change: its
first line is `status.line`.

### 7. Skill, charter and docs

- `skills/wuwei-plan/SKILL.md`:
  - Step 2: the lead JSON may carry `seats` (goal to seats); the CLI derives it otherwise.
  - Step 4: the Approve description lists the seats line; Change something lists seats per
    goal.
  - New paragraph after step 5, "Parallel dispatch": after approval run `wuwei dispatch next
    --all`; for each `start`, run its commands (worktree, builder brief); run `--all` again;
    emit every `launch` and `continue` entry as Agent calls in one message (the harness runs
    Agent calls in one message concurrently; never launch one and wait before the next); run
    each `run` entry's command in the background with Bash; when the turn returns, do each
    item's next step (check, receive) and run `--all` again. `wait` entries name why; CAP and
    `host.seats` are checked per launch. With `cap = 1` the set holds one builder, as before.
  - Builder step loop and Item dispatch: say the per-item loop runs inside the set; gate
    seats of one item are launched in one message; replace "Launch those seats in parallel"
    with the one-message wording; the delta `continue` actions the same.
- `charters/lead.md` Capacity 1: "Propose `cap` from `config.toml` (`bin/wuwei calibrate`
  proposes it from the host). The CLI derives seats per goal from the ranked queue; pass
  `seats` only to change the split." Regenerate `agents/lead.md` with `python3 -P -m wuwei
  agents build`; bump the charter version if `tests/test_charters.py` or `test_agents.py`
  requires it.
- `docs/site/concepts.md`: CAP section in plain words (calibrate proposes, the gate approves
  the day's value with seats per goal, the launch guard enforces it, host.seats bounds it);
  a `### Seats per goal` entry.
- `docs/site/daily.md`: one paragraph on the parallel start; update the sample `next` line
  at line 218 to the new dispatch row.
- `docs/site/configuration.md`: `cap` row (calibrate proposes it from the host; the morning
  gate approves the day's value, which the launch guard enforces); `host.seats` row (also
  bounds calibrate's CAP proposal and each turn's launch set).

## Data and contracts

- Proposal JSON (lead input and `proposal.json`): optional `seats: {goal|"unplanned": int}`.
- Day state: `goal_seats` (producer `wuwei plan approve`).
- `seat launched` payload: adds `free_mib` (int, MiB) and `running` (int, seats running
  before this launch).
- `metrics.collect`: adds `seat_cost_mib` (int MiB or `unmeasured`).
- `wuwei dispatch next --all` stdout: `{"action": "set", "cap", "building", "free_seats",
  "entries": [{"item", "goal", "action": "launch|continue|check|gates|fix|raise|escalate|
  start|wait|refused|park|done", ...the single-item fields}]}`.

## What must not change

- `wuwei dispatch next <item>`, `receive`, `opinion`, `discovery` output and exits.
- `dispatch.next_step` gate logic (it already waits for every verdict); `build.next_action`.
- The launch guard's memory floor, `host.seats` ceiling, stale note, brief checks and the
  MCP gate; CAP still counts running builder seats only.
- `plan add` (intraday) behaviour; it still validates through `_proposal` without `seats`.
- calibrate's rule never to overwrite a present config value; `setup`'s summary.
- No new config key, adapter, module or dependency; no change to the telemetry vocabulary.

## Risks for the builder

- `tests/test_calibrate.py` runs calibrate through the real `local` host adapter by default;
  add a `fakes.host.Fake` (`free_memory`) to its port fixture and patch `os.cpu_count`, so no
  test runs `vm_stat`.
- `_labelled(raw)` must yield a top-level section with path `()` for `apply` to add an absent
  `cap`; check with a config that starts with a table.
- Existing tests pin `CAP 1` in the gate text, the `next` dispatch command and the guard
  reading config cap (`tests/test_agent_launch.py` writes `cap` to config.toml; those cases
  launch sentinels, so only builder cases move to day-state cap). Update the pins, not the
  behaviour they guard.
- `test_reasons.py` requires every new refusal and reason to name a next step.
- The parallel fixture test needs three items with builder briefs; if one worktree for three
  items is refused, give each item its own worktree through the git adapter in the test.
