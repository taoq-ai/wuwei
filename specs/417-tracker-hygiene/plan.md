# Implementation Plan: Tracker hygiene

**Branch**: `417-tracker-hygiene` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

One new core module, `cli/wuwei/tracker.py`, holds the rule (`check`), the one creator
(`create` and its writer `record`) and the one comment writer (`log`). Every refusal point
calls `check`; every creation, CLI or approved draft, records through `record`; every comment
goes through `log`. The existing tracker port gains `comment`; the outward policy gains one
`auto` branch for tracker writes; drafts gain `comment` and record approved creations. The
Linear adapter is extended; Jira and GitHub adapters are added on the shared `_http.request`,
which learns GET, PUT and empty bodies. Everything else is a one-line call site, config keys,
setup and interview rows, a doctor row, owner surfaces and docs. Design 5.11 and the
implementation map in `specs/416-tracker-hygiene-spec/plan.md` are the source; this plan pins
them to current `main`.

## Technical Context

Python 3.11 stdlib only (`urllib`, `json`, `base64`, `re`). Tests: pytest, no network
(recorded fixtures replayed by monkeypatching `urllib.request.urlopen`, as
`tests/test_reference_adapters.py:30` `replay` does; the fake port in `tests/fakes/tracker.py`
for core tests). Run with `python -m pytest -q` from the repository root.

## Constitution Check

- I (stdlib): urllib adapters; no new dependency.
- II (three-state): every port call returns `Result`; `tracker create`, `log`, `done` and `plan
  set` exit 0/1/2; an unreadable state or a port exit 2 is exit 2 with the reason.
- III (one behaviour, one function): `tracker.check` is the only ticket rule; `tracker.record`
  the only writer of `tickets` from a creation; `tracker.log` the only comment writer.
- IV (test first): tasks.md orders every test before its code.
- V (ponytail): no new port beyond `comment`; linking rides on `create`'s `parent`; templates are
  literals in `tracker.py`, not config; the fold is one comment; one shared HTTP helper.
- VII (security): every write still passes `outward.check_call`; `auto` only skips the draft for
  record-derived text after the sensitive, audience and external checks; new tokens are in
  `env.CREDENTIALS` so seats never see them; evidence with an absolute path is refused.
- Pre-flight: scope (refusals act only in a workspace: every caller already resolves the
  workspace, the launch guard through `guard_scope`); no forgeable trust (`tickets`,
  `tracker_log` are producer-owned state keys, new event kinds are reserved since only `note` is
  free in `commands/event.py:10`); no new hook import on the common path (`tracker.py` imports
  only `re`, `wuwei.state`, `wuwei.workspace` at top level; `profiles`, `registry`, `drafts`,
  `decision`, `verdict` are imported inside the functions that need them).

## Shared core: new `cli/wuwei/tracker.py`

```python
CLASSES = ('items', 'bugs', 'triage', 'follow-ups')
KINDS = ('decisions', 'progress', 'verdicts', 'pr', 'close')

def ticket(data, item): ...            # data.get('tickets', {}).get(item, {}).get('id')
def in_force(config): ...              # adapters.tracker != 'none' and tracker.required
def check(data, config, item, row=None): ...   # -> (status, reason), pure
def pending(data, item): ...           # pending items draft id for item, else None
def create(root, subject, category='items', title=None, evidence=()): ...  # -> Result
def record(draft, created, *, root=None, directory=None): ...   # tickets + log + event
def log(root): ...                     # -> exit code
def done(root, item): ...              # dispatch.tracker_call(item, 'done', root)
```

`check(data, config, item, row)`:

- `off` when `not in_force(config)`; `ticket` when `ticket(data, item)`;
- tier = `(row or {}).get('gates', {}).get('tier') or (row or {}).get('tier')`; `skipped` when
  tier is in `config['tracker']['skip_tiers']`;
- else `missing` with the reason, exactly:
  `f"{item} has no ticket: bin/wuwei tracker create {item} (opens one from the item's record) or bin/wuwei plan set {item} ticket=<id>"`,
  or, when `pending(data, item)` returns a draft id,
  `f"{item} has no ticket: bin/wuwei drafts approve {draft}"`.
- `pending` reads `data.get('drafts', {})` directly (no `drafts` import): a row with
  `status == 'pending'`, `channel == 'tracker'`, `operation == 'create'` and
  `inputs['draft']` having `category == 'items'` and `item == item`.

`create(root, subject, category, title, evidence)`:

1. `config = workspace.load_config(root)`; adapter `none` returns `Result(2, reason='tracker
   adapter is none')`. `category` not in `CLASSES` is exit 2; `category != 'items'` and not in
   `config['tracker']['create']` is exit 1 `tracker.create: <class> is not in tracker.create`.
2. `items`: `ticket(data, subject)` already recorded prints it and returns exit 0. The record:
   the candidate from today's `proposal.json` `candidates`, else `data['discovery_candidates']`;
   none is exit 2 `unknown item <subject>`. Title = candidate `scope` (whitespace collapsed),
   description = `Evidence: <evidence>`, `Goal: <goal or unplanned>`, `Track: <track>` lines.
   Other classes: `title` is required; description = the evidence lines; `parent =
   ticket(data, subject)`.
3. Refuse (exit 1, writes nothing) when the title or any description line matches
   `profiles.ABSOLUTE`.
4. Idempotency: key `f'create:{category}:{subject}:{" ".join(title.lower().split())}'`; a
   `tracker_log` entry for it, or a pending or sent tracker draft whose `inputs['draft']` equals
   the draft, prints the ticket or draft and returns exit 0 (ticket) or 1 (draft), writing
   nothing.
5. `draft = {'title', 'description', 'item': subject, 'category': category, 'parent': parent}`
   (`parent` omitted when None); `result = registry.load('tracker', config).create(draft,
   root=root)`.
6. Exit 0: `record(draft, result.data, root=root)`. Exit 1 with `stored draft <id>` in the
   reason: write `tracker_log[key] = {'outcome': 'drafted', 'draft': <id>, ...}`. Other exit 1:
   `{'outcome': 'refused', 'reason': ...}`. Exit 2: write nothing. Return the result.

`record(draft, created, root=None, directory=None)`: validates `created` is `{'id': str, 'url':
str}`, then one `state._write_state(..., reserved=False, kind='tracker.created', payload={'class',
'subject', 'ticket', 'parent'})` that sets `tickets[subject] = {'id', 'source': 'create'}` when
the class is `items` and `tracker_log[key] = {'outcome': 'written', 'ticket': id}`. Called by
`create` and by `drafts.approve`.

`log(root)`:

- Off (`adapters.tracker == 'none'`): return 0. Reads today's state and events
  (`watch.records(day / 'events.jsonl')`, line number `n` from 1).
- Builds entries `(key, item, kind, text)` for kinds in `config['tracker']['log']`, only for items
  with `ticket(data, item)`; key = `f'{kind}:{item}:{n}'` (plus `:<suffix>` when one event gives
  one item two entries). Text = `f'[{day.name} {item}] ' + template`:

| Kind | Event (today) | Template |
|---|---|---|
| `decisions` | `decision.decided` whose `payload['item'] == item` or whose D-n names the item (`decision.naming(day, [item])`), and whose `item_disposition` does not start with `carried ` or `parked ` | `Decision {id}: {question} Outcome: {option}.` (`question` from `commands.why.question(day, id)`, ending in its own `?` or an added `.`) |
| `progress` | any event whose `payload['phase_changes'][item]` is not `merged` | `Phase: {phase}.` |
| `progress` | `seat launched` / `seat stopped` whose seat (`data['seats'][name]`) is the item's `builder` or `sentinel-<role>` | `Build started.`, `Build stopped.`, `Review {role} started.`, `Review {role} stopped.` |
| `progress` | `build.checked` with `passed` and `failed` in the payload | `Fast checks: {passed} passed, {failed} failed.` |
| `verdicts` | `gate.received` | `Review {role} ({round}): {verdict}, {n} blocking findings.` (`n` counts `findings` in `data['gate_verdicts'][f'{item}:{role}:{round}']` matching `verdict.BLOCKS_YES`) |
| `pr` | `pr.raised`, `pr.claimed` | `Pull request: {pr}.` |
| `close` | `phase_changes[item] == 'merged'` | `Merged in {items[item]['pr']}.` |
| `close` | `decision.decided` with `item_disposition` `carried <item>` / `parked <item>` | `Carried to {day + 1} ({id}).` / `Parked ({id}).` |

- Skips keys already in `tracker_log`. Per ticket: `used` = entries for that ticket with outcome
  `sending`, `written` or `drafted`; `allowed = cap - used`. When the new entries exceed
  `allowed`, the first `allowed - 1` go out singly and the rest become one fold `Folded {n}
  updates: {kind} {count}, ...` (kinds in table order) under the key `fold:{ticket}:{n of first}`,
  with one `state.append_event('tracker.folded', {'item', 'ticket', 'counts'})`; their own keys
  get `{'outcome': 'folded'}`. With `allowed <= 0` every new entry is recorded `folded` with no
  comment and no event.
- Each send: claim the key (`{'outcome': 'sending', 'ticket', 'kind'}`, refusing if present) in
  one `_write_state(kind='tracker.logged')`, call `port.comment(ticket, text, category)` where
  category is the kind (for a fold, the first folded kind not in `auto`, else the first kind),
  then settle: exit 0 `written`; exit 1 with `stored draft <id>` `drafted` and `draft`; other
  exit 1 `refused` and `reason`; exit 2 drops the claim (key removed) so the next run retries,
  and `log` returns 2. Returns 1 when this run refused an entry, else 0.

`done(root, item)`: `return dispatch.tracker_call(item, 'done', root)`.

## Call sites

| File | Function | Change |
|---|---|---|
| `cli/wuwei/plan.py` | `_proposal` (line 66 loop) | optional candidate `ticket`: a string matching `[A-Za-z0-9][A-Za-z0-9._/#-]{0,99}`, else `ValueError(f'{name}: invalid ticket')` |
| `cli/wuwei/plan.py` | `approve` (line 227 `update`) | per approved name: ticket = `tracker.ticket(current, name)` or candidate `ticket` (source `candidate`) or, when the name is in `data['discovered']` with `source == 'tracker'`, the name (source `tracker`); set it into `current['tickets']` before `tracker.check(current, config, name, candidates[name])`; collect every `missing` reason and raise one `state.StateError('\n'.join(reasons))` before any change; for `import_yesterday`, copy the prior day's `tickets` for imported names (source `yesterday`); after the write, one `state.append_event('tracker.skipped', {'item', 'tier'})` per `skipped` name |
| `cli/wuwei/plan.py` | `add` (line 300 `admit`) | same ticket choice from `candidate` (`source == 'tracker'` gives the id); `missing` raises `state.StateError(reason)` before the start decision; `tracker.skipped` after admission |
| `cli/wuwei/plan.py` | new `set_ticket(item, ticket, root=None)` | item must be in today's `items` or `proposal.json` candidates (else `StateError`); ticket must match the `_proposal` pattern; `registry.load('tracker', config).created(ticket, root=root)`: exit != 0 raises `OSError(reason)` (exit 2) or `StateError` (exit 1); writes `tickets[item] = {'id': ticket, 'source': 'set'}` with `kind='plan.set'` |
| `cli/wuwei/commands/plan.py` | `register`, `run` | verb `set` with `item` and `assignment` (`ticket=<id>`; any other key is exit 2 `plan set: only ticket=<id>`) |
| `cli/wuwei/commands/build.py` | `next_action` (before `_save`, line 139) | `status, reason = tracker.check(data, config, item, data['items'][item])`; `missing` raises `PortExit(1, reason)` |
| `cli/wuwei/commands/build.py` | `_save`, `complete_checks` (line 362) | `_save` takes `extra=None` merged into the event payload; `complete_checks` passes `{'passed': len(commands) - len(failures), 'failed': len(failures)}` |
| `cli/wuwei/dispatch.py` | `next_step` (after the tier block, line 180) | `tracker.check(data, config, item, row)`; `missing` raises `Refused(reason)` |
| `cli/wuwei/dispatch.py` | `tracker_call` (lines 117, 119) | `ticket = tracker.ticket(state.read_state(root), item) or item`; claim and transition use `ticket`; the event payload adds `'ticket': ticket` |
| `cli/wuwei/guards/agent_launch.py` | `_check`, inside `reserve` (before the seat row, line 184) | when `logged['item'] in data['items']`: lazy `from wuwei import tracker`; `missing` raises `brief.Refused(reason)` |
| `cli/wuwei/closing.py` | `unresolved` (in the approved-items loop, line 195) | while `tracker.in_force(config)`: for an item with `phase == 'merged'` and a ticket, no today's `tracker.call` event with `item == name`, `action == 'done'`, `exit == 0` gives the line `f'{name}: ticket {id} is not done: bin/wuwei tracker done {name}'`; `strict_close` appends it to findings, else prints it to stderr |
| `cli/wuwei/commands/close.py` | `run` (after `closing.check`, line 52) | when `code == 0`: `tracker.log(root)`; a nonzero exit prints `tracker log: ...` and leaves `code` |
| `cli/wuwei/watch.py` | `sweep` (after the steward block, line 302) | `tracker.log(root)` in its own `try`; exit 2 or an `ERRORS` exception adds to `unreadable` and `owed` and sets `exit` 2, printing `watch tracker log unmeasured` |
| `cli/wuwei/metrics.py` | `_references` (line 227) | key by `tracker.ticket(data, item) or item` |
| new `cli/wuwei/commands/tracker.py` | `register`, `run` | `tracker create <item>`, `tracker create --bug|--triage|--follow-up <subject> <title> --evidence <line> ...`, `tracker log`, `tracker done <item>`; print the ticket, draft or reason; return the exit |
| `cli/wuwei/commands/__init__.py` | `WRITES` | add `plan set`, `tracker create`, `tracker log`, `tracker done` |

## Config, state, events, env

- `cli/wuwei/workspace.py` `SCHEMA['tracker']` (line 74): `required (bool, True)`, `skip_tiers
  [(str, None, ('light', 'standard', 'full')), []]`, `strict_close (bool, True)`, `create [(str,
  None, ('bugs', 'triage', 'follow-ups')), [...]]`, `log [(str, None, KINDS), [...KINDS]]`,
  `auto [(str, None, (*CLASSES, *KINDS)), ['progress', 'pr', 'close']]`, `max_per_item_per_day
  (int, 10, 1)`, `project (str, '')`, `board (str, '')`. `adapters.tracker` unchanged.
- `templates/workspace/config.toml` `[tracker]`: the nine keys, commented, one line each; the
  `[outbound]` comment at line 165 ("tracker writes draft") says tracker writes in
  `tracker.auto` are sent.
- `cli/wuwei/commands/config.py` `requirements` (line 117): `('tracker', 'jira'): [('JIRA_SITE',),
  ('JIRA_EMAIL',), ('JIRA_API_TOKEN',)]`, `('tracker', 'github'): [('GITHUB_TRACKER_TOKEN',)]`.
- `cli/wuwei/env.py`: `CREDENTIALS` adds `JIRA_SITE`, `JIRA_EMAIL`, `JIRA_API_TOKEN`,
  `GITHUB_TRACKER_TOKEN`; `PUBLIC` adds `JIRA_SITE`.
- `cli/wuwei/state.py` `STATE_PRODUCERS`: `tickets` ('wuwei plan approve, add or set, wuwei
  tracker create or wuwei drafts approve'), `tracker_log` ('wuwei tracker create or log').
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `tracker.created`, `tracker.skipped`,
  `tracker.folded`, `tracker.logged`, `plan.set`.

## Port, outward, drafts

- `cli/wuwei/registry.py` `PARAMETERS['tracker']`: add `'comment': ('item', 'text', 'category')`.
- `cli/wuwei/outward.py`: `METADATA_FIELDS` adds `category` and `parent`. In `classify`, after
  the `recipient_org` check (line 335) and before `discussion = ''`:

  ```python
  if kind == 'tracker':
      return (CLEAN, 'send') if (context.get('category') in config['tracker']['auto']
                                 and not _external_tracker(config)) else (FINDINGS, 'draft')
  ```

  `_external_tracker(config)`: for `adapters.tracker == 'github'`, true when the owner of
  `tracker.project` (or the first repository's name) or of `tracker.board` is not in
  `outbound.code_host_orgs` (case-folded); false for other adapters.
- `cli/wuwei/drafts.py`: `OPERATIONS['tracker'] = {'create', 'comment'}`. In `approve`, after
  `finish`, when `row['channel'] == 'tracker' and row['operation'] == 'create' and result.exit
  == 0`: `tracker.record(inputs['draft'], result.data, directory=directory)` (an error there
  returns exit 2 `drafts: sent; could not record ticket`).

## HTTP helper and adapters

- `adapters/_http.py` `request(url, token, payload=None, *, method='POST', authorization='Bearer',
  extra_headers=None)`: `payload=None` sends no body; an empty response body returns `{}`. Every
  existing caller passes a payload and keeps POST. New `settings(root)`: `from wuwei import
  workspace; return workspace.load_config(workspace.find_workspace(root))` for adapters that
  read `[tracker]`.
- `adapters/tracker/none.py`: `comment(item, text, category, *, root=None)` decorated with
  `@outward_operation('tracker')`, `record_none(..., measurement=False)`.
- `adapters/tracker/linear.py`:
  - `create(draft)`: accepts the neutral draft; input `{teamId: project or backlog_filter, title,
    description, parentId}` where `parentId` is the parent's UUID (`issue(id:$parent){id}`);
    still accepts the existing Linear keys (`teamId`, `stateId`, `assigneeId`, `projectId`) for
    the current callers and tests; returns `{'id': identifier, 'url': url}` (the mutation
    selects `issue{id identifier url}`). Empty team is `Failure('tracker.project or
    backlog_filter must name a Linear team')`.
  - `comment(item, text, category)`: `issue(id:$id){id}` then `commentCreate(input:{issueId,
    body})`; returns `{'id': comment id}`. Decorated `@outward_operation('tracker')`.
- New `adapters/tracker/jira.py` (`JIRA_SITE` must start with `https://`; Basic auth
  `base64(email:token)`):
  - `backlog(filter)`: POST `/rest/api/3/search/jql` with `jql = f'project = "{project}" AND
    statusCategory != Done' + (f' AND ({filter})' if filter else '')`, `fields = ['summary',
    'updated', 'status']`, `maxResults = 100`; a `nextPageToken` is `Failure('incomplete Jira
    backlog')`; rows `{id: key, title: summary, url: f'{site}/browse/{key}', updated, state:
    status.name}`.
  - `claim(item)`: GET `/rest/api/3/myself`, PUT `/rest/api/3/issue/{item}/assignee`
    `{accountId}`.
  - `transition(item, state)`: GET `/rest/api/3/issue/{item}/transitions`, the one whose
    `to.name == state` (none or two is `Failure`), POST its id.
  - `create(draft)`: POST `/rest/api/3/issue` `{fields: {project: {key}, summary, description:
    ADF, issuetype: {name: 'Bug' if category == 'bugs' else 'Task'}}}`; with a parent, POST
    `/rest/api/3/issueLink` `{type: {name: 'Relates'}, inwardIssue: {key: new}, outwardIssue:
    {key: parent}}`; returns `{id: key, url}`. ADF: one paragraph per line.
  - `comment(item, text, category)`: POST `/rest/api/3/issue/{item}/comment` `{body: ADF}`.
  - `history(item)`: GET `/rest/api/3/issue/{item}/changelog?maxResults=100`; `isLast` must be
    true; rows `{'createdAt': created, 'toState': {'name': toString}}` for `status` items.
  - `created(item)`: GET `/rest/api/3/issue/{item}?fields=created`.
- New `adapters/tracker/github.py` (GraphQL `https://api.github.com/graphql`, Bearer
  `GITHUB_TRACKER_TOKEN`; ticket id `owner/repo#N` parsed by one `_ref`):
  - `backlog(filter)`: `repository(owner,name){issues(first:100,states:OPEN[,labels:[$filter]])
    {nodes{number title url updatedAt} pageInfo{hasNextPage}}}`; rows id `f'{repo}#{number}'`,
    state `Open`.
  - `claim(item)`: `viewer{id}`, the issue id, `addAssigneesToAssignable`.
  - `transition(item, state)`: with `board` (`<owner>/<number>`), the board's `Status` field
    option named `state` and the issue's item on that board, `updateProjectV2ItemFieldValue`;
    without `board`, `closeIssue` when `state == tracker.states.done`, else `addLabelsToLabelable`
    with the label named `state`.
  - `create(draft)`: `createIssue(input:{repositoryId, title, body, labelIds})`, body =
    description plus `\n\nRelated: {parent}` when a parent is set, label `bug` for `bugs`;
    returns `{id: f'{repo}#{number}', url}`.
  - `comment(item, text, category)`: `addComment(input:{subjectId, body})`.
  - `history(item)`: the first `ASSIGNED_EVENT` in `timelineItems` as `[{'createdAt': at,
    'toState': {'name': 'In Progress'}}]`, else `[]`.
  - `created(item)`: the issue's `createdAt`.
  Both new modules decorate `create` and `comment` with `@outward_operation('tracker')` over
  `@operation('<adapter>.<call>')`, as `linear.py` does.
- Fixtures: `tests/fixtures/tracker/linear.json`, `jira.json`, `github.json`, each a list of
  recorded responses in call order for the contract test; neutral names only (`ENG-1`,
  `PROJ-1`, `acme/app#1`).

## Setup, interview, doctor

- `cli/wuwei/commands/setup.py` `discover` (line 130): for each repository directory, read
  `README*`, `CONTRIBUTING*`, `.github/PULL_REQUEST_TEMPLATE*`; for `linear.app` or
  `atlassian.net` append `tracker links: <host> (<repo>/<file>)` to `found['lines']`. No config
  change.
- `cli/wuwei/interview.py` `QUESTIONS` (line 199): `tracker` choices Linear (first), Jira, GitHub,
  None, free `(_tracker, '<tracker> <project>, for example jira PROJ')` setting
  `adapters.tracker` and `tracker.project`; new `tickets` question (Every item: `{'tracker.required':
  True, 'tracker.skip_tiers': []}`; All but light items: `{'tracker.skip_tiers': ['light']}`;
  Optional: `{'tracker.required': False}`); new `updates` question (Progress, pull request and
  close: the default `auto`; Those plus new tickets: adds the four classes; Everything: every
  class and kind; Nothing: `[]`).
- `cli/wuwei/commands/doctor.py`: new `_tracker(root, config)` row (section `day`) appended in
  `diagnose` after `_day`: `ok` with `none` or `required` off; else `backlog` through the port:
  exit 0 `ok`, otherwise `fail` with the reason and the fix `set <names from
  config.requirements> in .wuwei/env, or bin/wuwei config set tracker.required false`. Not in
  `pr_flow`, which `plan propose` calls offline.

## Owner surfaces, docs, charters

- `cli/wuwei/commands/board.py` `read` (line 128): Work table gains a `Ticket` column
  (`tickets[name]['id']`, plus `, <n> folded` when `tracker_log` holds folded entries for it);
  a `Tickets created` table from today's `tracker.created` events (`Class`, `Subject`,
  `Ticket`, `Parent`).
- `cli/wuwei/commands/next.py` `step`: rows that name an item show `name (ticket)` using
  `data.get('tickets', {}).get(name, {}).get('id')` inline (no import: `next` is on a hook
  path).
- `cli/wuwei/listen.py` `notify` (line 66): the loop notice appends ` Ticket: <id>.` when the
  item has one.
- Docs: `docs/site/configuration.md` (`[tracker]` rows), `docs/site/adapters.md` (Jira and GitHub
  rows, credentials), `docs/site/concepts.md` glossary (ticket, tracker hygiene, fold),
  `docs/site/daily.md` (one paragraph: every item has a ticket; you see the ticket id on the
  board and in the DM), `docs/site/reference.md` (rows for `tracker create`, `tracker log`,
  `tracker done`, `plan set`). `tests/test_docs.py` pins template keys, reference commands and
  glossary links.
- Charters: `charters/_common.md` (read by every builder and gate; one home per rule) names
  `bin/wuwei tracker create --bug <item> "<title>" --evidence "<file:line>"` for a bug outside
  the item's scope, as the one exception to its follow-up rule;
  `charters/planner.md` names `tracker create <item>` at the morning gate and `--follow-up` for
  retro follow-ups; regenerate `agents/` with `bin/wuwei agents build`.

## Existing tests that change

Tests that configure `tracker = "linear"` and dispatch items (grep `tests/` for `tracker =
"linear"` and `'tracker': 'linear'`) add `[tracker] required = false` or record a ticket;
`tests/test_adapters.py` `CALLS` gains `('tracker', 'comment', ('item', 'text', 'category'),
False)`; `tests/test_reference_adapters.py:87` expects `{'id': identifier, 'url': url}` from
`linear.create`; `tests/fakes/tracker.py` gains `create`, `comment`, `created`.

## What must not change

- `adapters.tracker` defaults to `none`; with `none` or `required = false` no refusal point
  changes behaviour and `tracker log` writes nothing.
- The outward rules ahead of the new branch (security, sensitive, commitment, disagreement,
  audience flags, external channels, recipients) and every non-tracker classification.
- `_http.request` behaviour for current callers (POST with a JSON body, Bearer header).
- No hook's common-path imports (`tests/test_hooks.py` deny lists), the `tracker.call` event
  shape beyond the added `ticket` field, design spec and constitution text.

## Deferred

- Incident ids as `--triage` subjects (#415).
- Adding new GitHub issues to a Projects v2 board; Projects v2 status history.
