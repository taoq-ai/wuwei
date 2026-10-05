# Implementation Plan: a thread reply in a work channel sends when the thread's participants are known people

**Branch**: `526-thread-reply` | **Spec**: `specs/526-thread-reply/spec.md`

## Summary

A chat thread reply becomes a table decision. `classify` adds the topic `thread` and
`_parties` adds the thread's participants (recorded today by `outbound learn --thread`) as
person parties, or one "not learned" party when nothing is recorded. One default row,
`{ audience = "team", topic = "thread", tier = "send" }`, sends a thread whose readers are all
team; the existing rows decide everything else (owner sends, client and public ask, company
asks under `ask` only). `outbound learn` gains `--thread <file>`, which records the
participants and puts the unknown ones on the existing learn card. The draft card's Always
option adds `{ channel, topic = "thread", tier = "send" }`. The hook prints
`posture: outward = block; a draft is one card away` under a held draft.

## Technical Context

Python 3.11+, stdlib only. No new module, no new dependency. The hook path reads state once
more, only for a chat call with a thread and one destination (`state` is imported lazily, as
`classify` already does for the review gate).

Files changed:

- `cli/wuwei/workspace.py`: `TOPICS` + `'thread'`; `CONFIG_CACHE_VERSION` 12 to 13.
- `cli/wuwei/outward.py`: `DEFAULT_TIERS` (one row), `_person` (one keyword), `_parties` (one
  keyword, the thread parties), `classify` (the thread topic and the record lookup).
- `cli/wuwei/drafts.py`: `always_row` (thread branch), `widget` (the Always text for a thread
  row).
- `cli/wuwei/commands/hook.py`: `posture` (the draft line).
- `cli/wuwei/commands/outbound.py`: `register` (`--thread`), `_rows` (split out the validator),
  new `_thread(path)`, `propose` (participants), `learn` (record step).
- `cli/wuwei/state.py`: `STATE_PRODUCERS['outbound_threads']`.
- `cli/wuwei/commands/event.py`: `EVENT_PRODUCERS['outbound.thread']`.
- `cli/wuwei/signal.py`: `outbound.thread` is a silent kind, like `outbound.learned` (found by
  `tests/test_signal_status.py` during implementation).
- Docs: `docs/site/concepts.md`, `docs/site/security.md`, `docs/site/reference.md`,
  `docs/site/configuration.md`, `templates/workspace/config.toml`,
  `skills/wuwei-plan/SKILL.md`.
- Tests: `tests/test_outward.py`, `tests/test_outbound_learn.py`, `tests/test_drafts.py`,
  `tests/test_outbound.py` (rule numbers in the tiers printout, if pinned).

## Constitution Check

- I stdlib only: yes.
- II exits: `learn --thread` exits 2 on an unreadable file, 1 on a malformed one (naming the
  shape), 0 after recording; `classify` keeps its error mapping (any `ValueError`,
  `KeyError` or `OSError` from the state read is `UNRUN`, a draft).
- III one behaviour, one function: participants are classed only by `_person`; the decision is
  only `decide` over `table`; the record is written only by `learn`.
- IV test first: tasks.md orders every test before its implementation.
- V ponytail: one row, one topic, one state key, one CLI flag; the learn card, `propose`,
  `apply`, `_person`, `decide` and `always_row` are reused. No new card type and no new
  command. The old thread kind rule stays (its only path left is a thread reply without
  exactly one channel).
- VII security: no new refusal under observe or guarded (SC-002). The record and its event are
  reserved to `wuwei outbound learn` (pre-flight "no forgeable trust"); a seat cannot write
  `state.json` (records floor). An unknown participant reaches `outbound.people` only through
  the card, or `learn = "auto"` outside strict, as #492's people do.

## Design

### 1. Topic and row (`workspace.py`, `outward.py`)

- `TOPICS = ('sensitive', 'commitment', 'disagreement', 'thread')`; bump
  `CONFIG_CACHE_VERSION`.
- `DEFAULT_TIERS`: insert `{'audience': 'team', 'topic': 'thread', 'tier': 'send'}` directly
  after `{'audience': 'company', 'tier': 'ask'}`. Rule numbers 1 to 9 do not move (existing
  reasons and tests keep `rule 9 (audience=company)` and `rule 7 (topic=commitment)`); the
  monitoring row moves from 10 to 11. Not in `BROAD_ROWS`.

### 2. `classify` (outward.py)

After the nested-draft merge and before `decide`:

```python
ts = next((str(context[key]) for key in ('thread_ts', 'thread') if context.get(key) is not None), None)
thread = None
if kind in ('chat', 'slack') and ts and len(set(destinations)) == 1:
    from wuwei import state
    thread = (ts, state.read_state(root).get('outbound_threads', {}).get(f'{destinations[0]}/{ts}'))
topics = _topics(normalized, rules)
if thread:
    topics['thread'] = f'thread {ts}'
```

Pass `thread` to `_parties` (new keyword `thread=None`). Nothing else in `classify` changes;
the kind rule at `outward.py:634-638` stays.

### 3. `_parties` and `_person` (outward.py)

- `_person(..., dm=False, what='mention')`: the non-DM unknown text becomes
  `f'unknown {what} {label}, not an internal person in outbound.people'` (unchanged for
  mentions).
- `_parties(..., thread=None)`: when `thread` is set, after the destinations loop:
  - recorded list: `add(_person(pid, 'slack', rules, mine, fallback, pid, what='thread participant'))`
    for each id;
  - `None` (not learned): `add({'id': f'{target}/{ts}', 'kind': 'channel', 'key':
    f'{target}/{ts}'.casefold(), 'names': {target.casefold()}, 'class': fallback[0], 'why':
    f'participants of thread {ts} not learned{learn}, {fallback[1]}'})` with `learn = f', run
    bin/wuwei outbound learn --tool {tool or "<tool>"} --thread <file>'` unless
    `rules['learn'] == 'off'`. Kind `channel` and `names = {target}` let an owner row
    `{ channel = target, ... }` match it; the distinct key keeps it apart from the channel
    party. Evidence holds no `; `.

Result per reader (shipped rows): owner sends (rule 1); public and client ask (2 to 5);
sensitive text asks (6); team sends by the thread row (10); company and unknown (connector
default company) ask by rule 9 under `ask`, and match nothing under `send`, so the umbrella
sends (as on main). A connector whose `outward.classes` is `team` makes unknown readers team,
the owner's own choice.

### 4. `outbound learn --thread` (commands/outbound.py)

- `register`: `learn_parser.add_argument('--thread', metavar='FILE', help="JSON {channel,
  thread_ts, participants} from the connector's replies tool (slack only)")`.
- `_rows(path, kind)`: move the per-row validation into `_listing(rows, kind, problem)` so
  `_rows` reads and calls it. New `_thread(path)`: read (OSError propagates), `json.loads`, the
  object must have exactly `channel` (`[A-Z0-9]+`), `thread_ts` (`\d+\.\d+`) and
  `participants`; `_listing(found['participants'], 'people', problem)`; returns
  `(channel, ts, participants)`. The problem text names the shape and says "write the file
  again".
- `learn`: after `channel` is resolved and before the `open_card` check:

  ```python
  if args.thread:
      if channel != 'slack': fail('listings apply to a slack connector; ...')   # same text as today
      try: target, ts, participants = _thread(args.thread)
      except OSError: exit 2 "cannot read a listing ..."; except ValueError: exit 1
      state._write_state(lambda data: data.setdefault('outbound_threads', {}).__setitem__(
          f'{target}/{ts}', [row['id'] for row in participants]), root, reserved=False,
          kind='outbound.thread', payload={'thread': f'{target}/{ts}', 'participants': len(participants)})
      known = {key.casefold() for key in config['outbound']['people']}
      mine = <outbound.owner.slack.user casefolded>
      unknown = [row for row in participants if f"slack:{row['id']}".casefold() not in known
                 and row['id'].casefold() != mine]
      if not (unknown or args.channels or args.people or args.owner):
          print(f'outbound learn: recorded {len(participants)} participants of thread {target}/{ts}; send the reply again')
          return CLEAN
  ```

  Then the existing flow. The "needs its listings" check accepts `args.thread` as a listing.
  `propose(..., participants=unknown, thread=ts)`.
- `propose`: after the people loop, for each participant (skip ids already in `new_people`):
  class `team` when the email domain is in `company_domains`; `client` when there is an email
  and `company_domains` is non-empty; else `company`. Entry `{'email': email, 'class': cls}`
  (no `email` key when empty); `why = f'in thread {ts}'`. The card (`record`), its per-entry
  other-class option (`_other_class`: company or client to team, team to company) and
  `apply` are unchanged.

### 5. Draft card (drafts.py)

- `always_row`: before the person branch, `if party.startswith(row['destination'] + '/'):
  return ("Always send in this channel's threads", {'channel': row['destination'], 'topic':
  'thread', 'tier': 'send'})`.
- `widget`: when the added row has `topic == 'thread'`, the option text is
  `later thread replies in <channel> go out without a card`.
- `_add_row` and `approve --always` are reused unchanged.

### 6. Posture line (commands/hook.py)

In `posture`, next to the `NO_REVIEWER` line override:

```python
if guard == 'outward' and reason.startswith('outward: draft '):
    line = f'posture: {area} = {decided}; a draft is one card away'
```

`level()`, `OWNER_ONLY` and the floor text for publish and security refusals do not change.

### 7. Reserved producers

- `state.STATE_PRODUCERS['outbound_threads'] = 'wuwei outbound learn'`.
- `event.EVENT_PRODUCERS['outbound.thread'] = 'wuwei outbound learn'`.

### 8. Docs

- `concepts.md` (outbound tiers): the thread row in the defaults list; a thread reply's
  readers are its participants, learned by the planner with `outbound learn --thread`; the
  `ask` kind-rule sentence no longer says chat threads draft.
- `security.md` (learn paragraph): `--thread <file>` and what it records and proposes.
- `reference.md:370`: a held draft's line is `posture: outward = block; a draft is one card
  away`.
- `configuration.md:395`: topic list adds `thread`.
- `templates/workspace/config.toml:202-205`: topic list adds `thread`; the threads comment says
  a thread reply's participants come from `outbound learn --thread`.
- `skills/wuwei-plan/SKILL.md` (Unknown connectors paragraph): when a reason names
  `outbound learn --tool <tool> --thread <file>`, call the connector's replies tool
  (`conversations_replies` or `slack_read_thread`), write `{"channel", "thread_ts",
  "participants": [{"id", "name", "email"}]}` under today's day directory, run the command,
  ask the printed widget if any, then send the reply again.

## What must not change

- Rule numbers 1 to 9 of the default table, `BROAD_ROWS`, and the `send` umbrella's behaviour
  for a thread with no client, public or sensitive reader.
- `level()`, `OWNER_ONLY`, and the publish and records floor lines.
- `_person` texts for mentions and DM recipients; `record`, `apply` and the card options of
  `outbound learn`.
- Code-host `thread` fields (review thread ids) never become a chat thread.
- `drafts.spend` and the one-shot allowance.

## Complexity Tracking

None.
