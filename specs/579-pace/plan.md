# Implementation Plan: Day pace (careful, steady, fast)

**Branch**: `579-pace` | **Spec**: `specs/579-pace/spec.md` | **Issue**: #579

## Summary

One new module, `cli/wuwei/pace.py`, holds the pace: the three names, the day's current
value, the one pure rule that adjusts a tier record (`adjust`), the seats rule (`seats`),
the advice (`advise`), the host line and the default-pace card. Every other change is a
call into it from the place that already owns the knob: `dispatch.tier` (tier and depth,
#280 and #567), `dispatch.launch_set` (seats, #528), `fast_checks.commands` (local checks
and push evidence), `plan.propose`, `plan.gate_widget`, `plan.approve`, `plan set`
(the gate and the day), `status`, `metrics`, `report` and `retro` (visibility and
measurement). No second tier, no second depth table, no new refusal, no new guard.

## Precondition

#567 is on `main` (PR #577, a2ad2d1) but not on this worktree's base (b6daa42), which also
predates #559 and #560 (design 9.2 rows I12 to I14). Bring the branch up to `main` before
T001 (the branch holds only these spec files). This plan calls #567's `dispatch.depth`,
`dispatch.step_zero`, `dispatch.GUARD_CODE`, `dispatch.CLASS_PATHS`, `dispatch._changes`,
`brief.depth_line`, `verdict.light`, `metrics.cycles`, `metrics.cycle_by_tier` and
`metrics.CYCLE_TARGETS`. If they are missing at build time, stop and report; do not
re-implement them.

## Technical Context

Python 3.11 stdlib, pytest for tests. Touched modules: `pace.py` (new), `dispatch.py`,
`calibrate.py`, `fast_checks.py`, `commands/build.py`, `guards/commit_push.py`, `brief.py`,
`guards/verdict.py`, `guards/protect_state.py`, `commands/sweep.py`, `plan.py`, `commands/plan.py`,
`commands/pace.py` (new), `commands/__init__.py`, `commands/next.py` (gate THEN text),
`commands/status.py`, `state.py`, `workspace.py`, `metrics.py`, `report.py`, `retro.py`,
docs, design. Tests: run only the touched test files.

## Constitution Check

- I stdlib only: `os.getloadavg`, `statistics.median`, `shlex.quote`; no dependency.
- II three-state exits: `wuwei pace` exits 0 or 2 with the reason; `plan approve --pace` and
  `plan set pace=` exit 2 on an unknown value; an unmeasured load or budget is printed as
  unmeasured, never as clean; a diff that cannot be read never lightens depth.
- III one behaviour, one function: the pace rule in `pace.adjust`, the seats rule in
  `pace.seats`, the checks list in `fast_checks.commands`, the advice in `pace.advise`; all
  callers reuse them.
- IV test first: every task pair in `tasks.md` is test then code.
- V ponytail: one module, one pure rule, two config keys, no new event kinds beyond
  `pace.set` and `pace.carded`.
- VII security and #530: the pace never adds a refusal and never lowers a floor; `pace` is
  producer-owned state; the agent-launch guard and the merge policy do not read it. The push
  guard reads it only to pick which recorded checks count as evidence; under observe and
  guarded a missing record stays a warning or card (#530), under strict a refusal.

## Changes

### `cli/wuwei/pace.py` (new)

- `PACES = ('careful', 'steady', 'fast')` (slowest first; "the slower pace" is the lower
  index).
- `current(data, config)`: `data.get('pace') or config['pace']['default']`.
- `label(answer, recommended)`: `Approve` (with or without ` (Recommended)`) -> recommended;
  `Approve at <p>` or `<p>` -> p; anything else `ValueError` naming the paces and saying
  Change something asks the separate questions.
- `adjust(pace, effective, guard, flagged, measured)`: pure. `guard` is the reason string
  when the diff touches guard code or a trust path, else None; `flagged` is any lead flag or
  a FULL track; `measured` is whether the diff was read. Returns `(tier, depth, reasons)`:
  - careful: `guard` raises to full (`pace careful: <guard>`); light rises to standard
    (`pace careful`).
  - fast: `guard` raises to full (`pace fast: <guard>`); a standard tier with `measured`,
    no `guard` and not `flagged` keeps `tier` standard and returns `depth` light (`pace
    fast: light depth`).
  - steady: `(effective, effective, [])`.
  Never returns a tier below `effective` (I15 walks every combination).
- `seats(pace, limits)`: `(cap, bound, hold)`: careful `max(1, cap - 1)`, bound `pace
  careful`; fast with `limits['load']` not None and `>= limits['cores']`: same cap, bound
  `load`, `hold` = `host load {load:.1f} at or over {cores} cores (pace fast); the next seat
  launches when the load falls below {cores}`; otherwise `limits` unchanged and `hold` None.
- `predict(candidate)`: the lead `tier`, else `full` for a FULL track, else `standard`.
- `guard_items(candidates, trust_paths)`: ids whose `paths` match through
  `dispatch.step_zero('standard', paths, trust_paths)` (#567; no new matcher).
- `advise(root, config, candidates, goal_ids, limits, now)`: returns `{pace, lines, seats,
  close, binding, unlock, reach, wish}`:
  - queue input: careful when `guard_items` is not empty (`<n> items touching guard code:
    careful`, unlock `steady unlocks once they merge`); fast when the nearest goal date of
    the queue's goals (`goals.parse` `date`) is at most two days away or the expected close
    at steady is after `envelope.end`; else steady.
  - expected minutes per item: the median for its depth at that pace from
    `metrics.cycle_by_tier(metrics.cycles(root))`, else `metrics.CYCLE_TARGETS` (light 60,
    standard 180) and full 360 (`ponytail:` constant). Close = now + sum / seats.
  - host input: a ceiling of steady when `limits['load'] >= limits['cores']` (unlock `fast
    unlocks when the load average falls below <cores>`); else none.
  - result = the slower of queue and host; binding = `host` when the host lowered it, else
    `queue`.
  - budget: when `limits['per_seat_tokens']` is set, reach = items whose `per_seat x seats`
    (1 + 1 at light depth, 1 + 3 otherwise) fit `tokens_per_day - used_tokens`, in queue
    order; when reach < queue length, binding = `budget` and the line says `budget reaches
    <k> of <n> items at <pace>: advised against`. The budget never changes the pace.
  - wish = `config['pace']['default']`; when it differs, a third line `Your default is
    <wish>; the advice is <pace> (binding: <binding>)`.
  - line 1: `<n> items, <a> light, <b> standard, <c> full[, <G-n> due <date>]: <pace>,
    <seats> seats, expected close <HH:MM>`; line 2: `Host <cores> cores, load <x|unmeasured>,
    last suite <m min|unmeasured>; <budget part>; binding: <input>[; <unlock>]`.
- `host_line(root, limits, config)`: the host part of line 2. The last suite duration is
  the `seconds` of the newest `fast_checks` record whose command is exactly a configured
  `repos.tests`, searching day states newest first (as `calibrate.host` searches days for
  the seat cost), so the morning gate shows yesterday's run; `unmeasured` when none.
- `propose_default(root, config)`: when `metrics.by_pace(root)` has at least ten days in
  total across at least two paces and no day in the last ten holds `pace_card`, write one
  card with `grants._record` (option titles `pace.default = "<p>"`, one per measured pace,
  the numbers in the context; recommendation: the fewest escaped per merged item, ties to
  the higher merged per day; a pace with more escaped per merged than another gets its own
  context line) through `decision.write` and `decision.route_owner` (as `cruise._card`), and
  record `pace_card = {id, at}` in day state (event `pace.carded`). Returns the D-n or None.

### `cli/wuwei/dispatch.py` (on #567)

- `tier`: after the floor and lead-tier lines, call `pace.adjust(pace.current(state,
  config), effective, guard, flagged, measured)` where `guard` is the reason from
  `step_zero('standard', paths, trust_paths)` when it runs, `flagged` is any lead flag or
  track FULL, `measured` is `repo is not None`. Set `effective`, extend `reasons`, and add
  `record['depth']`. `roles` and `second_opinion` follow the (possibly raised) tier as today.
  The state read is wrapped: an unreadable day state means steady (today's record).
- `depth(row, gate=False)`: prefer `gates.depth`, then `gates.tier`, then (not for gates)
  `row.depth`, then standard.
- `classes`: decide light from `record['depth']` instead of `record['tier']`.
- `launch_set`: after `calibrate.host`, `cap, bound, hold = pace.seats(current, limits)`;
  the existing `cap.derived` write records the new `(cap, bound)`; inside `add`, when `hold`
  and the entry would launch, the entry is `wait` with `hold` as the reason. Gate and fix
  entries wait like builds (every seat adds load).

### `cli/wuwei/calibrate.py`

- `host`: add `load` (`os.getloadavg()[0]` rounded to one decimal, None on `OSError` or
  `AttributeError`), `per_seat_tokens` and `used_tokens` (the values it already computes,
  None when unmeasured) to every returned dict, and `load <x>` to `text`.
  The unmeasured branch returns `load: None`.

### `cli/wuwei/fast_checks.py`

- `commands(root, config, repo, tree)`: the pace's checks (spec FR-010). Changed test files
  come from `dispatch._changes(root, config, {'worktree': str(tree)})` filtered with
  `merge.matched(path, TEST globs from dispatch.CLASS_PATHS)` and `(tree / path).is_file()`,
  appended with `shlex.quote`. Any error reading the diff returns `repo['fast_checks']`.
- `record`: iterate `commands(...)` instead of `repo['fast_checks']`; each record gains
  `seconds` (rounded `time.monotonic()` difference); return value unchanged.

### `cli/wuwei/commands/build.py`

- `check`: after `fast_checks.record`, take the commands from `fast_checks.commands` for the
  record's worktree and store them as `marked['commands']` before the completeness check, so
  a fast or careful build compares against what the pace ran. `next_action` keeps
  `repo['fast_checks']` as the initial value (the diff is empty at build start).

### `cli/wuwei/guards/commit_push.py`

- `fast_evidence`: iterate `fast_checks.commands(root, workspace.load_config(root), repo,
  path)` (lazy import) instead of `repo['fast_checks']`. Messages unchanged. The #530
  levelling through `grants.evidence` is unchanged.

### `cli/wuwei/brief.py`

- `write`, builder branch: use `tier(...)['depth']` for the `Depth:` line and
  `items.<item>.depth`; append one `Checks:` line: steady `Checks: steady; the fast checks;
  CI runs the suite on the PR`; careful `Checks: careful; the fast checks and <tests> before
  the PR` (or `the full suite is not configured locally (repos.tests); CI runs it`); fast
  `Checks: fast; <tests> on the test files your diff changes, never the full suite; CI is
  the gate` (or the steady line when `repos.tests` is empty). `wuwei build check` runs them.

### `cli/wuwei/guards/verdict.py`

- `_light` (#567): the builder branch reads `tier(...)['depth']`.

### `cli/wuwei/commands/sweep.py`

- `classes` (#567): print by `record['depth']`.

### `cli/wuwei/state.py`, `cli/wuwei/workspace.py`

- `STATE_PRODUCERS`: `'pace': 'wuwei plan approve or wuwei plan set pace='`, `'pace_card':
  'wuwei plan propose'`.
- Config schema: `"pace": {"default": (str, "steady", ("careful", "steady", "fast"))}`;
  `repos[].tests: (str, "")`.

### `cli/wuwei/plan.py`

- `_proposal`: optional candidate `paths`, a list of strings.
- `propose`: after `calibrate.host`, `advice = pace.advise(...)`; store `pace`,
  `pace_reasoning` (the lines) and `pace_advice` in `data`; under `## Gate proposal` add
  `Pace: <pace> (recommended)` and the lines; call `pace.propose_default` beside
  `cruise.propose`.
- `gate_widget`: options `Approve` (description: `approves` plus ` Pace <pace>.` and the
  reasoning lines), `Approve at <p>` for the two other paces (same approvals, that pace),
  `Change something`. Record: the approve command plus `--pace "<label>"`.
- `approve(items, ..., pace_label=None)`: resolve with `pace.label(pace_label,
  data.get('pace') or config default)` before the state write; write `pace` in the same
  `update`; add `pace`, `recommended`, `wish` to the `plan.approved` payload. Without a label:
  `data.get('pace')` else the config default.
- `set_pace(value, root=None)`: validate, write `pace`, event `pace.set` (`pace`,
  `previous`); return `pace <p> (was <previous>)`.

### `cli/wuwei/commands/plan.py`

- `approve --pace` (string). `set`: `assignment` becomes `nargs='?'`; when it is None and
  `item` starts with `pace=`, call `plan.set_pace`; the error text lists `pace=<p>`.

### `cli/wuwei/guards/protect_state.py`

- Beside `_seat_docs_set`, `_planner_pace_set(action)`: the literal `plan set pace=<word>`
  with nothing after it and no shell metacharacter. In `check_bash`, the `plan set` owner
  reason is skipped for it only when `edits[1]` (the caller is today's registered planner
  session, `_gate_edits`) and the posture is not strict; a seat or strict keeps today's
  reason and levelling. No new refusal: the seat case is the reason that exists today.

### `cli/wuwei/commands/pace.py` (new), `cli/wuwei/commands/__init__.py`

- `wuwei pace`: reads state, config, `calibrate.host`, and the open candidates in
  `proposal.json` (those not merged today); prints `Pace: <p> (advice <a>; your default
  <w>)`, `Advice:` line 1, `Inputs:` host, wish, budget, `Balance: binding <input>[;
  unlock]`. Exit 0; exit 2 with `wuwei pace: <reason>` on OSError, ValueError, KeyError.
  Register; add `'pace'` to `READ_ONLY`.

### `cli/wuwei/commands/next.py`

- `THEN['gate']`: "On any Approve option run its record command with `<label>` replaced by
  the chosen label; on Change something ..." (the rest unchanged).

### `cli/wuwei/commands/status.py`

- `snapshot`: `result['pace'] = data.get('pace')`.
- `_groups`: attention gains `pace <p>` when the pace is set and not steady, and `held by
  load` when `cap_bound == 'load'`, after the posture token.

### `cli/wuwei/metrics.py`

- `cycles` (#567): each row gains `pace`, the `pace` of the day state in which the item's
  merge was seen (`steady` when absent).
- `by_pace(root)`: `{pace: {'days', 'merged', 'cycle_by_tier', 'escaped', 'cards'}}` from
  `cycles`, `_escaped` and each day's `pace` and `decision_routes`; `UNMEASURED` when no day
  has a pace.
- `collect`: `event_metrics['by_pace'] = by_pace(root)`.

### `cli/wuwei/report.py`, `cli/wuwei/retro.py`

- `report.pace_lines(root, data)`: `Pace: <p> (recommended <r>, binding <b>)` from the
  `plan.approved` event and later `pace.set` events, then one line per pace: `- <p>: <days>
  days, <merged> merged, light median <m>, standard median <m>, <e> escaped, <c> cards`, and
  `- <p> costs escaped defects: <e> of <merged>` for a pace with more escaped per merged than
  another. `build` adds `## Pace` after `## Cycle time`.
- `retro`: the same lines and `Pace proposal: <D-n>` when the latest `pace_card` is open.

### Docs and design

- Design 5.2: a "Pace (owner, 2026-10-08, #579)" paragraph with the three-column table of the
  issue (tier floor, fix rounds, checks, seats, cards), the floors that never move, and the
  advice inputs. 5.6: the per-pace metrics line. 9.2: rows I15 to I17 (next free ids on the
  base).
- `docs/site/concepts.md` (Pace), `daily.md` (the gate card lines and `plan set pace=`),
  `configuration.md` (`[pace] default`, `repos.tests`), `reference.md` (`wuwei pace`, `plan
  approve --pace`, `plan set pace=`).

### `tests/test_invariants.py` (structure on `main`: `INVARIANTS`, `READS`, cached rules)

- `pace_rule()` (`functools.cache`, like `budget_rule`), used by `i15`, `READS['I15'] = ()`:
  walks `pace.adjust` over every pace x tier x guard x flagged x measured and fails when a
  tier drops below its input, when depth is light outside (fast, standard, no guard, not
  flagged, measured) or a light tier, or when `pace.seats` returns a cap above the host's.
- `i16`, `READS['I16'] = (0,)` (posture): `cruise.level(config, name, run)` for every name in
  `cruise.CLASSES` and `decision.route(fields)` on a Routine and a Consequential fixture are
  equal with day state `pace` set to each value (cached once, posture-independent); and
  `plan set pace=fast` through `protect_state` passes from the planner below strict and
  never from a seat (memoised per posture, like `rules.record` for I8).
- `i17`, `READS['I17'] = ()`: `merge.green` with a pending required check raises
  `required check ... is not green` with day state `pace` set to each value (the merge
  policy does not read the pace; I3 keeps the gated head).
- `INVARIANTS` and `READS` gain the three ids; `test_table_matches_the_checks` keeps the
  table and the dict in step; the walk stays under its 1.0 s CPU budget because every new
  rule is cached.

## What must not change

- Steady: every tier record, launch set, check list, evidence rule and card is today's.
- The repository floor, gate roles, second opinion, merge policy (`merge.green`, gated head),
  grants, records floor, strict refusals and decision routing at every pace.
- The agent-launch guard (`guards/agent_launch.py`) does not read the pace; no new refusal
  anywhere under observe or guarded.
- One gate card (#530): pace is option rows on the existing card, not a second card.
- #567's depth table and `CYCLE_TARGETS`.

## Existing tests at risk

- `tests/test_plan.py:366` asserts the gate labels `['Approve', 'Change something']`; it
  becomes the four labels.
- `tests/test_parallel_dispatch.py:159` reads `options['Approve']`; the label stays.
- `tests/test_docs.py:1224-1235` reads the gate THEN text and the daily page.
- Tests that compare a `calibrate.host` dict exactly gain `load`, `per_seat_tokens`,
  `used_tokens` (monkeypatch `os.getloadavg` where an exact value matters).
- `tests/test_fast_checks.py` and `tests/test_build.py` records gain `seconds`.

## Changes made at build time

- `dispatch.tier` adds `depth` to the record only when it differs from the tier (fast on a
  plain standard item), so every steady and careful record stays byte-identical in shape;
  `dispatch.depth` reads `gates.depth`, then `gates.tier`.
- `calibrate.host` keeps its `text` unchanged (exact-text tests and the gate card read it);
  it gains `load`, and `per_seat_tokens` and `used_tokens` only when a budget is set.
  `pace.host_line` names the load.
- The builder brief's `Checks:` line appears only at careful and at fast with `repos.tests`
  set; a steady brief is unchanged.
- `build check` stores the pace's commands on the build record before it runs them, so the
  completeness check compares against what ran.
- Decision titles cannot carry a quote, so the default-pace card titles read
  `pace.default = fast`. `setup.assignment` reads a bare word as that string for a string
  key with fixed choices; the record command passes the TOML string
  (`config set pace.default '"fast"' --from-card D-n`). The card also carries a Keep option,
  which the decision lint requires.
- The report's `Pace:` line reads the recommendation and the binding input from today's
  `proposal.json`; `unmeasured` without one.
- `pace.set` and `pace.carded` are reserved event kinds and classified silent.
- The README's "Landing next" line drops #579, which this change lands; the lead charter
  documents the candidate `paths`.
