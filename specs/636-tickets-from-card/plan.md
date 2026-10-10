# Implementation Plan: tickets from the card

**Branch**: `636-tickets-from-card` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The proposal already has a ticket field (`ticket`) and `tracker.create` already builds a new
ticket from the item's record. This feature shows both on the plan and the gate card, makes
`plan approve` open the new ones itself below strict (`tracker.create` plus `drafts.approve`
on the held draft: the Approve answer is the Send), makes `plan add` draft an owner item's
ticket for its Send card, moves item tickets from "owner or any seat" to "the planner below
strict, the owner under strict" in the guard, and rewords the one missing-ticket reason. Two
small helpers in `plan.py`: `proposed` replaces the two copies of "which ticket does this
candidate carry" in `approve` and `add`; `_tickets` is the text `propose` and `gate_widget`
both show.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new config key,
no new event kind, no new port operation, no change to `outward.classify`, `tracker.auto` or
`drafts.approve`.

## Constitution Check

- I stdlib: no new import beyond in-repo modules.
- II exits: a creation failure in `plan approve` is a refusal with the adapter's reason
  (`StateError`, exit 1; the adapter's own exit 2 reason is kept in the text), nothing
  approved. `plan add` refuses with exit 1 while the draft waits.
- III one behaviour one function: "the ticket a candidate carries" is `plan.proposed`; "may
  this item run" stays `tracker.check`; "open an item ticket" stays `tracker.create`; "send a
  held draft" stays `drafts.approve`.
- IV test first: tasks.md orders a failing test before each change.
- V simplicity: no title matcher (the lead judges), no `tracker link` verb, no new proposal
  field (absence of `ticket` is "new"), no second card.
- VII security: the guard change is a narrowing for seats (item tickets were open to every
  seat) and a planner pass below strict modelled on `plan set pace=` (#579). It adds 9.2 row
  I36 with its check (constitution Workflow). `plan add` never sends: a seat can reach it.

## Design

### cli/wuwei/tracker.py

`check` (lines 35 to 48): keep the order; add the owner's none to the skip test and word the
two missing reasons by posture with the shared `workspace.posture`:

```python
    row = row or {}
    if ((row.get('gates', {}).get('tier') or row.get('tier')) in config['tracker']['skip_tiers']
            or data.get('tickets', {}).get(item, {}).get('source') == 'none'):  # #636: the owner's none
        return 'skipped', ''
    strict = workspace.posture(config)[0] == 'strict'
    draft = pending(data, item)
    if draft:
        return 'missing', (f'{item} has no ticket: the owner runs bin/wuwei drafts approve {draft} '
                           'in a host terminal' if strict else
                           f'{item} has no ticket: draft {draft} opens it once the owner answers '
                           f'Send on its card (bin/wuwei drafts show {draft} --widget)')
    return 'missing', (f"{item} has no ticket: the owner runs bin/wuwei tracker create {item} (opens "
                       f"one from the item's record) or bin/wuwei plan set {item} ticket=<id> in a "
                       'host terminal' if strict else
                       f"{item} has no ticket: the planner proposes one on the item's card (an "
                       "existing ticket or a new one from its record) and records the owner's answer")
```

`workspace` is already imported at the top of `tracker.py`. `check` stays pure.

`create(root, subject, category='items', title=None, evidence=(), row=None)`: for `items`,
`row = row or _candidate(root, data, subject)`. Nothing else changes (idempotency key,
queued-draft reuse, absolute-path refusal, `record`).

### cli/wuwei/plan.py

1. `_proposal` (lines 91 to 93): `"ticket": null` is valid:
   `if item.get('ticket') is not None and not (isinstance(...) and re.fullmatch(TICKET, ...))`.
   A string still has to match `TICKET`.

2. New helper next to `owner_steps`:

```python
def proposed(row, tracked=()):
    """#636: the ticket record a candidate carries: its ticket field (None is the owner's
    none), its own id when discovered from the tracker, or None for a new ticket."""
    if 'ticket' in row:
        return {'id': row['ticket'], 'source': 'candidate' if row['ticket'] else 'none'}
    if row['id'] in tracked or row.get('source') == 'tracker':
        return {'id': row['id'], 'source': 'tracker'}
    return None
```

   And the text both surfaces show, empty when tracker hygiene is off:

```python
def _tickets(config, rows, tracked):
    """#636: {item: '<id> (existing)' | 'new <title>' | 'none'} for the plan and the gate card."""
    from wuwei import tracker
    if not tracker.in_force(config):
        return {}
    texts = {}
    for row in rows:
        if row.get('tier') in config['tracker']['skip_tiers']:
            continue
        record = proposed(row, tracked)
        texts[row['id']] = ('new ' + ' '.join(row['scope'].split()) if record is None else
                            'none' if record['id'] is None else f'{record["id"]} (existing)')
    return texts
```

   The new-ticket title is the same expression `tracker.create` uses (`tracker.py` line 91).

3. `propose`: `tracked = {row['id'] for row in data['discovered'] if row.get('source') ==
   'tracker'}`; `shown = _tickets(config, data['candidates'], tracked)`; in the per-candidate
   lines, after the `Flags:` line, `*([f'Ticket: {shown[item["id"]]}'] if item['id'] in shown
   else [])`.

4. `gate_widget`: load `config = workspace.load_config(root)`, the same `tracked` from
   `data.get('discovered', [])`, `shown = _tickets(config, data['candidates'], tracked)`, and
   add one part after the queue part:
   `*(['tickets ' + ', '.join(f'{name} {text}' for name, text in shown.items())] if shown else [])`.
   In the Change something description, name tickets among the separate questions ("goals,
   queue, tickets, seat policy, ..."). The options, the record command and the card count do
   not change.

5. `approve`:
   - Replace lines 364 to 368 with
     `record = proposed(candidates[name], tracked)` and
     `if name not in tickets and record: tickets[name] = record`.
     (Same records as today for a string ticket and a tracker id; the owner's none adds
     `{'id': None, 'source': 'none'}`.)
   - Before `def update`, below strict, open the new tickets the card approved (inline, one
     caller; `drafts` imported locally like `tracker`):

```python
    current, reasons = state.read_state(root), []
    if (tracker.in_force(config) and workspace.posture(config)[0] != 'strict'
            and not current.get('gate_approved')):
        for name in items:  # #636: the Approve answer listed these tickets; it is their Send
            if (proposed(candidates[name], tracked) is not None
                    or tracker.check(current, config, name, candidates[name])[0] != 'missing'):
                continue
            result = tracker.create(root, name)
            if result.exit == 1 and isinstance(result.data, dict) and result.data.get('draft'):
                result = drafts.approve(root, result.data['draft'])
            if result.exit:
                reasons.append(f'{name}: {result.reason}')
    if reasons:
        raise state.StateError('\n'.join(reasons))
```

     `tracker.create` finds each row in `proposal.json` (`_candidate`), so no row is passed.
     It returns the recorded ticket on a rerun and reuses a queued draft, so a rerun opens
     nothing twice. `tracker.record` (through `drafts.approve`) writes `tickets[name]` before
     the gate write, and `update` keeps `current.get('tickets', {})`, so the check inside
     `update` finds them. Under strict nothing is opened and `update` refuses with the strict
     reasons (acceptance 2). `gate_approved` already set: nothing is opened and `update`
     refuses as today.
   - The skipped event (line 401): `{'item': name, 'tier': candidates[name]['tier']}` raises
     `KeyError` for an owner's none without a tier. Write
     `{'item': name, 'ticket': 'none'}` when `proposed(candidates[name], tracked)` has
     `id is None`, else the current payload.

6. `add`:
   - Replace `chosen = (...)` (lines 445 to 446) with `chosen = proposed(candidate)` (a
     discovery candidate's `source == 'tracker'` is read inside `proposed`).
   - When `status == 'missing'`, `owner_item` and the posture is not strict, draft the
     ticket for its Send card, then refuse with the fresh reason:

```python
    if status == 'missing' and owner_item and workspace.posture(config)[0] != 'strict':
        opened = tracker.create(root, item, row={'scope': candidate['title'],
                                                 'goal': candidate['goal'],
                                                 'track': candidate['track'],
                                                 'evidence': 'named by the owner'})
        if opened.exit == 0:
            status = 'ticket'
        elif isinstance(opened.data, dict):
            reason = tracker.check(state.read_state(root), config, item, candidate)[1]
        else:
            reason = opened.reason
    if status == 'missing':
        raise state.StateError(reason)
```

     With the default `tracker.auto` the create is held as a draft (exit 1, `data={'draft':
     ...}`), so the reason is the pending-draft card reason. With `items` in `tracker.auto`
     the owner chose auto-send, the ticket is created and the item is admitted. A discovery
     candidate is never drafted here (no owner answered for it).
   - `admit` keeps `if chosen and not tracker.ticket(current, item)`; with the owner's none
     `chosen` is truthy and is recorded, `tracker.ticket` returns None for it.

### cli/wuwei/guards/protect_state.py

1. `_OWNER_ACTIONS`:
   - Add `('tracker', 'create')`: "Item tickets are the planner's (#636): a seat hands the item
     back to the planner, which proposes the ticket on the item's card and opens it on the
     owner's answer. A seat opens a linked bug with bin/wuwei tracker create --bug <item>
     \"<title>\" --evidence <file:line>. Under strict the owner runs bin/wuwei tracker create
     <item> in a host terminal."
   - `('plan', 'set')`: replace the ticket sentence with "To link an existing ticket, the
     planner runs bin/wuwei plan set <item> ticket=<id> after the owner's card answer; under
     strict the owner runs it in a host terminal." Drop "a seat runs bin/wuwei tracker create
     <item>". Update the comment above it.
2. Two literal-shape predicates next to `_seat_docs_set`, same no-dynamic-word rule
   (`[$`*?\[{]`):
   - `_seat_class_create(action)`: `action[:2] == ['tracker', 'create']` and exactly one of
     `--bug`, `--triage`, `--follow-up` among the words before the first `--`. A class create
     stays a seat command (charters `_common.md` rule 7). `tracker create A -- --bug` does not
     match (the flag is after `--`, so argparse reads it as the title of an item create).
   - `_planner_ticket(action)`: exactly `['tracker', 'create', <item>]` or
     `['plan', 'set', <item>, 'ticket=<id>']`, the item not starting with `-`. The id is
     validated by the CLI (`plan.TICKET`); the hook does not import `plan`.
3. `_owner_action`, at the owner-table branch:
   - `if (reason := _owner_reason((group, verb))) and not (not xargs and (_seat_docs_set(action)
     or _seat_class_create(action))):`
   - next to the pace rule: `if not xargs and _planner_ticket(action) and edits[1] and not
     _strict(cwd): continue`.
   Adding `tracker` and `create` to the owner table widens `_owner_relevant` (`_OWNER_GROUPS`,
   `_OWNER_VERBS`); run `tests/test_protect_state.py` and `tests/test_invariants.py` (I10:
   no opaque read refused) to confirm no read becomes relevant-and-refused.

### Charters, agents and docs

- `charters/lead.md` (version 1.5.0 to 1.6.0), step 3 after "Verify the work is still open,
  deduplicate against tracker and day items": "With a tracker set and `tracker.required` on,
  give each candidate the open ticket that is its work as `ticket` (same workstream, same
  title words, from the backlog you queried); leave `ticket` out and the gate opens a new one
  from the item's record. `"ticket": null` is only the owner's none from Change something."
- `charters/planner.md` (2.0.0 to 2.1.0): rule 2 names tickets among the Change something
  questions (a different ticket or none goes back into the lead JSON, then propose again).
  Rule 3: replace the last sentence with "Approve opens the tickets the plan proposed. An
  owner-named item without a ticket gets a ticket draft from `plan add`; show its Send card.
  When an item still has no ticket after its card, run `bin/wuwei tracker create <item>` or
  `bin/wuwei plan set <item> ticket=<id>`; under strict the owner runs them." Keep the
  literal `bin/wuwei tracker create <item>` (`tests/test_charters.py` line 214).
- Regenerate `agents/*.md` with `bin/wuwei agents build` (repository root), then `bin/wuwei
  agents check`.
- `docs/site/concepts.md` "Tickets and comments": the plan shows each item's ticket, Approve
  links and opens them below strict, a seat never opens an item ticket, strict prints the
  commands.
- `docs/site/configuration.md` row `tracker.required`: the refusal names the item's card
  below strict and the host terminal commands under strict.
- `docs/site/reference.md` rows `bin/wuwei plan` and `bin/wuwei tracker`: `set <item>
  ticket=<id>` and `create <item>` are the planner's below strict.
- `docs/site/daily.md` line 355: the loop stops with the line naming the item's card.
- `cli/wuwei/commands/event.py` line 74 producer text for `tracker.created`:
  `wuwei tracker create, wuwei drafts approve or wuwei plan approve`.

### tests/test_invariants.py and design 9.2

I36: "An item ticket is attached by the planner below strict or by the owner, never by a
seat: `tracker create <item>` and `plan set <item> ticket=<id>` through `protect_state` pass
for the registered planner below strict and never for a seat, whose reason names the planner;
`tracker create --bug` stays a seat command". `i36` reads the posture (`READS['I36'] = (0,)`)
and models `i16`'s `setter`: `rules.configure(case[0])`, then `check_bash` of
`rules.bash(command)` and of `{**call, 'agent_id': 'seat-1'}` for both commands; the planner
passes iff not strict, the seat never passes and its reason contains `planner`; a seat's
`bin/wuwei tracker create --bug A "Broken" --evidence cli/x.py:1` passes. Add the 9.2 row
after I35 (`test_table_matches_the_checks` reads it), `READS['I36']`, `INVARIANTS['I36']`.
Renumber if another branch took I36 first. Design spec: the 9.2 row only; 5.11 text is raised
in the PR (spec, Design spec conflict).

## What must not change

- `outward.classify`, `tracker.auto` and its default, `drafts.approve` (strict host confirm,
  lint, claim), `drafts.hold`.
- `tracker.create` class creates, idempotency, the absolute-path refusal, `tracker.record`,
  `tracker.log`.
- `plan.set_ticket`: the adapter `created` confirmation stays.
- The gate card: one question, the same options and record command; no second card.
- Candidate tickets recorded without confirmation (design 5.11), import-yesterday carry.
- `protect_state`: `_seat_docs_set`, `_planner_pace_set`, the gate edits (`_GATE_EDITS`) and
  their rules; `outbound learn`.
- `discovery.intake` routing: a discovery candidate without a ticket still becomes an owner
  proposal with the reason (now the card wording).

## Tests to update (old wording or old default)

- `tests/test_tracker.py`: `MISSING` and the pending reason become posture-aware; the
  `config()` helper gains `guards` and `security` keys so `workspace.posture` reads it.
- `tests/test_plan.py` `test_approve_refuses_every_candidate_without_a_ticket`: run it under
  `strict` (it would otherwise reach the real Linear adapter).
- `tests/test_dispatch.py` lines 1457 and 1513: the guarded reason names the card; assert
  the card wording, or set `strict` where the test is about the commands.
- `tests/test_intraday_intake.py` line 238 (reason wording) and
  `test_owner_named_item_needs_a_ticket_when_a_tracker_is_set` (line 283): under guarded the
  owner item now gets a draft; run that test under `strict` and add the guarded case with the
  fake port (tasks).
- `tests/test_agent_launch.py` line 607 asserts only `X has no ticket`; unchanged.
