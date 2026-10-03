# Implementation Plan: close offers carry or park for each open item and records the decision itself

**Branch**: `363-close-carry` | **Spec**: `specs/363-close-carry/spec.md`

## Summary

One new producer and three edits at the shared spots:

1. `plan.dispose` in `cli/wuwei/plan.py`, exposed as `plan carry <item>` and `plan park
   <item>`: builds a two-way, `own branch`, `Decided-by: seat` record, writes it with
   `decision.write` and records `decision.seat_outcome` in one locked state write. It is the
   pattern of `commands/build.py` `_park`, which already passes the close check
   (`tests/test_stop.py::test_build_park_counts_at_close`).
2. `closing.unresolved` builds the open-item line as the coaching question. `close` and the
   Stop hook both print it from there, so they match with no change to `guards/stop.py`.
3. `commands/close.py` checks `closing.unresolved` before it launches the steward, and gains
   a read-only `--widget` that prints each open item through `decision.widget`.
4. `closing.retro` names `/wuwei:wuwei-retro`; `commands/next.py` skips disposed items.

Then the skill and doc text.

## Technical Context

Python 3.11+, stdlib only (`json`, `sys`). Tests: pytest, in process, reusing the `case`
fixture, `approved`, `payload` and `module` helpers of `tests/test_stop.py` (fake code host,
VCS and runtime, `WUWEI_WORKSPACE`, `WUWEI_NOW`), the `root`/`approved`/`row` helpers of
`tests/test_next.py`, and `ROOT`/`SITE` in `tests/test_docs.py`. No subprocess, no network.

## Constitution Check

- I stdlib only: yes.
- II exits: `plan carry|park` exits 0 recorded, 1 unknown item (`state.StateError`), 2 on
  unreadable state (existing `commands/plan.py` mapping). `close` keeps 0/1/2;
  unmeasured item obligations exit 2 and launch no steward; `close --widget` exits 2 with
  the reason on stderr when unmeasured.
- III one behaviour, one function: the open-item question is built once in
  `closing.unresolved`; the record is built once in `plan.dispose`; widgets use the shared
  `decision.widget` and `decision.gate`.
- IV test first: every task pair in `tasks.md`.
- V ponytail: no new module, no new state key, no new event kind, no new decision field.
  `guards/stop.py` is untouched (named in the issue scope, but its text already comes from
  `closing.check`). No widget for PR dispositions, no change to the import of yesterday.
- VII security: `decision_outcomes` stays producer-only (written in a CLI state write with
  `reserved=False`, as `decision route` and `build` do); `decision.decided` stays a reserved
  event kind (`commands/event.py`). A seat gains nothing it could not do with a record plus
  `decision route`. The reason is collapsed to one line, so it cannot add record fields.

## Design

### 1. `cli/wuwei/plan.py`: `dispose`

Add after `add`:

```python
def dispose(item, outcome, reason=None, root=None):
    """plan carry|park: write and route a two-way record that carries or parks one item at
    day close; return its D-n. Park pauses an active item, carry changes no phase."""
```

- `root = workspace.find_workspace(root)`; `verb = {'carried': 'carry', 'parked': 'park'}[outcome]`.
- `data = state.read_state(root)`; when `item not in data['items']` raise
  `state.StateError(f"no item {item} today; today's items: {', '.join(sorted(data['items'])) or 'none'}")`.
- `reason = ' '.join((reason or '').split())` (one line, so no reason text can start a
  field line).
- Record text, same shape as `build._park`; `<status>/<phase>` from `data['items'][item]`:

```
Question: <Verb> <item> at day close?
Context: <item> is <status>/<phase> at day close.[ Reason: <reason>]
Options:
| Option | Description |
| --- | --- |
| <verb> | carry: Carry it to tomorrow's plan / park: Park it until someone resumes it |
| keep | Do nothing: keep it open and keep working today |
Musts:
| Criterion | <verb> | keep |
| --- | --- | --- |
| Reversible | pass | pass |
Wants:
| Criterion | Weight | <verb> | keep |
| --- | --- | --- | --- |
| Day can close | 10 | 10 | 0 |
Recommendation: <verb>
Confidence: high
Reversibility: two-way
Blast radius: own branch
Pre-mortem: The item needed attention today and waits a day.
Revisit: At tomorrow's morning gate.
Decided-by: seat
Outcome: <outcome> <item>
```

- One state write, `kind='decision.decided'`, `payload = {'item': item}`; the update
  (runs under the state lock, like `_park`):
  1. re-check `item in data['items']` (raise the same `StateError`);
  2. `path = decision.write(text, root)`;
  3. `record = decision.seat_outcome(*decision.evaluate(text))`;
     `data.setdefault('decision_outcomes', {})[path.stem] = record`;
  4. when `outcome == 'parked'` and the phase is not in `('parked', 'escalated', 'merged')`:
     `data['items'][item].update(phase='parked', status='blocked')` (the
     `decision.waits` pattern; `state._validate` checks the transition and sets
     `resume_phase`);
  5. `payload.update(id=path.stem, **record)` (the same dict reaches the event, which
     `_write_state` appends after the update).
- Return `payload['id']`.

Item ids are the safe ids `plan._proposal` validates, so they go into the table unquoted.

### 2. `cli/wuwei/commands/plan.py`

In `register`, after `add`:

```python
for verb, text in (('carry', 'Carry an open item to tomorrow and record the decision'),
                   ('park', 'Park an open item and record the decision')):
    command = actions.add_parser(verb, help=text)
    command.add_argument('item')
    command.add_argument('--reason', help='why, written into the record')
```

In `run`: `elif args.action in ('carry', 'park'):` call
`plan.dispose(args.item, {'carry': 'carried', 'park': 'parked'}[args.action], args.reason)`
and `print(f'{identifier}: {outcome} {args.item}')`. Existing `except` mapping gives 1 for
`StateError`, 2 for the rest.

### 3. `cli/wuwei/closing.py`

- `retro`, line 64: `f'OWED: retro/{day}.md does not exist; run /wuwei:wuwei-retro to write it'`.
- `unresolved(root, rows, open_items=None)`: replace the line at 202-203 with

```python
findings.append(f'{name} is still open ({item["status"]}/{item["phase"]}): carry it to '
                'tomorrow (recommended), park it, or keep working? '
                f'Carry: bin/wuwei plan carry {name}. '
                f'Park: bin/wuwei plan park {name} --reason "<why>". '
                'Keep working: finish it, then run bin/wuwei close again.')
if open_items is not None:
    open_items.append(name)
```

  The condition above it is unchanged. `check` and `guards/stop.py` are unchanged.

### 4. `cli/wuwei/commands/close.py`

```python
def register(subparsers):
    ... existing ...
    parser.add_argument('--widget', action='store_true',
                        help='Print each open item as an AskUserQuestion widget; writes nothing')


def widget(root, name, item):
    return decision.widget(
        decision.gate(root) + f'{name} is still open ({item["status"]}/{item["phase"]}): '
        'carry it to tomorrow, park it, or keep working?', 'Open item',
        [('carry', f"Recommended. Carry {name} to tomorrow; tomorrow's plan brings it back."),
         ('park', f'Park {name}; it waits until someone resumes it.'),
         ('Skip', f'Keep working on {name}; run bin/wuwei close again when it is done.')],
        f'bin/wuwei plan <label> {name}')
```

`run`, after the `guard_scope` early return:

- `args.check`: unchanged.
- `getattr(args, 'widget', False)` (a test builds `SimpleNamespace(check=None)`): `names =
  []`; `code, reason = closing.unresolved(root, pr_actions.evaluate(root)[1],
  open_items=names)`; on `code == 2` print the reason to stderr and return 2; else print
  `json.dumps([widget(root, n, items[n]) for n in names], indent=2)` with `items =
  state.read_state(root)['items']`, return `int(bool(names))`.
- default: keep the `state.json` check (raise as today); write `close_requested` (as
  today, now first); `_, rows = pr_actions.evaluate(root)`; `code, reason =
  closing.unresolved(root, rows)`; only when `code == 0`: `steward.run(root,
  trigger='close')` then `code, reason = closing.check(root)`. Mark the second PR read:
  `# ponytail: owned PRs are read again by closing.check; close runs a few times a day.`
- Import `json`, `sys`, `decision`, `pr_actions` (local import of `pr_actions` is fine;
  `closing.check` already imports it locally).

### 5. `cli/wuwei/commands/next.py`

In `step`, before the item loop:

```python
disposed = {record['item_disposition'].split(' ', 1)[1]
            for record in data.get('decision_outcomes', {}).values()
            if isinstance(record, dict) and record.get('decided_by') == 'seat'
            and str(record.get('item_disposition', '')).startswith(('carried ', 'parked '))}
```

and leave disposed names out of `approved` (built at build time: the skip then also keeps a carried item out of the `building` count, so it does not hold a CAP slot). The close row
text becomes `Every approved item is merged, parked, carried or escalated; run the report
skill to retro, report and close the day.`

### 6. `cli/wuwei/state.py`

`STATE_PRODUCERS['decision_outcomes']`: `'wuwei decision route or wuwei build or wuwei plan
carry or park or owner host wuwei doctor --fix'` (keeps the substring
`tests/test_state_allowlist.py` checks).

### 7. Skills and docs

- `skills/wuwei-report/SKILL.md`: the "Owner questions" list adds `wuwei close --widget`.
  New step 1, the others renumbered: "Run `wuwei close`. For each open item it names, ask the
  owner with `wuwei close --widget` (carry is recommended) and run the widget's `record` with
  the chosen label; `Skip` means keep working on it. Without AskUserQuestion, run `wuwei plan
  carry <item>` yourself and say so in the report. Pending owner decisions it names go
  through `wuwei decision show D-n --widget`. Rerun `wuwei close` until it prints
  `steward_launch`, and launch that steward with Agent exactly as returned." Then retro,
  report, and "Run `wuwei close` again until it exits 0. The Stop hook is the final close
  guard."
- `skills/wuwei-retro/SKILL.md` step 1: keep `wuwei close` and `steward_launch`; add "While
  items are open it prints one question per item and launches nothing: answer them as the
  report skill's step 1 says, then run it again."
- `docs/site/concepts.md` "Day close": the first paragraph says the refusal asks, per open
  item, carry (recommended), park or keep working, with the command for each; replace the
  hand-written-record paragraph (lines 92-97) with `bin/wuwei plan carry ITEM` and `bin/wuwei
  plan park ITEM [--reason TEXT]` writing and routing a two-way record and printing its id,
  and the steward launching once item obligations are clear. Keep the build-loop and owner
  decision sentences.
- `docs/site/daily.md` section 6: one sentence: close asks carry, park or keep working for
  each open item and records the answer with `wuwei plan carry` or `wuwei plan park`.
- `docs/site/reference.md`: `plan` row adds "`carry` and `park` record an open item's
  disposition at close"; `close` row adds "`--widget` asks about each open item".

## What must not change

- The close-clean rule in `closing.unresolved` (which dispositions count, merge evidence,
  owner decisions, pushed branches) and every other finding text in `closing.py`.
- `guards/stop.py`, `closing.check`, `pr_actions`, `decision.py`, `steward.py`.
- `close --check retro` behaviour apart from the one retro line.
- The once-per-day close steward rule (`steward.run`).
- `plan approve --import-yesterday`.

## Risks for the builder

- `tests/test_records_after_dryrun4.py::test_one_close_steward_review_per_day` calls `close.run(SimpleNamespace(check=None))` and patches only `closing.check`. With
  the new order `close.run` also calls `pr_actions.evaluate` and `closing.unresolved` on that
  fixture. If either fails there, patch `close.closing.unresolved` to return `(0, '')` in
  that test; do not change the production order.
- `tests/test_next.py::test_end_of_day_rows` may compare the close step text; update it to
  the new text if so.
- The decision lint guard lints every `D-*.md` after a Bash call; the generated record must
  pass `decision.lint` (asserted in T001).
