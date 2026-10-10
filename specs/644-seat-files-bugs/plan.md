# Implementation Plan: a bug a seat finds is filed by the seat

**Branch**: `644-seat-files-bugs` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The tier table, the umbrella and the draft card already exist. A seat's bug ticket never
reaches them: the port path exempts every tracker write from the umbrella and gives the
tracker a `team` party no row matches, so `tracker.auto` drafts it. This feature marks WUWEI's
own class creation on a non-external tracker as internal in `outward.classify` (one flag),
gives it an `owner` party when nobody else reads it (so an owner row `tool = "tracker",
audience = "owner"` matches), lets the umbrella decide it, and rewords the held reason in
`tracker.create`. A `--seat` label goes on the `tracker.created` event; the board and the
retro show it. The brief and `_common.md` say the finder files.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, config key, event kind, port
operation, tier row or guard. `DEFAULT_TIERS`, `table()`, `protect_state`, `drafts.approve`,
`tracker.check`, `tracker.log` and `plan.py` do not change.

## Constitution Check

- I stdlib: no new import.
- II exits: block is exit 1 with the existing `outward: ...; the owner decides: bin/wuwei
  outbound tiers` reason; an invalid `--seat` is argparse exit 2.
- III one behaviour one function: "is this tracker write internal" lives in
  `outward.classify` (the one tier decision); "print a held ticket" lives in `tracker.create`.
- IV test first: tasks.md orders a failing test before each change.
- V simplicity: no class key on `repos`, no new default row (rule numbers in 48 test lines
  and the docs stay put), no seat detection, no new card.
- VII security: a narrowing of nothing; a widening only for WUWEI's own port creation of a
  class ticket on a non-external tracker. The owner's rows still win, the sensitive row still
  holds, client trackers and client mentions still hold, strict still refuses client sends.
  `--seat` is a label nothing trusts. Adds 9.2 row I55 with its check.

## Design

### cli/wuwei/outward.py

`_parties` (line 473): add a keyword `own=False`. The fallback at lines 539 to 540 becomes:

```python
    if not parties and own:  # #644: WUWEI's own bug, triage or follow-up ticket, nobody else named
        place(connector, 'owner', "the workspace tracker is the owner's own")
        parties[connector.casefold()]['own'] = True
    elif not parties:
        place(connector, *_default(config, kind, tool, DEFAULT_CLASS))
```

`decide` (line 553), in the row loop before the strict branch at line 568:

```python
            elif party.get('own') and source == 'default' and row['tier'] == 'send':
                outcome = "passed: the umbrella decides the owner's own tracker"  # #644
```

(`_matches` must be true for this branch to be reached; keep the order: not matching ->
`passed`, then this, then strict, then match.)

`classify`, after the nested draft is flattened (line 628) and `rules` is read (line 629):

```python
        # #644: WUWEI's own class ticket in a tracker that is not external is internal.
        own = (port and kind == 'tracker' and context.get('category') in config['tracker']['create']
               and not _external_tracker(config))
```

Pass `own=own` to `_parties` (line 644). The umbrella condition at line 664 becomes:

```python
        if (own or not (port and kind in ('docs', 'tracker'))) and rules['default_tier'] != 'ask':
```

and its comment gains "and WUWEI's own class tickets in the owner's tracker (#644)". Under
`ask` the existing tracker kind rule (lines 676 to 680) holds it unless the class is in
`tracker.auto`. Only the port sets `category` (MCP payloads cannot claim it: `port` is
false), so the flag cannot be forged by a seat's connector call.

What this gives (no other path changes):

| Case | Parties | Decision |
| --- | --- | --- |
| send umbrella, no row | tracker (owner, own) | default send rows passed, none else match, umbrella send |
| ask umbrella | same | kind rule: draft unless the class is in `tracker.auto` |
| block umbrella | same | `block by outbound.default_tier: no narrower row matched` |
| owner row tool=tracker audience=owner tier=ask | same | `ask by rule 1 (tool=tracker audience=owner) for tracker: the workspace tracker is the owner's own` |
| sensitive title | same | default `topic = "sensitive"` ask row |
| external GitHub tracker | board (client) | client ask row, as today (`own` false) |
| a comment or an item ticket | tracker (team) | unchanged |

### cli/wuwei/tracker.py

`create` gains `seat=None` and passes it to `record`. Both held messages (lines 125 to 127,
the queued path, and 139 to 141, the fresh hold) go through one local helper:

```python
def _held(root, config, subject, draft_id):
    """#644: a held ticket is the planner's card below strict, a host-terminal approve under strict."""
    from wuwei import drafts, outward
    rule = drafts.read(state.read_state(root))[draft_id]['tier_reason'].removeprefix(
        outward.APPROVAL_REQUIRED + ': ')
    if workspace.posture(config)[0] == 'strict':
        return (f'{subject}: ticket held ({rule}): the owner runs bin/wuwei drafts approve '
                f'{draft_id} in a host terminal')
    return (f'{subject}: ticket held ({rule}): the planner asks it on its card '
            f'(bin/wuwei drafts show {draft_id} --widget)')
```

The `Result(1, {'draft': id}, ...)` shape stays, so `plan.approve` and `plan.add` (#636) are
unaffected. `record` (line 290) gains `seat=None` and adds `**({'seat': seat} if seat else
{})` to the `tracker.created` payload; `drafts.approve` and `plan approve` call it without.

### cli/wuwei/commands/tracker.py

`create.add_argument('--seat', choices=('builder', 'sentinel-arch', 'sentinel-goal',
'sentinel-quality', 'sentinel-security'), help='Your seat role, recorded on the event')`, and
pass `seat=args.seat` to `tracker.create`.

### cli/wuwei/commands/board.py

Lines 153 to 155: `('Class', 'Subject', 'Ticket', 'Parent', 'Seat')` and
`row.get('seat') or 'none'`.

### cli/wuwei/retro.py

After the Cycle section (line 100), from the same `watch.records(day / 'events.jsonl')`
reader the function already uses:

```python
    filed = [row['payload'] for row in watch.records(day / 'events.jsonl')
             if row['kind'] == 'tracker.created' and row['payload'].get('seat')]
    lines += ['', '## Tickets seats filed', '| Ticket | Class | Item | Seat |', '| --- | --- | --- | --- |',
              *([f"| {p['ticket']} | {p['class']} | {p['subject']} | {p['seat']} |" for p in filed]
                or ['| none | | | |'])]
```

### cli/wuwei/commands/outbound.py

The umbrella line at lines 84 to 85 reads "for chat, code host, mail and other, and bug,
triage and follow-up tickets in the workspace's own tracker".

### cli/wuwei/brief.py

Line 478: `f'Verdict file: {verdict} (the only file you write; an out-of-scope bug you find you
file yourself with bin/wuwei tracker create --bug, common rule 7). Include the retro note
here.'`

### charters/_common.md (then `bin/wuwei agents build`)

- Version 1.8.0 to 1.9.0.
- Rule 1: "A sentinel writes one verdict at the briefed path and files the out-of-scope bugs
  it finds (rule 7)."
- Rule 7: the command gains `--seat <your role>`; add "The finder files it in the owner's
  tracker directly. When it is held, the reason names the rule and the planner's card: note
  the ticket or the hold in your report and go on; never ask the owner." Keep `tracker create
  --bug` only in `_common.md` (`tests/test_charters.py` line 212).

### Design spec and invariants

- `docs/specs/2026-09-24-wuwei-design.md` 9.2: add I55 after I42: "A bug, triage or
  follow-up ticket WUWEI opens in the workspace's own tracker follows the owner's tier rows,
  then the sensitive row, then the umbrella: it sends under send and is held as a card under
  ask, in every posture; an external tracker or a client mention holds it" | "per posture,
  audience and umbrella, `classify` on an adapter write with category `bugs`" | "#644". Add
  "class tickets in the owner's tracker: I55 (#644)" to I7's Notes.
- `tests/test_invariants.py`: `i7` held case uses `('page', 'decisions')`; new `i55` over
  `OUTWARD` (kind `tracker`, mode `adapter`, topic `none`): audience `owner` gives `send`
  under the send umbrella and `draft` under ask; audience `client` gives `draft` under both.
  Register it in `INVARIANTS` and `READS`.

### Docs

- `docs/site/configuration.md`: `outbound.default_tier` row (the umbrella also decides
  WUWEI's bug, triage and follow-up tickets in the workspace's own tracker), `tracker.auto`
  row (those classes follow the umbrella unless the tracker is external), `tracker.create`
  row (`--seat`).
- `docs/site/concepts.md` "Tickets and comments": the finder files, sent under the send
  umbrella, a row `{ tool = "tracker", audience = "owner", tier = "ask" }` makes it a card;
  the board and the retro list who filed it.
- `docs/site/reference.md` tracker row: `--seat <role>`.

## Must not change

- `DEFAULT_TIERS`, `BROAD_ROWS`, `table()` and every rule number.
- Item tickets (`category == 'items'`, #636), `tracker.log` comments, `tracker.check`.
- MCP tracker writes (`port` false) and external trackers.
- `protect_state` (it already passes `tracker create --bug` from a seat, extra flags
  included).
- The `Result` data of a held `tracker.create`.

## Files

`cli/wuwei/outward.py`, `cli/wuwei/tracker.py`, `cli/wuwei/commands/tracker.py`,
`cli/wuwei/commands/board.py`, `cli/wuwei/retro.py`, `cli/wuwei/commands/outbound.py`,
`cli/wuwei/brief.py`, `charters/_common.md`, `agents/*.md` (generated),
`docs/specs/2026-09-24-wuwei-design.md`, `docs/site/configuration.md`,
`docs/site/concepts.md`, `docs/site/reference.md`; tests in `tests/test_outward.py`,
`tests/test_tracker.py`, `tests/test_protect_state.py`, `tests/test_board_mcp.py`,
`tests/test_report_retro.py` (or `tests/test_retro.py`, whichever compiles the retro),
`tests/test_brief*.py`, `tests/test_charters.py`, `tests/test_outbound.py`,
`tests/test_invariants.py`.
