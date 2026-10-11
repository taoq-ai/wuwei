# Implementation Plan: an optional polish round after a pass

**Branch**: `723-polish-round` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

A polish round is a fix round whose feedback is the notes and whose delta one gate runs.
Everything that runs a fix round already exists: `build.open_fix` opens it (and counts it
against the #623 cap), the build loop moves `fix` to `delta`, `_seats` continues the
stopped gate seat, `receive --round delta` records it and the delta tail of `next_step`
raises or opens the next round. Three things are missing: a decision at the round-one pass
(offer, open or raise), a record of which gate re-checks (`items.<item>.polish`), and one
predicate that lets that gate run a delta although its round-one verdict was PASS. The
guards that judge "gates passed at HEAD" read a gate's delta record whenever it exists.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, no new port, no new phase. One
config key (`gates.polish`), one item key (`items.<item>.polish`), one event kind
(`polish.skipped`), two `dispatch` subcommands.

## Constitution Check

- I stdlib: nothing new imported.
- II exits: `dispatch polish` and `dispatch skip-polish` follow `commands/dispatch.py`:
  `Refused` exit 1, `ValueError`/`OSError` exit 2, success 0. A `polish` action is exit 0.
- III one behaviour one function: the offer rule lives in `dispatch.polish_offer`, the
  "due a delta" rule in `dispatch.rechecks`, the round opens only in `build.open_fix`.
- IV test first: tasks.md orders each test before its code.
- V simplicity: no polish phase, no second budget, no new seat kind; polish reuses the fix
  round end to end.
- VII security: `items.<item>.polish` is producer-owned by the state writer's default
  (`state._protected` keeps every item key but `note`), so a seat cannot name itself the
  re-check gate through `wuwei state set`; `polish.skipped` is reserved in the event
  command. A gate's delta record for a PASS gate can only exist when `receive` accepted it
  through `rechecks`, so the widened PR-guard and merge reads trust nothing new. A
  trust-boundary security finding still always blocks, so it never becomes a polish note.
- Workflow: a new decision rule, so 9.2 row I58 and its `tests/test_invariants.py` check.
  Design 5.3 is not contradicted (the polish round is a round under the cap); no other
  design text changes.

## Design

### cli/wuwei/workspace.py

`SCHEMA['gates']` (line 139) gains, after `tier_max_rounds`:

```python
"polish": (str, "offer", ("never", "offer", "always")),  # #723: one notes-only round after a pass
```

### cli/wuwei/dispatch.py

New helpers beside `rotate` (line 188):

```python
def polish_offer(config, row, roles, results, used):
    """#723: the polish round a round-one pass offers, {'gate', 'notes'}, or None (off, no
    notes, already recorded, or at the round cap). The gate is the one that wrote every
    note, else quality."""
    notes = [note for result in results for note in result['notes']]
    if (config['gates']['polish'] == 'never' or not notes or row.get('polish')
            or used >= max_rounds(config, row)):
        return None
    authors = [role for role, result in zip(roles, results) if result['notes']]
    return {'gate': authors[0] if len(authors) == 1 else 'quality', 'notes': notes}


def rechecks(data, item, role):
    """#723: role runs the item's delta: its initial verdict was FIX, or it is the gate of the
    item's open polish round (before the PR). One rule for next_step, delta_due, receive and
    opinion."""
    row = data['items'][item]
    first = _record(data, item, role, 'initial')
    polish = row.get('polish') or {}
    return bool(first) and (first['verdict'] == 'FIX' or (
        polish.get('status') == 'opened' and polish.get('gate') == role and not row.get('pr')))
```

`next_step`:

- Fix phase (lines 349-350) and delta phase (lines 358-359): `roles = [role for role in
  gates if rechecks(data, item, role)]`. The "requires all initial verdicts" refusals above
  them stay.
- Gate phase, no failures (lines 377-379) becomes:

```python
        if not failures:
            offer = polish_offer(config, row, roles, results, rounds_used(data, item))
            if offer is None:
                return {'action': 'raise', 'notes': [note for result in results for note in result['notes']]}
            if config['gates']['polish'] == 'always':
                return _open_polish(root, item, offer)
            return {'action': 'polish', **offer, 'command': 'wuwei dispatch polish ' + shlex.quote(item),
                    'skip': 'wuwei dispatch skip-polish ' + shlex.quote(item)}
```

New functions after `_fix` (line 614):

```python
def _open_polish(root, item, offer):
    from wuwei.commands import build
    build.open_fix(item, _polish_feedback(offer['notes']), root=root,
                   polish={'status': 'opened', 'gate': offer['gate'], 'notes': offer['notes']})
    return _fix(item, [offer['gate']])


def _offered(root, item):
    """#723: the open polish offer, refused unless gates.polish is offer and one is open."""
    mode = workspace.load_config(root)['gates']['polish']
    if mode != 'offer':
        raise Refused(f'gates.polish is {mode}; dispatch next decides the polish round itself')
    offer = next_step(item, root)
    if offer['action'] != 'polish':
        raise Refused(f'{item} has no polish offer; run bin/wuwei dispatch next {item} for its step')
    return offer


def polish(item, root=None):
    """#723: open the offered polish round."""
    root = workspace.find_workspace(root)
    return _open_polish(root, item, _offered(root, item))


def skip_polish(item, root=None):
    """#723: decline the offered polish round; the notes ship as review notes."""
    root = workspace.find_workspace(root)
    offer = _offered(root, item)

    def update(fresh):
        row = _item(fresh, item)
        if row['phase'] != 'gate' or row.get('polish'):
            raise Refused(f'polish state changed during skip; {RACE}')
        row['polish'] = {'status': 'skipped', 'gate': offer['gate'], 'notes': offer['notes']}
    state._write_state(update, root, reserved=False, kind='polish.skipped',
                       payload={'item': item, 'gate': offer['gate'], 'notes': len(offer['notes'])})
    return {'action': 'raise', 'notes': offer['notes']}
```

Feedback texts:

```python
def _polish_feedback(notes):
    return ('Polish round: every gate passed. Fix only these non-blocking review notes, test first '
            'where a note names a behaviour, and change nothing else. A note that needs more than a '
            'small local change stays a review note; name it in your handoff.\n' + '\n'.join(notes))


def _recheck_feedback(row, first, light=False):
    """#723: a polish re-check reads the notes; any other delta keeps _delta_feedback."""
    polish = row.get('polish') or {}
    if first['verdict'] == 'FIX' or polish.get('status') != 'opened':
        return _delta_feedback(first, light)
    return (f'Polish re-check: the polish round changed {first["head"]}..HEAD to close these review '
            'notes:\n' + '\n'.join(polish['notes']) + f'\nRewrite {first["file"]} for the current HEAD: '
            'drop each note the delta closed, keep an open one as blocks: no, and block only on a '
            'defect the delta introduced.')
```

Call sites:

- `_seats` line 559: `feedback = _recheck_feedback(data['items'][item], first, depth(data['items'][item], gate=True) == 'light')`.
- `opinion` line 775: `_recheck_feedback(row, first) if round_name == 'delta' else ...`.
- `delta_due` line 575: `first['verdict'] == 'FIX'` becomes `rechecks(data, item, role)`
  (it already holds `first`; keep its other conditions).
- `receive` lines 632-634: `if first is None or not rechecks(data, item, role):` with the same
  refusal text.
- `opinion` line 743: `if round_name == 'delta' and not rechecks(data, item, gate):`.

### cli/wuwei/commands/build.py

`open_fix(item, feedback, *, root, polish=None)` (line 179):

- In `update(fresh)` (line 225), before the phase write: when `polish` is given, refuse
  with `ValueError(f'polish round already recorded for {item}; run bin/wuwei dispatch next {item}')`
  if `fresh['items'][item].get('polish')`, else set `fresh['items'][item]['polish'] = polish`.
- Event payload (line 236): add `'polish': True` when `polish` is given.

Nothing else in `open_fix` changes: the cap check, the brief name `<item>-gate-fix`, the
resume or launch choice and the feedback carriage are reused as they are.

### cli/wuwei/guards/pr.py

`_recorded_gates` (lines 103-129): compute once per candidate

```python
rechecked = {role for role, first in zip(roles, initial)
             if first['verdict'] == 'FIX' or f'{candidate}:{role}:delta' in records}
```

Line 105: `row = records.get(f'{candidate}:{role}:delta') if role in rechecked else first`.
Lines 125-127: the head condition `(first['verdict'] == 'FIX' or not any(... FIX ...))`
becomes `(role in rechecked or not rechecked)`. Without a polish round `rechecked` is the
FIX set, so behaviour is identical (no delta record exists for a PASS gate today: `receive`
refuses it).

### cli/wuwei/merge.py

Line 345: `selected = data['gate_verdicts'].get(f'{item}:{gate}:delta') or first`. Equal to
today for reachable states (`gate_check` above already requires a FIX gate's delta).

### cli/wuwei/commands/dispatch.py

`register`: `actions.add_parser('polish').add_argument('item')` and
`actions.add_parser('skip-polish').add_argument('item')`. `run`: dispatch
`args.action == 'polish'` to `dispatch.polish(args.item)` and `'skip-polish'` to
`dispatch.skip_polish(args.item)`; existing exit mapping.

### cli/wuwei/commands/next.py

`resolve`, `verdicts` branch (lines 383-393), before the generic return:

```python
        if action['action'] == 'polish':
            return _row('polish', f"{item}: every gate passed with {len(action['notes'])} review "
                        'note(s); one polish round fixes them before the PR.', action['command'],
                        item=item, then=f"Run the command, or run {action['skip']} instead when the "
                        'notes are not small fixes inside the item; then run wuwei next.')
```

### cli/wuwei/state.py and cli/wuwei/commands/event.py

- `_producer_error` item map (line 337-348): `'polish': 'wuwei dispatch polish or wuwei dispatch skip-polish'`.
- `EVENT_PRODUCERS` (event.py line 21): `'polish.skipped': 'wuwei dispatch skip-polish'`.

### Charters, docs, template

- `charters/_common.md` rule 5 (line 21): append "Polish (`gates.polish`, default offer):
  after a round-one pass with notes, `dispatch next` offers one polish round under the cap.
  The planner runs `wuwei dispatch polish <item>`, or `wuwei dispatch skip-polish <item>`
  when the notes are not small fixes inside the item; the builder fixes only the listed
  notes and names any it leaves; the gate that wrote the notes (quality when several did)
  re-checks the delta and blocks only on a defect the delta introduced." Bump `version`
  1.9.0 to 1.10.0; run `bin/wuwei agents build` to regenerate `agents/*.md`.
- `tests/test_charters.py` anchor list: `("polish round", "_common.md", "fixes only the listed notes")`.
- `docs/site/configuration.md` after the `gates.tier_max_rounds` row: `| gates.polish |
  "offer" | ... |` naming never, offer and always, the one re-check gate, the skip command
  and that it counts as a fix round.
- `templates/workspace/config.toml` `[gates]`: `# polish = "offer" # never, offer or always: one notes-only round after a pass.`
- `docs/site/reference.md` line 24 dispatch row: add "`dispatch polish <item>` and
  `dispatch skip-polish <item>` take or decline a polish round".

### tests/test_invariants.py and design 9.2

I58: "A polish round opens only from a round-one pass with notes, below the round cap, at
most once per item and never under `gates.polish = never`, and exactly one gate re-checks
it". `i58` (model on `i43`, pure, `rules.memo(('polish',), compute)`): walk mode {never,
offer, always} x note authors {none, arch, arch and quality, quality@codex} x recorded
{absent, opened, skipped} x used {0, cap}: `dispatch.polish_offer` is None exactly when
never, no notes, recorded or at the cap, and otherwise names the single author or quality;
and for a three-gate row with all-PASS initial records and `polish = {'status': 'opened',
'gate': g}`, `[r for r in roles if dispatch.rechecks(data, 'P', r)] == [g]`, and `[]` once
the row records a `pr`. Add `INVARIANTS['I58']`, `READS['I58'] = ()` and the 9.2 row after
I46 (`test_table_matches_the_checks` reads it).

## Data shape

`items.<item>.polish` (absent until decided):

```json
{"status": "opened", "gate": "quality", "notes": ["- P3 | cli/x.py:1 | fails when ... | blocks: no"]}
```

`status` is `opened` (written with the fix round) or `skipped`. `notes` are the recorded
note blocks, as `receive` stored them.

`dispatch next` polish action:

```json
{"action": "polish", "gate": "quality", "notes": ["..."],
 "command": "wuwei dispatch polish A", "skip": "wuwei dispatch skip-polish A"}
```

## Existing tests whose meaning changes

- `tests/test_dispatch.py::test_ordinary_finding_below_threshold_remains_a_note`: a
  round-one pass with a note now gets the polish offer at the default; assert
  `action == 'polish'` with the note (that is the note's new home), or set
  `[gates]\npolish = "never"\n` with `caps(root, ...)` and assert `raise` with the note.
- Any fixture that passes at round one with a note and expects `raise`: same fix, never by
  weakening an expectation. `raise` without notes (`'notes': []` in `test_e2e_day.py`,
  `test_parallel_dispatch.py`, `test_gate_stays_without_complete_fix_round`) is unchanged.
- `tests/test_workspace.py` line 234: the gates defaults gain `'polish': 'offer'`.

## What must not change

- A FIX at round one opens a fix round; a delta without a blocking finding raises with its
  notes; a blocking delta opens the next round or parks at the cap (#623).
- `build.open_fix`'s cap, count, brief naming, resume and `rotate`; `rounds_used`;
  `max_rounds`; the reset of `fix_rounds` at delta to raised (`state.py:474-475`).
- The verdict lint and its PASS-with-notes rule; `receive` for round `initial`.
- The auto-merge cycle budget (`merge.py:176-182`): a polish round counts as one fix cycle.
- `_delta_feedback` texts (standard and light) for a FIX gate.
- PR-stage fix rounds (`pr_actions._fix`) and their arch delta.
- The design spec outside the 9.2 row.

## Project Structure

```text
cli/wuwei/workspace.py          gates.polish
cli/wuwei/dispatch.py           polish_offer, rechecks, _open_polish, _offered, polish, skip_polish,
                                _polish_feedback, _recheck_feedback; next_step, _seats, delta_due,
                                receive, opinion call sites
cli/wuwei/commands/build.py     open_fix(polish=)
cli/wuwei/commands/dispatch.py  polish, skip-polish subcommands
cli/wuwei/commands/next.py      polish row
cli/wuwei/guards/pr.py          _recorded_gates reads a delta whenever it exists
cli/wuwei/merge.py              verdict digest selection
cli/wuwei/state.py              producer text for items.*.polish
cli/wuwei/commands/event.py     polish.skipped reserved
charters/_common.md, agents/*.md
docs/site/configuration.md, docs/site/reference.md, templates/workspace/config.toml
docs/specs/2026-09-24-wuwei-design.md   9.2 row I58 only
tests/test_dispatch.py, tests/test_pr_guards.py, tests/test_merge.py, tests/test_next.py,
tests/test_workspace.py, tests/test_charters.py, tests/test_invariants.py
```
