# Implementation Plan: an item-level owner_merge flag

**Branch**: `678-owner-merge-flag` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One hold at the shared spot: `merge.check` is the function every merge path already calls
(command, grant, `pr act`, PR guard, overnight shepherd), so one `owner_hold` read at its top
covers them all. The rest is the record and its writers: `plan set <item> owner_merge=`, a
reserved item field, a guard shape that lets agent tools set (never clear) the flag, a
`label` code_host operation for the PR record, a body line at raise, one sentence on the gate
card, the I37 invariant and a docs paragraph.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new event kind
(`plan.set` is already reserved to `wuwei plan set` in `cli/wuwei/commands/event.py:76`), no new
config key. One new code_host port operation, `label(ref, name, present)`.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: the hold is a `Refused` (exit 1); a malformed record is `ValueError` (exit 2,
  `DAMAGED`); a label failure after the state write is exit 2 naming the rerun.
- III one behaviour one function: `merge.owner_hold(item)` is the one read, reached by every
  path through `merge.check`; `pr raise` reads it for the body line.
- IV test first: every task pair below is test then implementation.
- V simplicity: no per-path guard, no new event kind, no gate card option (the card is at its
  four-option limit), no daemon merge (the daemon checks only, unchanged).
- VII security: only `wuwei plan set` writes `items.<id>.owner_merge`; agent tools may only
  set it (the restrictive direction); clearing stays the owner's. The PR label is written,
  never read as the flag. The label operation has a closed allowlist: one label name, POST to
  `issues/<n>/labels`, DELETE of `issues/<n>/labels/owner-merge`.
- Workflow: a new decision rule adds row I37 to design 9.2 and its check to
  `tests/test_invariants.py`.

## Design

### cli/wuwei/merge.py

- `LABEL = 'owner-merge'`.
- `owner_hold(item)`: `flag = item.get('owner_merge')`; `None` when absent; `ValueError(f'invalid
  owner_merge record; {DAMAGED}')` unless `flag` is a dict with a bool `value` and str `by` and
  `at`; returns `(flag['by'], flag['at'][:10])` when `value` is true, else `None`.
- `check`: right after `ref = reference(...)`, read the state once (move the existing
  `data = state.read_state(root)` up from line 231 and drop the later read) and, for the item
  whose `pr == ref`, refuse when `owner_hold` returns a hold:
  `raise Refused(f'owner merges: owner_merge set by {by} on {date}; clear it with bin/wuwei
  plan set {name} owner_merge=false')`. Placing it before `merge.auto`, the breaker and the
  quiet-hours rules makes it the reason every path logs. The existing `except Refused` wrappers
  (`merge policy: ...; the owner merges; ask the owner`, and the granted form) stay as they
  are.
- Do not change `execute`, `by_grant`, `poll` or the grant logic: they already route through
  `check`.

### cli/wuwei/plan.py

- `set_owner_merge(item, value, root=None)`, beside `set_spec`:
  - `value` must be `'true'` or `'false'`, else `ValueError` naming
    `bin/wuwei plan set <item> owner_merge=true|false`;
  - `by = os.environ.get('WUWEI_SEAT_ROLE') or ('planner' if sessions.current() else 'owner')`;
  - one `state._write_state(update, root, reserved=False, kind='plan.set', payload={'item',
    'owner_merge': bool, 'by'})`; `update` refuses an unknown item with the `set_spec` message
    and sets `items[item]['owner_merge'] = {'value', 'by', 'at': workspace.now().isoformat()}`,
    capturing the item's `pr`;
  - when the item links a PR and `adapters.code_host != 'none'`: `merge.read(host.label, ref,
    merge.LABEL, on, root=root)` and require `(merge.LABEL in labels) == on`; on `merge.ERRORS`
    raise `OSError(f'{item}: owner_merge {value} recorded; PR label not updated: {exc}; rerun
    bin/wuwei plan set {item} owner_merge={value}')` (exit 2; the state already holds);
  - returns `f'{item}: owner_merge {value}'`.
- `gate_widget`: the `Change something` description gains one sentence: `Name any item you
  merge yourself; the planner records it with wuwei plan set <item> owner_merge=true.`

### cli/wuwei/commands/plan.py

- `run`: `elif key == 'owner_merge': print(plan.set_owner_merge(args.item, value))`.
- The `set` help strings and the unknown-assignment message name `owner_merge=true|false`;
  update the substring asserted in `tests/test_plan.py:554` to the new message.

### cli/wuwei/state.py

- `_producer_error`: add `'owner_merge': 'wuwei plan set'` to the item field map, so
  `state set items.<id>.owner_merge` names its writer (generic writes to item fields other than
  `note` are already refused by `_generic_allowed`).

### cli/wuwei/guards/protect_state.py

- `_seat_owner_merge(action)`, beside `_seat_docs_set`: exactly
  `['plan', 'set', <item>, 'owner_merge=true']`, the item not starting with `-`, no word
  matching `[$`*?\[{]`.
- The owner-action test at line 259 passes it like `docs=`:
  `not (not xargs and (_seat_docs_set(action) or _seat_owner_merge(action)))`.
- The `('plan', 'set')` reason gains one sentence: `A seat or the planner records
  owner_merge=true itself; clearing it (owner_merge=false) is the owner's, in a host terminal.`
  Keep the existing `Spec overrides are an owner action` prefix (asserted by tests).

### adapters/code_host/github.py, adapters/code_host/none.py, cli/wuwei/registry.py, tests/fakes/code_host.py

- `registry.PARAMETERS['code_host']['label'] = ('ref', 'name', 'present')`.
- github `label(ref, name, present)` under `@_operation`: `name` must be `'owner-merge'` and
  `present` a bool, else `ValueError`. Present: `_api(f'repos/{repo}/issues/{number}/labels',
  payload={'labels': [name]})`. Absent: `_run(['api', f'repos/{repo}/issues/{number}/labels/{name}',
  '--method', 'DELETE'])`, treating a `(HTTP 404)` failure as already absent. Returns
  `{'labels': [names]}` from the returned label list.
- `_run` allowlist: the POST regex gains `issues/[1-9][0-9]*/labels`; a new
  `payload is None and options == ['--method', 'DELETE']` branch accepts only
  `issues/[1-9][0-9]*/labels/owner-merge`.
- none: `record_none('code_host', 'label', root, measurement=False)`.
- Fake: `label(self, ref, name, present, root=None)` through `_call`.
- `tests/fixtures/code_host/recordings.json`: one `label` recording (add) so the shared write
  failure table covers it; `tests/test_adapters.py` gains the contract row
  `('code_host', 'label', ('ref', 'name', 'present'), False)`.

### cli/wuwei/shepherd.py (`raise_pr`)

- After the `Review tier` line: `if hold := merge.owner_hold(row): body += f'\n\nOwner merges:
  owner_merge set by {hold[0]} on {hold[1]}'` (before the outward lints, which see the full
  body).
- After `state.record_pr(...)`, when `hold`: `merge.read(host.label, ref, merge.LABEL, True,
  root=root)`; a failure goes through the existing `except ERRORS` (exit 2).

### docs

- `docs/specs/2026-09-24-wuwei-design.md` 9.2: row I37, `An item with owner_merge set is never
  merged by WUWEI: merge check, wuwei merge, pr act, the PR guard and the overnight shepherd
  refuse naming the flag, under any grant; cleared, they follow the normal policy`, checked by
  `merge.owner_hold` in the walk and the path table `test_owner_merge_holds_on_every_path`;
  notes `#678; only wuwei plan set writes it; agent tools set it, the owner clears it`.
- `docs/site/daily.md`, next to the `plan set` paragraphs (around line 344): how to keep a merge
  for yourself, who sets and clears it, the refusal line, the label.

## Must not change

- The order and text of every other `check` rule, `execute`, `by_grant`, grants, `poll`, the
  overnight shepherd's check-only behaviour, and `pr_actions` classification.
- `plan set` for `spec=`, `docs=`, `ticket=`, `pace=`; the `docs=` and `pace=` guard shapes.
- The gate card's option count (four) and its record command.

## Deferred

- `merge.owner_paths` as a rule source (#675) and a card-answered clear (#661).
- Editing the body of an already raised PR.
