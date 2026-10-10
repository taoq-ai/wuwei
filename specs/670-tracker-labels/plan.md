# Implementation Plan: setup creates the tracker labels the lifecycle uses, and pr raise says which label is missing instead of failing the move

**Branch**: `670-tracker-labels` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

One new tracker port operation, `labels(create)`, answers which lifecycle labels the
configured port needs and lacks, and creates them on request. Only the GitHub adapter without
a board needs one (`tracker.states.in_review`); the others answer "none" without a request.
Three CLI callers use it through one helper in `cli/wuwei/tracker.py`: `setup` and
`init --upgrade` create (owner commands), `doctor` reads, and the shared transition path
`dispatch.tracker_call` reads or creates after a failed in-review move, by one posture and
ownership rule, then retries the move once or names the label and the commands. `pr raise`
prints the move's reason instead of dropping it, and `tracker move` re-runs a move. Root
cause with file and line: `spec.md`, Root cause.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests are in-process: the urlopen replay in
`tests/test_tracker_adapters.py`, the `Fake` tracker in `tests/fakes/tracker.py`, the `ws`
fixture in `tests/test_doctor.py`, the `root` fixture in `tests/test_dispatch.py`, the
`case` fixture in `tests/test_shepherd.py`, `tmp_path` workspaces in `tests/test_workspace.py`.

## Constitution Check

- I stdlib: nothing new imported; the adapter uses its existing `_query`.
- II exits: `labels` is exit 0 with data, 2 could not run (the `@operation` wrapper); a label
  still missing at the move is exit 1 with the fix; any other move failure keeps its exit.
  Doctor: `ok`, `warn` (missing), `unmeasured` (could not read).
- III one behaviour one function: `tracker.labels` is the one call of the port operation;
  `tracker.creates_labels` is the one posture and ownership decision; `tracker.relabel` is
  the one retry, reached by every in-review move through `dispatch.tracker_call`.
- IV test first: each implementation task follows its failing test.
- V ponytail: one port operation (not a list op plus a create op), no new config key, no new
  event kind or state key, no new module. The label rule runs only for `in_review` and only
  after a failure, so a working move costs no extra request.
- VII security: the automatic path creates only on the owner's own tracker below `strict`
  (#530: below strict a missing label is not a wall); under `strict` or on an external
  tracker it prints the owner's commands. The label name is config, not free text, so
  `labels` is not an outward operation. No credential handling changes.
- Workflow: a new decision rule adds I49 to design 9.2 and `tests/test_invariants.py`.

## Design

### cli/wuwei/registry.py

- `PARAMETERS['tracker']` gains `'labels': ('create',)`.

### adapters/tracker/github.py

- `labels(create, *, root=None)`, decorated `@operation('github.labels')` (not
  `outward_operation`):
  - `tracker = settings(root)['tracker']`; with `tracker['board']` return
    `{'created': [], 'missing': []}` (no request).
  - `repo = _repo(root)`; `name = tracker['states']['in_review']`; one query
    `query($owner:String!,$name:String!,$label:String!){repository(owner:$owner,name:$name){id label(name:$label){id}}}`.
    Note the variable for the repository name is `$name`; use `$label` for the label.
  - label present: `{'created': [], 'missing': []}`; absent and not `create`:
    `{'created': [], 'missing': [name]}`.
  - absent and `create`: mutation
    `mutation($repositoryId:ID!,$name:String!,$color:String!){createLabel(input:{repositoryId:$repositoryId,name:$name,color:$color}){label{id}}}`
    with a fixed `color` (`'fbca04'`); a `Failure` from it is re-raised as
    `Failure(f'could not create the label "{name}" in {repo}: {exc}')`; return
    `{'created': [name], 'missing': []}`.
- Update the module docstring: "without a board, in review is a label (created by setup,
  init --upgrade, or on a failed move, #670)".
- Do not change `transition`: its `Failure` at line 156 stays the signal.

### adapters/tracker/linear.py, adapters/tracker/jira.py

- `labels(create, *, root=None)` under `@operation('linear.labels')` /
  `@operation('jira.labels')`, returning `{'created': [], 'missing': []}` with a one-line
  docstring: workflow states, not labels.

### adapters/tracker/none.py

- `labels(create, *, root=None)`: `return registry.record_none('tracker', 'labels', root,
  measurement=False)`.

### cli/wuwei/tracker.py (the shared helpers)

- `creates_labels(config)`: `workspace.posture(config)[0] != 'strict' and not
  outward._external_tracker(config)` (lazy `from wuwei import outward`; reuse the private
  helper, do not copy it).
- `labels(root, config, create, port=None)`: `Result(0, {'created': [], 'missing': []})` for
  `adapters.tracker = "none"`; else `(port or registry.load('tracker', config)).labels(create,
  root=root)`. A non-`Result`, an exit outside 0..2, or exit 0 whose data is not a dict with
  list `created` and `missing` is `Result(2, reason=f'tracker labels: {ADAPTER_DATA}')`;
  `(OSError, ValueError, KeyError, TypeError, AttributeError)` is `Result(2, reason=f'tracker
  labels unmeasured: {exc}')`.
- `ensure_labels(root, prefix)`: `labels(root, workspace.load_config(root), True)`; returns the
  lines to print: `f'{prefix} tracker label "{name}"'` per created name, or on exit != 0
  `[f'tracker labels not created: {reason}; run bin/wuwei doctor']`. Used by setup and init.
- `relabel(port, root, config, item, ticket, failed)`: the failed in-review move.
  `name = config['tracker']['states']['in_review']`; `found = labels(root, config,
  creates_labels(config), port)`; `found.exit` -> `failed`; `found.data['created']` ->
  `port.transition(ticket, name, root=root)`; `found.data['missing']` ->
  `registry.Result(1, reason=f'{item} not moved to {name}: the tracker label {quoted} is
  missing; the owner runs bin/wuwei init --upgrade in a host terminal, which creates it, then
  bin/wuwei tracker move {item} in_review')` where `quoted` is the names in double quotes,
  comma separated; otherwise `failed`.

### cli/wuwei/dispatch.py (`tracker_call`, line 235)

- In the `in_review`/`done` branch: after `result = tracker.transition(...)`, add
  `if action == 'in_review' and result.exit: result = relabel(tracker, root, config, item,
  ticket, result)` (lazy import beside the existing `from wuwei.tracker import ticket as
  recorded`). It sits before the existing `isinstance(result, registry.Result)` check, so the
  retried result is validated the same way; the `tracker.call` event records the final
  result. `claim` and `done` are unchanged.
- Update the error text of the unknown action to stay accurate (unchanged list: claim,
  in_review, done).

### cli/wuwei/shepherd.py (`raise_pr`, line 363)

- `moved = dispatch.tracker_call(item, 'in_review', root)`; `if
  config['adapters']['tracker'] != 'none' and moved.exit: print(f'tracker: {moved.reason}',
  file=sys.stderr)` (module-level `import sys`; the function at line 385 imports it locally
  today, leave that). The `adapters.tracker` check comes first, so the existing stubs that
  return `None` (`tests/test_shepherd.py:272,312`, `tests/test_undo.py:368`) keep working on
  their `none` tracker; if one of them configures a tracker, make that stub return
  `Result(0)`.
- The exit of `pr raise` is unchanged.

### cli/wuwei/commands/tracker.py and cli/wuwei/commands/__init__.py

- `move = actions.add_parser('move', help="Move the item's ticket to a lifecycle state")`,
  `move.add_argument('item')`, `move.add_argument('state', choices=('in_review', 'done'))`.
- `run`: `done` and `move` share one branch: `action = 'done' if args.action == 'done' else
  args.state`; `result = dispatch.tracker_call(args.item, action, root)` (what `tracker.done`
  already calls; `tracker.done` had no other caller, so it is removed); `reason = f'{args.item}: ticket
  {action}'` on exit 0, so `tracker done` prints exactly what it prints today.
- `commands.WRITES` gains `'tracker move'` (`tests/test_cli_known_command.py` pins the sets).

### cli/wuwei/commands/init.py (`upgrade`)

- Before the `No workspace changes needed` check (line ~452):
  `labelled = [] if args.dry_run else tracker.ensure_labels(destination.parent, prefix)`
  (lazy import), print each line, and add `and not labelled` to the no-changes condition.
  The config write above has already run, so the labels follow the upgraded config. The dry
  run never contacts the tracker (doctor's template row runs it).

### cli/wuwei/commands/setup.py (`_setup`)

- After `final = load_config(root)` and before `doctor.diagnose()`:
  `for line in tracker.ensure_labels(root, 'Created'): print(line)` (lazy import).

### cli/wuwei/commands/doctor.py

- `_tracker_labels(root, config)` beside `_tracker`: `tracker.labels(root, config, False)`;
  exit != 0 -> `_row('day', 'tracker labels', 'unmeasured', reason, 'fix the tracker row,
  then run wuwei doctor')`; missing -> `_row('day', 'tracker labels', 'warn',
  'missing: "In Review"', 'wuwei init --upgrade')` (names quoted, comma separated); else
  `_row('day', 'tracker labels', 'ok', 'none missing')`.
- `diagnose`: after `_tracker(root, config)`, append `_tracker_labels(root, config)` only when
  `config['adapters']['tracker'] != 'none'` (`test_day_rows` pins the default day rows).
- No `apply`: `init-upgrade`'s preview is the dry run, which does not show labels.

### tests/fakes/tracker.py

- `Fake.labels(self, create, root=None)`: `self._call('labels', (create,), root)`; `ported`
  passes `labels=fake.labels`. An unconfigured `labels` returns the Recorder's exit 2, which
  keeps every existing failed-move test on its original result.

### Docs

- `docs/specs/2026-09-24-wuwei-design.md`: the port table (line 1861) lists `labels(create)`;
  5.11 Setup and health gains one sentence (setup and `init --upgrade` create the labels the
  port needs; `doctor` lists missing ones; a failed in-review move creates it on the owner's
  tracker below strict, otherwise names it and `bin/wuwei tracker move <item> in_review`);
  9.2 gains row I49.
- `docs/site/adapters.md`, the GitHub tracker paragraph: the same, in two sentences.

## What must not change

- `transition`, `claim`, `create`, `comment`, `backlog`, `history`, `created` of every
  adapter; the outward policy and `_external_tracker`.
- `tracker done`'s output and exit; the merge path's `done` call.
- `pr raise` exit codes and stdout.
- `init --upgrade --dry-run` output and the doctor template row.
- The day rows of a workspace with `adapters.tracker = "none"`.

## Risks

- `createLabel` must be accepted by the token or gh login the adapter uses; a refusal is the
  port's exit 2 naming the label, and setup/init/doctor show it.
- I49 is the id reserved for this item in the wave.
