# Implementation Plan: after a gate blocks, next offers the fix round or the decision card and writes the record the gate asked for

**Branch**: `732-next-after-block` | **Date**: 2026-10-10 | **Spec**: `specs/732-next-after-block/spec.md`

## Summary

The gate decision already lives in one function, `dispatch.next_step`
(`cli/wuwei/dispatch.py`), which `dispatch next`, `build next` (#666), `next` and
`dispatch next --all` all call. The fix is there:

1. A PARK or ESCALATE verdict becomes a card (written once, id on the verdict record) whose
   recorded answer opens the fix round or parks the item. Until then `escalate` carries
   the card id and the command that answers it.
2. A blocking gate with no round left, and the `fix round already used` branch, park the
   item through the existing park-with-record writer `plan.dispose`, which now links its
   record on the item.
3. An item parked on a linked record answers `escalate` with that record from `next_step`,
   and `build next` asks `next_step` for it, so both commands agree.

Reused, not rewritten: `decision.write` (allocate and lint a D-n), `decision.route_owner`
(owner route under strict), `plan.dispose` (park with record), `build.open_fix` (fix
round), `max_rounds` and `rounds_used` (#623), the `items.<item>.decision` link that
`commands/decision.py` `owner_outcome`, `why` and `report` already read. No new module, no
config key.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest (dev only), in-process through `wuwei.__main__.main` and the helpers of
`tests/test_dispatch.py` (`root`, `built`, `record`, `gate_fix`, `caps`, `cli`,
`build_next`, `fix_events`)
**Constraints**: `next_step` stays a planner command (never on a hook path); every state
write goes through `state._write_state`; a card file is allocated by `decision.write`
(never replaced)

## Constitution Check

- I. Stdlib only: no new import outside `wuwei`.
- II. Exits: unchanged. `escalate` exits 1 from `dispatch next` and `build next`; a card
  that cannot be written (lint, OSError) exits 2 through the existing handlers; a race on
  the card id raises `Refused(... RACE)`, exit 1, like the tier race at `dispatch.py:325`.
- III. One behaviour, one function: the blocked-gate route is decided only in
  `next_step`; `build next` and `next` print what it returns.
- IV. Test first: every task in `tasks.md` has its failing test first.
- V. Ponytail: three small private helpers in `dispatch.py`, one linking keyword in
  `plan.dispose`, one condition in `build.run`, one row change in `next.resolve`, one retro
  table. Deleted: the early PARK/ESCALATE return.
- VII. Security: below strict the planner answers a two-way, own-branch card (the existing
  route rules); under strict the card is written for the owner and routed to the owner. No
  new trusted key is seat-writable without the state guard; `gate.card` is reserved to
  `wuwei dispatch next`.
- Workflow: a changed decision rule adds its invariant to design 9.2 and
  `tests/test_invariants.py` (I59, or the next free id when this lands).

## Design

### 1. Helpers in `cli/wuwei/dispatch.py`

Module constant `CARD`, a decision record template modeled on `build._park`
(`cli/wuwei/commands/build.py:444-458`), formatted with `item`, `role`, `verdict`, `file`,
`fix`/`park` want scores, `recommendation` and `by`:

```text
Question: Gate {role} says {verdict} on {item}: open a fix round or park it?
Class: park
Context: {file} holds the {verdict} verdict and its findings.
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| fix | Open a fix round | The verdict file names the finding and what closes it. | The builder fixes the blocking findings and the gate checks them again. |
| park | Defer and park the item | Stops spending until the finding is reconsidered. | The item pauses until the owner resumes it. |
Musts:
| Criterion | fix | park |
| --- | --- | --- |
| Within the round cap | pass | pass |
Wants:
| Criterion | Weight | fix | park |
| --- | --- | --- | --- |
| Follows the gate verdict | 10 | {fix} | {park} |
Recommendation: {recommendation}
Reasoning: The gate's {verdict} verdict decided it; the owner's answer on this card would flip it.
Confidence: medium
Reversibility: two-way
Blast radius: own branch
Pre-mortem: A fix round that cannot close the finding spends a round; the round cap then parks the item.
Revisit: When the fix round's delta verdict is in, or when the owner resumes the item.
Decided-by: {by}
Outcome: pending
```

The park title starts with Defer because the decision lint requires a Do nothing, Defer
or Keep option (found while building). `recommendation` is `park` for PARK and `fix` for ESCALATE (the recommended option scores
10, the other 0). `by` is `owner` under strict (`workspace.posture(config)[0] == 'strict'`),
else `seat`. No finding text is copied into the card.

```python
def _waiting(item, ident, reason, owner=True):
    """#732: every escalate names its record and the command that answers it."""
    return {'action': 'escalate', 'reason': reason, 'decision': ident,
            'command': f'wuwei decision show {ident} --widget' if owner
            else f'wuwei decision route {ident}'}


def _parked(root, item, reason):
    """#732: a blocked item with no round left parks with its record (plan.dispose)."""
    from wuwei import plan
    return _waiting(item, plan.dispose(item, 'parked', reason, root), reason)


def _card(root, config, data, item, role, round_name):
    """#732: (id, recorded option or None) of the card a PARK or ESCALATE verdict asks
    for; written once, its id kept on the verdict record; routed to the owner under strict."""
```

`_card` body:

- `key = f'{item}:{role}:{round_name}'`, `result = data['gate_verdicts'][key]`,
  `ident = result.get('decision')`, `strict = workspace.posture(config)[0] == 'strict'`.
- When `ident` is None: format `CARD`; `payload = {'item': item, 'role': role, 'round':
  round_name}`; in one `state._write_state(update, root, reserved=False, kind='gate.card',
  payload=payload)` whose `update(fresh)` raises `Refused(f'gate card changed during
  dispatch; {RACE}')` when `fresh['gate_verdicts'][key].get('decision')` is set, else calls
  `decision.write(text, root)`, stores `path.stem` on `fresh['gate_verdicts'][key]
  ['decision']` and in `payload['decision']` (the `plan.dispose` pattern).
- When `strict` and `ident not in data.get('decision_routes', {})`: `decision.route_owner(
  ident, decision.evaluate(decision.today_path(ident, root).read_text(encoding='utf-8'))[0],
  root)` (idempotent; also repairs a card whose route did not land).
- Return `ident, (data.get('decision_outcomes', {}).get(ident) or {}).get('option')`.

### 2. `next_step` (`cli/wuwei/dispatch.py:296-397`)

- After `phase = row['phase']` (line 307), before the phase refusal:

  ```python
  if phase in ('parked', 'escalated') and row.get('decision'):
      return _waiting(item, row['decision'], f'{item} is {phase} on decision {row["decision"]}')
  ```

- Line 345-346: `return _parked(root, item, 'fix round already used')`.
- Lines 350 and 359: the initial verdict test `== 'FIX'` becomes `!= 'PASS'`.
- Delete lines 361-364 (the early PARK/ESCALATE return).
- Replace lines 373-397 (after `results`) with one tail for both rounds:

  ```python
  asked = [role for role, result in zip(roles, results) if result['verdict'] in ('PARK', 'ESCALATE')]
  blocking = [role for role, result in zip(roles, results) if role in asked or (
      result['verdict'] == 'FIX' if phase == 'gate' else result['blocks'])]
  if not blocking:
      return {'action': 'raise', 'notes': [] if phase == 'gate' else
              [note for result in results for note in result['notes']]}
  first = results[roles.index(blocking[0])]
  cap = max_rounds(config, row)
  if rounds_used(data, item) >= cap:  # #623: a park with its finding at the cap
      finding = next((text for text in first['findings'] if re.search(verdict.BLOCKS_YES, text, re.I)),
                     (first['findings'] or [''])[0])
      return _parked(root, item, <today's round-cap reason text, unchanged>)
  if asked:  # #732: the verdict's decision request is a card; its answer decides
      ident, answer = _card(root, config, data, item, asked[0], round_name)
      if answer is None:
          head = (first['findings'] or [''])[0]  # first finding of the asking gate
          return _waiting(item, ident, f'gate {asked[0]} {verdict-of-asked[0]}: '
                          f'{" ".join(head.splitlines()[0].split()) if head else "no finding"}',
                          owner=strict-or-routed)
      if answer == 'park':
          <one state write: items[item].update(phase='parked', status='blocked', decision=ident),
           kind 'state.transition', payload {'item', 'phase': 'parked', 'decision': ident}>
          return _waiting(item, ident, f'{item} parked on decision {ident}')
  from wuwei.commands import build
  build.open_fix(item, _fix_feedback(data, item, blocking, round_name), root=root)
  return _fix(item, blocking)
  ```

  `strict-or-routed` is `workspace.posture(config)[0] == 'strict' or ident in
  data.get('decision_routes', {})`; return it from `_card` as a third value if that is
  shorter. The waiting reason uses the asking gate's own first finding (blocking findings
  sort first, #677), not `first`, when `asked[0] != blocking[0]`.
- `_fix_feedback` (line 609): `Gate {role} FIX:` becomes `Gate {role} {record['verdict']}:`.

Behaviour that stays: the `gates` answer while verdicts are missing, the FIX round, the
round-cap reason text (`round cap N reached: <gate> still blocks: <finding>; unpark after a
design change that closes it is recorded in the spec`), `raise` and its notes.

### 3. Delta re-gates every non-PASS gate (`cli/wuwei/dispatch.py`)

`delta_due` (line 575) `first['verdict'] == 'FIX'` becomes `!= 'PASS'`; `receive`
(line 633) and `opinion` (line 743) `first['verdict'] != 'FIX'` become `== 'PASS'`.
Without this, an ESCALATE gate answered `fix` is never re-checked and the item raises.

### 4. `plan.dispose` links its record (`cli/wuwei/plan.py:720`)

`record.update(phase='parked', status='blocked', decision=path.stem)`. `owner_outcome`
then resumes the item on the owner's answer, `why` names the record and the report's
`## Parked` stops printing `unmeasured` for it.

### 5. `build next` asks `next_step` for a parked item (`cli/wuwei/commands/build.py:41`)

```python
row = state.read_state(root)['items'][item]
if action['action'] == 'done' and (row['phase'] in ('gate', 'delta') or (
        row['phase'] in ('parked', 'escalated') and row.get('decision'))):
```

The rest of the branch (refusal exit 1, `fix` reading the build record, exit 1 on
`escalate`) is unchanged.

### 6. `next` prints the answer's command (`cli/wuwei/commands/next.py:389-391`)

```python
if action['action'] == 'escalate':
    return _row(name, f"{item}: {action['reason']}; decision {action['decision']}.",
                action['command'], item=item)
```

### 7. Retro `## Blocks` (`cli/wuwei/retro.py`)

A `_blocks(data)` helper next to `_second_opinion`, called after it in `compile`:

```text
## Blocks
| Item | Gate | Verdict | Followed |
| --- | --- | --- | --- |
```

One row per `data['gate_verdicts']` value whose `verdict` is not PASS, sorted by key:
`item`, `role round`, `verdict`, and Followed, the first that holds:
`card D-n: <option>` or `card D-n: open` (record has `decision`);
`parked: <items.<item>.decision or no record>` (item at `parked` or `escalated`);
`fix round <builds.<item>.fix_rounds>` (when above 0); else `none yet`.
No row: `| none | | | |`.

### 8. Reserved event kind (`cli/wuwei/commands/event.py`)

Add `'gate.card': 'wuwei dispatch next'` to `EVENT_PRODUCERS`.

### 9. Invariant and docs

- `docs/specs/2026-09-24-wuwei-design.md`, 9.2 table, a new row after I44:
  `| I59 | A blocking gate verdict never ends in a bare escalate: dispatch next answers a fix round, or an escalate naming its decision record and the command that answers it; a PARK or ESCALATE verdict's card is written once, for the planner below strict and routed to the owner under strict | per posture, dispatch.next_step twice on a light item whose quality verdict is ESCALATE: one D-n, the same id twice, command wuwei decision route D-n below strict and wuwei decision show D-n --widget under strict with the card in decision_routes | #732; tests/test_dispatch.py runs both commands through main |`
  (columns as the neighbouring rows; take the next free id if I59 is taken when this lands).
- Same file, the "Negotiation budget" bullet (5.3): one amendment line:
  `Amended (owner, 2026-10-10, #732): a PARK or ESCALATE verdict is a decision card that dispatch next writes from the verdict (fix or park; the planner answers below strict, the owner under strict); a blocked item with no round left parks with its record; every escalate names the record and the command that answers it, and build next prints the same.`
- `tests/test_invariants.py`: `i59(case, rules)` reading posture only
  (`READS['I59'] = (0,)`), memoized per posture, in its own workspace under
  `rules.root / f'gate-card-{posture}'` (the `i35` pattern): config
  `[spec]\nengine = "none"\n[security]\nposture = "<posture>"\n`, state seeded with
  `gate_approved`, the item approved at `gate` with `gates = {'tier': 'light', 'roles':
  ['quality']}`, a stopped builder seat and one `R56:quality:initial` ESCALATE record
  (`blocks`, `findings`, `notes`, `file`, `head`); call `dispatch.next_step` twice and
  return a message on any deviation.
- `docs/site/daily.md` steps 4 and 5: one sentence each: a PARK or ESCALATE verdict returns
  `escalate` with `decision` and `command` (route it, or the owner answers it under
  strict); the answer opens the fix round or parks the item; with no round left the item
  parks with its record.

## What must not change

- `build.next_action`, `build.open_fix`, `build.run_loop`, `rotate`, `max_rounds`,
  `rounds_used`, `receive`'s lint and HEAD checks, `launch_set`.
- The FIX path, the `gates` answer while verdicts are missing, the `raise` answer and the
  round-cap reason text.
- The verdict format, the verdict lint, the charters and the rendered agents.
- `decision.write`, `route_owner`, `owner_outcome` and the route rules.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/dispatch.py` | `CARD`, `_waiting`, `_parked`, `_card`; `next_step` tail; four `FIX` tests; `_fix_feedback` wording |
| `cli/wuwei/plan.py` | `dispose` links `decision` |
| `cli/wuwei/commands/build.py` | `run` asks `next_step` for a parked item with a record |
| `cli/wuwei/commands/next.py` | `verdicts` escalate row uses the answer's command |
| `cli/wuwei/retro.py` | `## Blocks` table |
| `cli/wuwei/commands/event.py` | reserve `gate.card` |
| `docs/specs/2026-09-24-wuwei-design.md` | I59 row, 5.3 amendment line |
| `docs/site/daily.md` | gate steps 4 and 5 |
| `tests/test_dispatch.py` | new acceptance tests; updated escalate expectations |
| `tests/test_next.py` | escalate row expectation |
| `tests/test_report_retro.py` | blocks table (the `retro.compile` tests live there) |
| `tests/test_invariants.py` | `i59` |

## Risks

- Existing tests that assert the exact `{'action': 'escalate', 'reason': 'fix round already
  used'}` (`tests/test_dispatch.py:110`, `:179` and the residual-note test) and the
  round-cap test that expects `wuwei plan park` from `next`
  (`test_issue_acceptance_blocking_trust_finding_at_round_three_parks`) change: they now
  assert `escalate` with the same reason plus `decision` and `command`, and a parked item.
- Report and close tests that read a `plan park` item's decision may now see the linked id
  instead of `unmeasured`; update an expectation only where it asserted `unmeasured` for a
  parked item.
