# Implementation Plan: The loop's remaining joints

**Branch**: `225-loop-joints` | **Date**: 2026-09-30 | **Spec**: `specs/225-loop-joints/spec.md`

## Summary

Four small fixes, each at the one function every caller already routes through: the
state guard stops reading `wuwei` CLI arguments as write targets, `runtime dispatch`
applies the gate role mapping `brief` already uses, the state writer moves the phase on
raise and on an observed merge, and the decision router is shared so `pr act` routes what
it creates and status lists pending owner decisions. No new modules, state keys, event
kinds or configuration.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest, in process with existing fixtures: `test_protect_state.workspace`
and `payload`; `test_runtime_cli` fakes; `test_shepherd.case`; `test_pr_actions.linked`
(on `test_stop.case`, `own`, `REF`); `test_signal_status.day` and `cli`
**Constraints**: three-state exits, fail closed, no guard loosened beyond FR-001

## Constitution Check

- One behaviour, one function: guard targets stay in `_write_targets`; the gate alias
  stays `dispatch.ROLES`; phase legality stays `state._check_transition`; routing moves
  to one function in `cli/wuwei/decision.py`.
- Reuse: `_wuwei_action`, `dispatch.ROLES`, `state.transition` logic (extracted, not
  copied), `decision.route`, `decision.answered`.
- Test first for every behaviour; tasks.md orders each test before its change.
- No forgeable trust: `decision_routes` and item `phase` are still written only by CLI
  producers (`_write_state` with `reserved=False` inside the CLI); nothing seat-writable
  is trusted.

## Changes by file

### `cli/wuwei/guards/protect_state.py` (joint 1)

- `_write_targets(argv, cwd, root)`: after the `cd|pushd|popd` early return, add
  `if _wuwei_action(argv) is not None: return []` with a one-line comment: the CLI is the
  only state writer; its arguments (job JSON, prompts, paths it reads) are data. Redirects
  stay checked because `check_bash` builds `targets = [*command.writes, *_write_targets(...)]`
  (line 444).

Must not change: `_owner_action`, `_owner_relevant`, `_STATE_MENTION`, the interpreter
opacity check in `check_bash` (lines 425 to 428), the parse-error branch, and every
target rule for other programs (`cp`, `mv`, `rsync`, `rm`, `tee`, `dd`, `sed -i`,
readers, the generic fallback at line 344).

### `cli/wuwei/commands/runtime.py` (joint 2)

- In `run`, dispatch branch: compute
  `role = 'sentinel-' + args.role if args.role in dispatch.ROLES else args.role`
  (import `dispatch` from `wuwei`, as `commands/brief.py` does) and pass `role` to both
  `registry.runtime_config` and `adapter.dispatch`.

Must not change: `status`, `result`, `continue` (they take the job, whose `agent_type`
already carries `wuwei:sentinel-<role>`), the runtime override and output shape.

### `cli/wuwei/security.py` (joint 2)

- `agent_path(root, role)`: compute the plugin charter path first
  (`Path(__file__).resolve().parents[2] / 'charters' / (role + '.md')`). In a secured
  workspace raise `ValueError('workspace instructions unavailable; run wuwei agents build')`
  only when the generated file is missing and that charter exists (a known role);
  otherwise return the generated path, whose absence the adapters already report as
  exit 1 "unknown role, brief or worktree" (`adapters/runtime/claude.py` line 22,
  `adapters/runtime/codex.py` line 44). Unsecured path unchanged.

Must not change: callers (`commands/build.py`, both runtime adapters) and the secured
path for known roles.

### `cli/wuwei/state.py` (joint 3)

- Extract the body of `transition`'s `update` into `_move(data, item, phase)`:
  `_check_transition`, the `delta -> raised` `fix_rounds` reset, set the phase.
  `transition` calls it (behaviour identical, `KeyError` for an unknown item stays in
  `transition`).
- `record_pr`: inside `update`, when `raised` and
  `data['items'][item]['phase'] in ('gate', 'delta')`, call `_move(data, item, 'raised')`.
  `_write_state` already adds `phase_changes` to the `pr.raised` event.

Must not change: `PHASES`, `_validate`, the claim path (`raised=False`), the event kinds.

### `cli/wuwei/pr_actions.py` (joint 3 and joint 4)

- `observe`, inside `update(data)`: when `current == 'merged'`, for each
  `name, item in data['items'].items()` with `item.get('pr') == ref` and
  `item['phase'] == 'raised'`, call `state._move(data, name, 'merged')`. The existing
  `pr.action` write carries the `phase_changes`.
- `_thread`, scope branch: bind the record text to a local, `path = decision.write(text,
  root)`, then `decision.route_owner(path.stem, decision.evaluate(text)[0], root)` before
  the existing `pr.action.decision` write. The decision text itself is unchanged
  (`Reversibility: unsure` routes to the owner).

Must not change: `classify`, action deadlines and tiers, dispositions, the pending and
answered branches of `_thread`, `act`.

### `cli/wuwei/decision.py` and `cli/wuwei/commands/decision.py` (joint 4)

- Move the owner branch of `commands/decision.decide` (the `mark` callback, the
  `decision_routes` presence check and the `decision.routed` write, lines 39 to 48) into
  `decision.route_owner(identifier, fields, root)` in `cli/wuwei/decision.py`
  (idempotent: no write when already routed). `decide` calls it and still returns
  `(0, 'owner')`.

Must not change: `owner_outcome` (it keeps refusing unrouted decisions), seat routing,
the `decision.routed` payload shape (`id`, `reversibility`), metrics counting of
`decision.routed`.

### `cli/wuwei/commands/status.py` (joint 4)

- `scan`: after the escalated-items loop, read
  `routes = classified_state.get('decision_routes', {})`; raise
  `ValueError('invalid decision ledger')` when it is not a dict (status and nudges already
  map `ValueError` to exit 2, unmeasured). For each identifier with
  `decision.answered(classified_state, identifier) is None`, add
  `current[('decision.pending', identifier)] = {'tier': 'nudge', 'source':
  'decision.pending', 'lane': 'Decisions', 'reason': f'{identifier} pending owner decision'}`.
  `nudges` and `status --line` both read `scan`, so both show it.

Must not change: event scanning, `signal.SILENT`, `signal.classify`, watch health.

### `tests/test_e2e_day.py` (existing test updated)

- Remove `day.transition('raised')` after the successful `day.raise_pr()` and
  `day.transition('merged')` after the merged `pr state`; assert
  `day.data['items']['A']['phase']` is `raised` then `merged` at those points.
- Replace the `transitions` assertion with phase moves read from `phase_changes`
  (`[row['payload']['phase_changes']['A'] for row in events if 'A' in
  row['payload'].get('phase_changes', {})]`), expecting
  `['implement', 'gate', 'fix', 'delta', 'raised', 'merged']`.

### `docs/site/reference.md`

- "Automatic phases" row: add "`wuwei pr raise` moves `gate` or `delta` to `raised`; an
  observed merge (`pr state`, `pr act`, the watch) moves `raised` to `merged`."
- "Charter names" row: add "`runtime dispatch` accepts `arch`, `quality` and `security`
  for the sentinel roles, as `brief` does."
- Decision paragraph (line 36): add "`pr act` routes the decisions it creates."

## Reproduction for the builder

Before any change, confirm each root cause with a failing test (tasks.md). The dry-run
evidence is summarised in spec.md; do not reference the dry-run paths from the repository.

## Out of scope

- `echo` or other readers quoting protected paths; `python -m wuwei` without `-P`.
- Automatic phase moves other than `gate|delta -> raised` on raise and `raised -> merged`
  on observation.
- Changing `STATE_PRODUCERS` hints, the dashboard's decision list, or `owner_outcome`.
