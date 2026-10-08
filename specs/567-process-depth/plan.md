# Implementation Plan: Process depth follows the tier

**Branch**: `567-process-depth` | **Spec**: `specs/567-process-depth/spec.md` | **Issue**: #567

## Summary

The tier that `dispatch.tier` already computes (#280) becomes the one input for process
depth. A three-line helper `dispatch.depth(row)` reads it; the briefs carry a `Depth:` line
built from it; the launch prompt repeats that line; the verdict lint, the retro check and the
post-fix continue read it from state; a read-only `wuwei sweep classes <worktree>` lists the
classes a diff touches. `decision show` prints one line for a Routine record taken under
mandate. `metrics.collect` derives cycle and gate minutes per item and per tier from events
that exist; the report and retro show them. Charters lose prose and point to the design 5.3
table. No new event kind, no new refusal, no second tier.

## Technical Context

Python 3.11 stdlib, pytest for tests. Touched modules: `dispatch.py`, `brief.py`,
`verdict.py`, `guards/verdict.py`, `guards/pr.py`, `obligations.py`, `commands/sweep.py`,
`commands/__init__.py`, `commands/decision.py`, `state.py` (producer message only),
`metrics.py`, `report.py`, `retro.py`, charters, generated agents, docs. Test command:
`python -m pytest -q` from the repository root.

## Constitution Check

- I stdlib only: yes; no dependency.
- II three-state exits: `sweep classes` exits 0 measured, 2 with the reason; the lint keeps
  its exits; an unresolvable tier falls back to today's full shape, never to clean.
- III one behaviour, one function: depth in `dispatch.depth`, the tier in `dispatch.tier`
  (unchanged), the light shape in `verdict.lint`, the tier lookup for a verdict file in
  `verdict.light`; every caller reuses them.
- IV test first: every task pair below is test then code.
- V ponytail: one helper, one table, one optional lint flag; charters shrink.
- VII security: nothing a seat writes decides the depth; `items.<item>.depth` and
  `gates.tier` are CLI-written state; the trust-boundary floors (records, merge policy) are
  untouched. #530: no new refusal under any posture.

## Changes

### `cli/wuwei/dispatch.py`

- Add after `TIERS`:
  - `GUARD_CODE = ('guards/*', 'grants*', 'outward*', 'hooks/*')`: the issue's mutation paths.
  - `CLASS_PATHS`: an ordered tuple of `(class, globs)` for the ten builder classes, globs
    matched with `merge.matched` (suffix glob, same matcher as `trust_paths`). Starting table
    (the builder may tune globs, not the shape):
    `AUTH: guards/*, *auth*, grants*, *permission*, security*`;
    `VAL: *pars*, *valid*, *schema*, config*, *normal*`;
    `DOC: *.md, docs/*, *.rst`;
    `TEST: tests/*, test_*, *_test.*`;
    `INF: .github/*, workflows/*, hooks/*, bin/*, *.toml, *.yml, *.yaml, Dockerfile*, *.json`;
    `RET: registry*, adapters/*, *retry*`;
    `ERR: exits*, *error*, adapters/*, guards/*`;
    `STATE: state*, *lock*, *journal*, events*`;
    `CON: commands/*, __main__*, *contract*, *schema*, *api*`;
    `BUD: adapters/*, *runtime*, *dispatch*, *timeout*`.
- `depth(row, *, gate=False)`: the recorded `gates.tier`, else (builder readers only)
  `row.get('depth')`, else `'standard'`. Gate readers (gate brief line, `verdict.light`,
  `_recorded_gates`, `_seats`, sentinel retro) pass `gate=True`, so a builder prediction never
  lightens a gate that `dispatch next` has not tiered.
- Extract the diff read inside `tier` (`dispatch.py:56-65`) into `_changes(root, config, row)`
  returning `(repo, changes)`; `tier` calls it inside the same `try` so its record, reasons
  and error handling stay byte-identical.
- `classes(root, config, row)`: `record = tier(...)`; light returns `(record, {})`; full
  returns every class with the changed paths (or `[]`); standard returns only classes with at
  least one matching path. Raises `ValueError` when `_changes` cannot read the diff (the
  command maps it to exit 2); `tier`'s own fallback is not used here, because a sweep must not
  report "no class" on an unread diff.
- `step_zero(depth, paths, trust_paths)`: `None` at light; `(True, '')` at full; at standard the
  first `(path, pattern)` from `merge.matched(path, (*trust_paths, *GUARD_CODE))`, returning
  `(True, '<path> matches <pattern>')` or `(False, 'no guard code or trust path in the diff')`.
- `_delta_feedback(first, light=False)`: light text: `Re-read: the fix round changed
  <head>..HEAD. Re-read the diff for your blocking findings and rewrite only the Verdict: and
  Head: lines of <file>; mark each finding the fix closed blocks: no.` The standard text is
  unchanged. `_seats` passes `depth(data['items'][item], gate=True) == 'light'`.
- Do not change: `tier`'s outputs, `gate_set`, the round keys, `receive`, `next_step`'s state
  machine or budget.

### `cli/wuwei/brief.py`

- `depth_line(role, value, paths, trust_paths, worktree)`: the header text, one line.
  - builder: `Depth: <value>; before handoff run wuwei sweep classes <worktree> and report one
    CLASS line per class it lists` plus, at light, `; skip: the class sweep (it lists none),
    the retro note when every line would be none`.
  - sentinel at light: `Depth: light; skip: gate step zero, the Probe or Mutation row, the
    class-sweep line, the Simplicity and Design rows, the retro note when every line would be
    none; verdict: Verdict:, Head:, findings`.
  - sentinel at standard: `Depth: standard; step zero: run (<reason>)` or `Depth: standard;
    step zero: skip (<reason>); write Mutation: skipped (depth standard)`.
  - sentinel at full: `Depth: full; step zero: run`.
  - other roles: `None` (no line).
- In `write`: for `role == 'builder'` call `dispatch.tier(root, config, {**current, 'worktree':
  str(tree)} if tree else current)['tier']`; for a gate use `dispatch.depth(current, gate=True)`. The
  paths for step zero are `[row['path'] for row in changed]` (status plus diff stat, already
  read); the trust paths are `repo.get('gates', {}).get('trust_paths', [])`. Append the line
  after the `Spec:` line. In the state `update`, for a builder set
  `fresh['items'][item]['depth'] = value` when the item exists.
- `launch_prompt`: read the brief text, find the first `^Depth: .+$` line in the header (before
  the first blank line) and append it to the mandate block; no line, no change.
- Do not change: `mandate()`'s text, the other header lines, the refusals.

### `cli/wuwei/state.py`

- `_producer_error`: add `'depth': 'wuwei brief'`. Nothing else: item fields are already
  producer-owned by default.

### `cli/wuwei/commands/sweep.py` and `commands/__init__.py`

- `sweep classes <worktree>`: resolve the workspace, read state, find the item whose
  `worktree` resolves to the given path (absolute, or relative to the workspace root), call
  `dispatch.classes`, print `Depth: <tier>` (`Depth: light; no class sweep` at light) then
  `<CLASS>: <comma-separated paths>` per class (`<CLASS>: none changed` at full when no path
  matches). Exit 2 with `wuwei sweep classes: <reason>` on no matching item, unreadable state
  or diff.
- Add `'sweep classes'` to `READ_ONLY`.

### `cli/wuwei/verdict.py`

- `lint(text, *, quality=False, class_sweep=False, light=False)`: when `light`, skip the
  probe row check (`:106-107`), the class-sweep check (`:108`), the quality rows (`:130-133`),
  and the retro checks when `missing` holds all three keys. Every other check runs.
- `light(path, data)`: `False` when `data` is `None`; else name = `Path(path).stem` without
  `gate-`, seat = `brief.seats(data).get(name)`, row = `data['items'].get(seat['item'])`;
  return `dispatch.depth(row, gate=True) == 'light'`; a missing seat or item, or any `ValueError`,
  `KeyError`, `TypeError`, returns `False`.
- `lint_file`: when `root` is known, read `state.read_state(root)` (an `OSError` or
  `ValueError` there means `data = None`, today's shape) and pass `light=light(path, data)`.

### `cli/wuwei/guards/pr.py`, `cli/wuwei/obligations.py`

- `_recorded_gates` (`pr.py:113`): the candidate item is known, so pass
  `light=dispatch.depth(items[candidate], gate=True) == 'light'`.
- `obligations._gate_recorded(directory, head, data)`: `_visibility` (`:184`) already holds the
  day state `data`; pass it and lint with `light=verdict.light(path, data)`.
- `gate_check`'s file fallback (`pr.py:177`, no recorded verdicts) stays strict.

### `cli/wuwei/guards/verdict.py`

- `check_retro`: after `retro_fields`, when `missing` holds all three keys and the seat's item
  is light (`gate=True` when the seat role starts `sentinel-`), set
  `fields = dict.fromkeys(RETRO_KEYS, 'none')` and `missing = []`. Resolve the
  seat with `agent_launch.stopping_seat(payload, root)` when the payload has a transcript,
  else by `agent_id` as the seat name; resolve the item from `brief.seats(state)`; any failure
  keeps today's check.

### `cli/wuwei/commands/decision.py`

- `show`: after reading `fields`, when `level != 'full'` and the state outcome for the id has
  `decided_by == 'mandate'` and `cisr == 'Routine'`, return one line:
  `D-n (Routine, mandate): <Question> Took <option>. Full record: wuwei decision show D-n --full`.
  The `--widget` branch is unchanged.

### `cli/wuwei/metrics.py`

- `CYCLE_TARGETS = {'light': 60, 'standard': 180}`.
- `cycles(root)`: walk `watch.days(root)` oldest first; per item record the first
  `plan.approved` (payload `items`) or `plan.added` (payload `item`) time, the first sentinel
  `seat launched` (name found in a `brief written` payload with role `sentinel-*` and the
  item), the last `gate.received`, and the `phase_changes` `merged` time; the tier is
  `dispatch.depth` of the item row in the merged day's state. Return rows
  `{'item', 'tier', 'cycle_minutes', 'gate_minutes', 'merged_at'}` for merged items with a
  start; `gate_minutes` is `UNMEASURED` without a sentinel launch.
- `collect`: add `cycle_minutes`, `gate_minutes` (dicts by item) and `cycle_by_tier`
  (`{tier: {'median_minutes', 'items', 'target'?}}`); all three `UNMEASURED` when no row.
- `cycle_moved(rows, today)`: medians per tier for this ISO week and the previous one; the
  tier with the largest absolute difference among tiers present in both, as a line, else
  `Cycle time: unmeasured (no tier merged in both weeks)`.

### `cli/wuwei/report.py`, `cli/wuwei/retro.py`

- `report.build`: a `## Cycle time` section at every verbosity after `## Merged`: per tier
  `- <tier>: median <m> minutes over <n> items (target <t>)` and per item `- <item> (<tier>):
  <c> minutes, gates <g> minutes`; `unmeasured` when none.
- `retro.compile`: one line after the `## Cycle` table from `metrics.cycle_moved`.

### Charters (then `bin/wuwei agents build`)

- `_common.md` Evidence 2: one sentence first: process depth follows the tier (design 5.3);
  run step zero only when your brief's `Depth:` line says `step zero: run`, otherwise write
  the row it gives. Evidence 5: at light the fix is re-read by the same sentinel (the continue
  feedback says what to rewrite). Evidence 8: at light the verdict is `Verdict:`, `Head:` and
  findings. Decisions 4: at light the retro note only when a line is not `none`. Shorten the
  step zero procedure text where it repeats the brief. Net line count not above today.
- `builder.md` item 11: run `wuwei sweep classes <worktree>` and report one line per class
  it lists (none at light); the class rows shrink to their one-line trigger.
- `sentinel-quality.md` step 1: "Follow gate step zero when your brief's Depth: line says run";
  step 5: rows "except at light". `sentinel-arch.md` 6 and `sentinel-security.md` 5 point to
  the Depth line for the delta and the shape.
- Bump each edited charter's `version` minor. Regenerate `agents/*.md` with `bin/wuwei agents
  build`; grants must not change (if they do, stop and report).

### Docs and design

- `docs/specs/2026-09-24-wuwei-design.md` 5.3: an amendment bullet "Process depth follows the
  tier (owner, 2026-10-08, #567)" with the issue's table, and "(at light, see the depth
  table)" on the Verdict shape and Retro note bullets; 5.6 or the process metrics: cycle and
  gate minutes per tier with the targets.
- `docs/site/concepts.md` Tier: the depth columns; `docs/site/daily.md`: one paragraph;
  `docs/site/reference.md`: `sweep classes`, the one-line `decision show`, the metrics keys.

## What must not change

- `dispatch.tier`'s record and reasons; the gate set per tier; the `delta` round key and the
  budget (one fix round plus one re-read or delta); `receive`'s HEAD, docs and scanner checks.
- Standard and full verdicts lint exactly as today; a verdict whose item cannot be resolved
  lints as today.
- The decision record file, its lint, routing and the widget; the digest and report mandate
  lines.
- The records floor and every refusal under strict (#530).

## Existing tests at risk

- `tests/test_verdict.py` (signature gains a keyword; defaults unchanged).
- `tests/test_brief.py` and `tests/test_brief_adapters.py` (header gains a `Depth:` line for
  builder and gate briefs; tests that compare whole headers need the line).
- `tests/test_dispatch.py` (the extracted `_changes`; the tier record must be identical).
- `tests/test_charters.py`, `tests/test_agents.py` (charter text and regenerated agents).
- `tests/test_cli_known_command.py` (the new command path).
- `tests/test_metrics.py`, `tests/test_report_retro.py` (new keys and sections).
- `tests/test_path_day.py`, `tests/test_parallel_dispatch.py` (fixture days through the new
  lines).
