# Implementation Plan: one ticket id format

**Branch**: `741-one-ticket-format` | **Date**: 2026-10-10 | **Spec**: `specs/741-one-ticket-format/spec.md`

## Summary

One function in the tracker core, `tracker.full_id(config, ticket)`, turns a bare GitHub issue
number into `<tracker repository>#<n>` and refuses it when no tracker repository can be named.
The three places a ticket id enters the plan call it (`plan add`, `plan set ticket=`,
`plan propose`), so `tickets` in `state.json` only ever holds the full form and the adapter's
`claim` (unchanged) accepts it. `drafts approve` prints the id of a ticket a sent draft
opened. `init --upgrade` runs the same function once over the latest day's stored tickets.
No adapter, guard, schema or event-kind change.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest, in process; fakes for the tracker (`tests/fakes/tracker.py`,
`registry.load` monkeypatched), no network
**Constraints**: exits 0/1/2; a refusal is a `ValueError` (exit 2) with the fix named; no
em-dashes, no emojis, no absolute paths

## Constitution Check

- I stdlib only: `re` only. Pass.
- II fail closed: an unnameable repository refuses with exit 2 and the fix; the upgrade pass
  prints instead of failing because it decides nothing else (as the graph register, A13). Pass.
- III one behaviour, one function: normalisation lives only in `tracker.full_id`; every entry
  point calls it. Pass.
- IV test first: every task pair below is test then code. Pass.
- V ponytail: one ~10-line function plus one call per entry point, one string change, one
  upgrade loop reusing `watch.days` and `state._write_state`. Item code repository lookup,
  Linear/Jira completion and history rewriting are not built (spec Assumptions). Pass.
- VII security: no guard changes; the planner rule of #636 is pinned by a regression test.
  Pass.
- Workflow: no guard or decision rule changes, so no new invariant row.

## Design

### The shared helper (new, the only new function besides the upgrade loop)

`cli/wuwei/tracker.py`, next to `ticket()`:

```python
def full_id(config, ticket):
    """#741: a bare GitHub issue number becomes <tracker repository>#<n> (design 5.11:
    tracker.project, else the first configured repository); every other id is kept."""
    if config['adapters']['tracker'] != 'github' or not re.fullmatch(r'[1-9][0-9]*', str(ticket)):
        return ticket
    repo = config['tracker']['project'] or next((row['name'] for row in config['repos']), '')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
        raise ValueError(f'ticket {ticket} names no repository; pass owner/repo#{ticket}, or the '
                         'owner sets tracker.project to the GitHub owner/repo with bin/wuwei '
                         'config set tracker.project <owner/repo> in a host terminal')
    return f'{repo}#{ticket}'
```

The repository expression and the `owner/repo` regex are the ones `github._repo`
(`adapters/tracker/github.py:87`) and `outward._external_tracker` (`cli/wuwei/outward.py:360`)
already use. Do not refactor those two callers onto the helper in this feature (they return
different things and live in the adapter layer); the regex stays identical so the three agree.

### Entry points (one call each)

1. `plan.add` (`cli/wuwei/plan.py:471`): right after `from wuwei import tracker` and before
   `chosen = proposed(candidate)` (around line 507), normalise a candidate that carries a
   ticket, for owner and discovery candidates alike:

   ```python
   if candidate.get('ticket'):  # #741: one id format, before anything is written
       candidate = {**candidate, 'ticket': tracker.full_id(config, candidate['ticket'])}
   ```

   A refusal raises before `tracker.create`, the `plan.proposed` write and `admit`.
2. `plan.set_ticket` (`cli/wuwei/plan.py:643`): after the `TICKET` regex check, add
   `ticket = tracker.full_id(workspace.load_config(root), ticket)` (load the config once and
   reuse it for `registry.load` below), then confirm with `created(ticket)` and store the
   normalised id as today. Return `ticket`.
3. `commands/plan.py` `set` branch (`cli/wuwei/commands/plan.py:94-96`): print
   `f'{args.item}: ticket {plan.set_ticket(args.item, value)}'`, so the printed id is the
   stored one.
4. `plan.propose` (`cli/wuwei/plan.py:205`): right after `data = _proposal(data, goals_text,
   framework)` (line 240), where `config` is already loaded:

   ```python
   for row in data['candidates']:  # #741: the lead's tickets, in the one id format
       if row.get('ticket'):
           row['ticket'] = tracker.full_id(config, row['ticket'])
   ```

   (`from wuwei import tracker` locally, as the module does elsewhere.) `proposal.json`, the
   gate text (`_tickets`) and `approve` then all see the full id.

### The printed id of a sent draft

`drafts.approve` (`cli/wuwei/drafts.py:386`): the final `Result` reason becomes
`f'drafts: {draft_id} sent; ticket {result.data["id"]} {result.data["url"]}'` when the row is
a tracker `create` that succeeded and was recorded (the block at line 373 already handles that
case; only the reason string changes). Every other draft keeps `drafts: <id> sent`.
`tracker.create`'s direct path already prints `<item>: ticket <id> <url>`
(`cli/wuwei/tracker.py:143`); unchanged.

### The init --upgrade pass

`cli/wuwei/tracker.py`, below `full_id`:

```python
def upgrade(root, config, write=True):
    """#741, once: the latest day's bare GitHub ticket ids become <repo>#<n>; the lines say what
    changed (or why an id stays). Earlier days are history and are not rewritten."""
```

- Return `[]` unless `config['adapters']['tracker'] == 'github'`.
- Latest day: the first of `watch.days(root)` (`cli/wuwei/watch.py:55`, newest first, date
  directories up to today) that has a `state.json`; none means `[]`.
- Read it with `state.read_state(directory=day)`; an error (`OSError`, `ValueError`,
  `state.StateError`) returns one line `<day>/state.json: tickets unread: <reason>` and nothing
  is written.
- For each `item, row` in `tickets` whose `id` is a string matching `[1-9][0-9]*`: call
  `full_id`; a `ValueError` adds `<day>/state.json: ticket <item> <id> unchanged: <reason>`;
  otherwise, when `write`, `state._write_state(update, root, reserved=False, kind='plan.set',
  payload={'item': item, 'ticket': new, 'was': old}, directory=day)` where `update` sets
  `data['tickets'][item]['id'] = new` only if it still equals `old`; the line is
  `<day>/state.json: ticket <item> <old> to <new>`.

`cli/wuwei/commands/init.py` `upgrade()`: after `seeded = novelty.seed(...)` (line 397), call
`changed = tracker.upgrade(destination.parent, workspace.load_config(destination.parent,
raw=migrated), write=not args.dry_run)` and print each line as `f'{prefix} {line}'` next to
the other `prefix` lines; add `and not changed` to the "No workspace changes needed"
condition (line 446). Lines that report an id left unchanged or an unread state also print
with the prefix; they count as output, which is acceptable (rare, and they name the fix).
Keep it in the existing `try`, so nothing new can turn the upgrade into exit 2: `upgrade`
catches its own read errors.

`cli/wuwei/commands/event.py:78`: the `plan.set` producer becomes
`'wuwei plan set or wuwei init --upgrade'`.

### What must not change

- `adapters/tracker/github.py`: `_ref` keeps refusing a bare number (the core never hands one
  over now); `claim`, `transition`, `comment` unchanged.
- `TICKET` (`plan.py:14`) and the `_proposal` validation: the shape check stays; normalisation
  is a separate step after it.
- `proposed()`, `tracker.check`, `tracker.record`, `dispatch.tracker_call`: unchanged.
- Linear, Jira and `none` trackers: every id passes through `full_id` unchanged.
- `protect_state._planner_ticket`: unchanged; only a regression test is added.
- The design spec: not amended (owner only; 5.11 already says it).

## Project Structure

### Documentation (this feature)

```text
specs/741-one-ticket-format/
├── spec.md
├── plan.md
└── tasks.md
```

No research.md, data-model.md, contracts/ or quickstart.md: the spec's root cause holds the
research, the record shape does not change, and there is no new interface beyond one function.

### Source Code (files touched)

```text
cli/wuwei/tracker.py           full_id, upgrade (new)
cli/wuwei/plan.py              add, set_ticket, propose: one full_id call each
cli/wuwei/commands/plan.py     set ticket= prints the stored id
cli/wuwei/drafts.py            approve: reason names the created ticket
cli/wuwei/commands/init.py     upgrade: calls tracker.upgrade, prints, counts the change
cli/wuwei/commands/event.py    plan.set producer text
tests/test_tracker.py          full_id table, upgrade unit
tests/test_intraday_intake.py  plan add with --ticket 24 (one repo, project, two repos, refusal)
tests/test_plan.py             plan set ticket=24; plan propose with a bare ticket
tests/test_drafts.py           sent tracker create draft prints the id
tests/test_workspace.py        init --upgrade end to end (change, dry run, idempotent)
tests/test_protect_state.py    planner plan set ticket=24 and ticket=acme/app#24 pass below strict
```

## Complexity Tracking

None. No new module, class, config key, event kind or adapter operation.
