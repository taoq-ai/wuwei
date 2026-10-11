# Implementation Plan: a seat's small fix becomes an item without a ticket

**Branch**: `646-fix-from-finding` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

A seat records a small fix with `wuwei note --fix "<title>"` into the day's `seat_findings`.
`wuwei next` proposes each unadded finding as `wuwei plan add <id> --from-finding`, which
admits it through the existing owner-item path of `plan.add` as a light, unflagged SLICE item.
"Small" is the light tier. The one shared ticket rule, `tracker.check`, gains a status `later`
for an unticketed light item, so every refusal point (they all refuse only on `missing`) lets
it through without being touched. `plan approve` still runs the #636 creation for a `later`
item but does not refuse when it fails; `close` names `tracker create <item>` for a merged
`later` item, so the planner opens the ticket after it ships. The retro lists the findings.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime.
**Testing**: pytest, `python -m pytest -q` from the repository root; offline fakes
(`tests/fakes/tracker.py` `Fake` and `ported`).
**Storage**: the day's `state.json` (new key `seat_findings`) and `events.jsonl` (new kind
`finding.noted`), both through `state._write_state`.
**Constraints**: `next` runs on hook paths: no new imports there, the row reads `data` only.
`tracker` stays lazily imported where it is today.

## Constitution Check

- I stdlib only: yes.
- II exits: `note --fix` exits 0 recorded, 1 refused with the reason (`state.StateError`), 2 on
  an unreadable state or no workspace. `plan add` keeps its exits.
- III one behaviour, one function: the ticket rule stays in `tracker.check`; the new status is
  one branch there, read by every caller. No caller gets its own exemption.
- IV test first: tasks.md orders a failing test before each change.
- V ponytail: no schema field for "small" (the lead's `tier` already exists), no new verb
  (`note --fix` is a flag on the existing `note` parser), no carry-over of findings, no seat
  attribution. `plan.add` already takes `source` (used by `shepherd.claim_pr` with `adopted`).
- VII security: the finding title is seat-written text the planner reads; it is bounded to one
  line of at most 120 characters with no absolute path. `seat_findings` and `finding.noted`
  are reserved for their one producer. A finding item is unflagged and light, and dispatch
  only raises a lead tier (`dispatch.py` lines 115 to 127), so no gate is lowered.
- Workflow: the rule change touches what the Agent launch guard refuses, so design 9.2 gains
  I56 with its check in `tests/test_invariants.py`.

## Design

### 1. `cli/wuwei/tracker.py` `check` (lines 35 to 53): the `later` status

Read the deciding tier once and add one branch after the `skipped` return, before the pending
draft lookup:

```python
    tier = row.get('gates', {}).get('tier') or row.get('tier')
    if (tier in config['tracker']['skip_tiers']
            or data.get('tickets', {}).get(item, {}).get('source') == 'none'):  # #636: the owner's none
        return 'skipped', ''
    if tier == 'light':  # #646: a small item never waits for its ticket (gate or after it ships)
        return 'later', ''
```

Update the docstring to `(off|ticket|skipped|later|missing, reason)`. Nothing else in `check`
changes. Callers that refuse compare to `'missing'` and need no change: `build.py` line 148,
`dispatch.py` line 337, `agent_launch.py` line 238, `plan.add` line 514. `plan.approve`'s
update loop (lines 427 to 433) only acts on `missing` and `skipped`, so a `later` item is
admitted with no event.

### 2. `cli/wuwei/tracker.py` `_candidate` (lines 63 to 68): a finding item's record

`tracker.create(root, <item>)` (class `items`) reads the row from today's proposal, then
`discovery_candidates`. Add the finding as the last fallback, with the day item's goal:

```python
    found = data.get('seat_findings', {}).get(item)  # #646: a seat's finding added as an item
    return next((row for row in rows if row.get('id') == item),
                data.get('discovery_candidates', {}).get(item)
                or found and {**found, 'goal': data['items'].get(item, {}).get('goal', 'unplanned')})
```

The ticket title is the finding's `scope` (its title), the body its evidence, goal and track,
by the existing code at lines 87 to 93.

### 3. `cli/wuwei/plan.py` `approve` (lines 400 to 411): create for `later`, never refuse on it

```python
        for name in items:  # #636: the Approve answer listed these new tickets; it is their Send
            status = tracker.check(current, config, name, candidates[name])[0]
            if proposed(candidates[name], found) is not None or status not in ('missing', 'later'):
                continue
            result = tracker.create(root, name)
            if result.exit == 1 and isinstance(result.data, dict) and result.data.get('draft'):
                result = drafts.approve(root, result.data['draft'])
            if result.exit and status == 'missing':  # #646: a small item is approved without it
                reasons.append(f'{name}: {result.reason}')
```

The strict branch, `_tickets` (plan.md and the gate card already show `new <scope>` for a light
item with no ticket) and the update loop are unchanged.

### 4. `cli/wuwei/plan.py` `add` (lines 463 to 564): the finding path

`add` already has `source` (shepherd passes `adopted`). For `source == 'finding'`, right after
the `item in day['items']` block and before `config = ...`:

```python
    if source == 'finding':  # #646: a seat's finding joins as a small item, ticket later
        finding = day.get('seat_findings', {}).get(item)
        if finding is None:
            raise state.StateError(f'{item} is not a seat finding; wuwei next lists the findings to add')
        goal, title = goal or day['goals'][0], finding['scope']
```

and in the owner-item `candidate` dict add `**({'tier': 'light'} if source == 'finding' else
{})`. The rest follows the existing owner path: `--goal` checked against today's goals,
`tracker.check` returns `later`, the #636 create block (`status == 'missing'`, line 503) does
not run, `admit` stores `tier`, `source` and `title` (lines 552 to 555), `plan.added` records
`source: finding`.

`cli/wuwei/commands/plan.py`: `add.add_argument('--from-finding', action='store_true',
help="Admit a seat's finding (wuwei next lists them) as a small item; its ticket comes later")`
and pass `source='finding' if args.from_finding else None` to `plan.add`. The positional `item`
stays, so both `plan add --from-finding <id>` and `plan add <id> --from-finding` parse.

### 5. `cli/wuwei/commands/note.py`: `note --fix "<title>"`

On the `note` parser: `parser.add_argument('--fix', metavar='TITLE', help='Record a small fix a
seat found; wuwei next proposes it as an item')`, `parser.set_defaults(func=run_fix)`, and the
verb subparsers no longer `required` (the `add` subparser's own `func=run_add` default still
wins for `note add`). `run_fix(args)`:

- `args.fix is None`: print `wuwei note: pass add <slug> or --fix "<title>"` to stderr, return
  `UNRUN`.
- title = `' '.join(args.fix.split())`; refuse (`FINDINGS`) when empty, when `args.fix` is not
  one line, over 120 characters, when `profiles.ABSOLUTE` matches, or when it has no
  `[a-z0-9]` word. Reasons name the accepted form.
- id = `'fix-' + '-'.join(re.findall(r'[a-z0-9]+', title.lower())[:6])`.
- `state._write_state(update, root, reserved=False, kind='finding.noted', payload={'id': id,
  'title': title})` where `update` raises `state.StateError(f'{id} is already recorded; wuwei
  next proposes it')` when the id is in `seat_findings` or `items`, else sets
  `seat_findings[id] = {'scope': title, 'evidence': 'seat finding', 'track': 'SLICE', 'at':
  workspace.now().isoformat()}`.
- print the id; `StateError` returns `FINDINGS` with the reason, `OSError`, `ValueError` return
  `UNRUN` with the reason.

`wuwei note add` is unchanged. `commands.READ_ONLY`/`WRITES` need no entry: the registered path
set stays `note add`, and `read_only(['note', '--fix', 'x'])` is already `False`.

Reserve the producer: `cli/wuwei/state.py` producer table (line 255 onward) gains
`'seat_findings': 'wuwei note --fix'`; `cli/wuwei/commands/event.py` `EVENT_PRODUCERS` gains
`'finding.noted': 'wuwei note --fix'`, so `wuwei event finding.noted` is refused.

### 6. `cli/wuwei/commands/next.py` `step`: the `finding` row

After the stuck-seat row (line 234) and before `rows = state.in_flight(data)` (line 237):

```python
    for ident, finding in data.get('seat_findings', {}).items():  # #646: proposed once
        if ident not in data['items'] and ('finding', ident) not in returned:
            return _row('finding', f"A seat found a small fix: {finding['scope']}. Add it as a "
                        'small item; its ticket follows after it ships.',
                        f'wuwei plan add {ident} --from-finding', item=ident)
```

`returned` already holds a row whose command ran, passed or came back three times (`_seen`),
so a finding the planner does not add stops being proposed. No import is added.

### 7. `cli/wuwei/closing.py` `unresolved` (lines 222 to 227): the ticket after it ships

```python
                number = tracker.ticket(data, name)
                line = None
                if tracker.in_force(config) and item['phase'] == 'merged':
                    if number and name not in done:
                        line = f'{name}: ticket {number} is not done: bin/wuwei tracker done {name}'
                    elif not number and tracker.check(data, config, name, item)[0] == 'later':
                        line = f'{name}: shipped without a ticket: bin/wuwei tracker create {name}'
                if line:
                    if config['tracker']['strict_close']:
                        findings.append(line)
                    else:
                        print(line, file=sys.stderr)
```

After `tracker create`, the existing done line asks `tracker done <item>`, as for every item.

### 8. `cli/wuwei/retro.py` `compile`: `## Seat findings`

After the Cycle lines (line 100, after `cycle_moved`):

```python
    found = data.get('seat_findings', {})
    lines += ['', '## Seat findings', *([f"- {ident}: {row['scope']} ("
              + (f"item {data['items'][ident]['phase']}" if ident in data['items'] else 'not added')
              + ')' for ident, row in sorted(found.items())] or ['none'])]
```

`closing.retro` only requires `Applied` and `Proposed` and refuses duplicates; the new heading
is unique.

### 9. Charters, agents and docs

- `charters/builder.md`: new step 12 after step 11: "A small, valuable fix outside your item's
  promise (a CI pin, a lint rule, a one-line check): record it with `wuwei note --fix
  "<title>"` and stay on your item; the planner adds it as its own small item. A bug outside
  your scope still goes through `tracker create --bug`."
- `charters/lead.md` step 3, after the ticket sentences: "A small fix you find that is not
  worth a ranked candidate: record it with `wuwei note --fix "<title>"`. A candidate with
  `tier` `light` starts without a ticket; the gate opens it."
- `charters/planner.md` step 3, at the end: "A seat finding that `wuwei next` proposes joins
  with `wuwei plan add <id> --from-finding`: a small item that starts with no ticket. When
  `close` names `bin/wuwei tracker create <item>` for it after it ships, run it."
- Run `bin/wuwei agents build` to regenerate `agents/builder.md`, `agents/lead.md`,
  `agents/planner.md`; do not hand-edit `agents/`.
- `docs/site/reference.md` row `bin/wuwei note` (line 50): add "`--fix "<title>"` records a
  small fix a seat found; `next` proposes it." Row `bin/wuwei plan` (line 55): add "`add <id>
  --from-finding` admits a seat's finding as a light item that starts without a ticket".

### 10. Design 9.2 and `tests/test_invariants.py`

Row after I38 in the 9.2 table (`test_table_matches_the_checks` compares the order with
`INVARIANTS`):

`| I56 | A small item never waits for its ticket: an unticketed item whose deciding tier is
light reads later in tracker.check, which no refusal point refuses; once its gate tier is
standard or full it reads missing again | per posture, tracker.check on an unticketed item
with lead tier light, and with lead tier light and gate tier standard | #646; the gate opens
its ticket, or close names tracker create after it ships |` (one line in the file, backticks
on code names as in I36).

`i56(case, rules)`: under `rules.memo(('small ticket', case[0]), compute)`, build the config
as `tests/test_tracker.py` `config()` does with posture `case[0]` and `skip_tiers = []`; return
a message unless `tracker.check({}, config, 'A', {'tier': 'light'}) == ('later', '')` and
`tracker.check({}, config, 'A', {'tier': 'light', 'gates': {'tier': 'standard'}})[0] ==
'missing'`. Append `'I56': i56` to `INVARIANTS` and `'I56': (0,)` to `READS` (last entries).
Renumber if another branch takes I56 first.

## Files

| File | Change |
|---|---|
| `cli/wuwei/tracker.py` | `check`: `later`; `_candidate`: finding fallback |
| `cli/wuwei/plan.py` | `approve` create loop; `add` finding path |
| `cli/wuwei/commands/plan.py` | `--from-finding` |
| `cli/wuwei/commands/note.py` | `--fix`, `run_fix` |
| `cli/wuwei/commands/next.py` | `finding` row |
| `cli/wuwei/closing.py` | shipped-without-ticket line |
| `cli/wuwei/retro.py` | `## Seat findings` |
| `cli/wuwei/state.py`, `cli/wuwei/commands/event.py` | producer entries |
| `charters/builder.md`, `charters/lead.md`, `charters/planner.md`, `agents/*.md` | one line each, regenerated |
| `docs/site/reference.md` | two rows |
| `docs/specs/2026-09-24-wuwei-design.md` | 9.2 row I56 only |
| `tests/test_notes.py`, `tests/test_tracker.py`, `tests/test_plan.py`, `tests/test_intraday_intake.py`, `tests/test_next.py`, `tests/test_stop.py`, `tests/test_report_retro.py`, `tests/test_invariants.py` | new tests |

## What must not change

- `tracker.check` for every non-light item, for a ticketed item, for a tier in `skip_tiers`
  (still `skipped` with its event) and for the owner's none; its two `missing` reasons.
- `plan approve` refusal for a non-light item without a ticket, the strict branch, the gate
  card and `_tickets`.
- `plan add` for discovery candidates (the intraday policy) and for owner-named items (the #636
  draft at add, the `--ticket` path, the #481 form reason).
- `tracker.create` idempotency, the absolute-path refusal, class creates; `tracker.record`.
- `note add` and memory notes; `notes.parse_note`.
- `next` row order for every existing state; the hook-path import set of `next.py`.
- `dispatch` tiering: a lead tier only raises the computed tier.
- The close done line and `strict_close`.

## Tests to revisit

Existing tests that assert a missing-ticket refusal on an item whose tier ends up `light` now
pass by design. Run `tests/test_dispatch.py`, `tests/test_build_next.py`,
`tests/test_agent_launch.py`, `tests/test_intraday_intake.py` and `tests/test_plan.py` after
step 1; for any such test, give the item a standard tier (its intent is the refusal) rather
than changing the rule. `test_dispatch_refuses_an_item_without_a_ticket` and
`test_light_item_skips_the_ticket_until_its_tier_rises` are the likely ones.
