# Implementation Plan: Slack inbound by polling mentions and DMs

**Branch**: `050-slack-inbound` | **Spec**: `specs/050-slack-inbound/spec.md`

## Summary

One new adapter module, `adapters/inbound/slack.py` (one function, `poll`), built on the
Slack page loop that already lives in `adapters/chat/slack.py`. That loop is lifted out
of `sent` into a shared `history(channel, **params)` so both callers use it, and it gains
the one thing both need: an HTTP 429 turned into a clear exit 2. One requirements row in
`wuwei config check`. Two doc tables and one paragraph. The listener, the inbox, the
redactor and the registry are untouched: #48 and #49 already dedup, redact, persist the
cursor and wake the planner.

## Technical Context

Python 3.11+, stdlib only at runtime (`json`, `os`, `re`, `urllib`), pytest for tests.
No subprocess. Tests replay recorded HTTP through the existing `replay` helper in
`tests/test_reference_adapters.py`, which patches `urllib.request.urlopen`.

## Constitution Check

- I Stdlib only: yes.
- II Three-state exits: `poll` is 0 with a list of events, or 2 with a reason (missing
  credential, malformed cursor, owner id missing, error body, malformed row, 429, over
  ten pages, network error). Never 1: findings are `inbox.store`'s redaction.
- III One behaviour, one function: the Slack page loop lives only in
  `chat.slack.history`; dedup only in `inbox.store`; redaction only in the redactor;
  the cursor only in `listen.tick`.
- IV Test first: tasks.md orders each test before its code.
- V Ponytail: no new config key, no new port operation, no backoff state, no thread
  replies, no `search.messages`, no adapter-side dedup. Two `ponytail:` comments (lookback
  cursor, 429 without backoff) plus the existing ten-page ceiling.
- VII Security: tokens from the environment or `.wuwei/env` only (already in
  `env.CREDENTIALS`, so kept out of seat environments); no provider text in reasons (the
  `Retry-After` value is echoed only when it is all digits); error bodies are never
  parsed as data; text is stored only through `inbox.store`, which redacts.

## Design

### 1. `adapters/chat/slack.py`: lift the page loop into `history`

Replace `from urllib.request import Request, urlopen` with `import urllib.request`,
`from urllib.error import HTTPError` and `from urllib.request import Request`. The call
must be `urllib.request.urlopen(...)`, looked up at call time: the test `replay` helper
patches `urllib.request.urlopen`, and a name bound at import time in an already imported
module would reach the network.

```python
def history(channel, **params):
    """Bounded conversations.history rows, newest first; each caller validates its rows."""
    token = os.environ.get('SLACK_USER_TOKEN') or credential('SLACK_BOT_TOKEN')
    rows, cursor = [], ''
    for _ in range(10):
        url = URL + 'conversations.history?' + urlencode(
            {'channel': channel, 'limit': 100, 'cursor': cursor, **params})
        try:
            with urllib.request.urlopen(Request(url, headers={'Authorization': f'Bearer {token}'}),
                                        timeout=30) as response:
                body = response.read(4_000_001)
        except HTTPError as exc:
            if exc.code != 429:
                raise
            # ponytail: no backoff state; the caller's next poll is the retry.
            # Persist a not-before time if 429s repeat.
            wait = (exc.headers or {}).get('Retry-After', '')
            raise Failure(f'rate limited; retry after {wait if wait.isdigit() else "unknown"} s') from None
        if len(body) > 4_000_000:
            raise Failure('history response too large')
        value = json.loads(body)
        if not isinstance(value, dict) or value.get('ok') is not True or not isinstance(value.get('messages'), list):
            raise Failure('invalid history response')
        rows.extend(value['messages'])
        cursor = value.get('response_metadata', {}).get('next_cursor', '')
        if not isinstance(cursor, str):
            raise Failure('invalid history cursor')
        if not cursor:
            return rows
    raise Failure('history exceeds ten pages')
```

`sent` keeps its decorator, its query check and its per-row checks and filter unchanged,
and loops over `history(channel)` instead of fetching pages itself. Its results for any
recorded response are identical; the only difference is a 429 now reads
`slack.sent: could not run: rate limited; retry after N s` instead of `HTTPError`.

### 2. `adapters/inbound/slack.py` (new)

```python
"""Slack inbound: the owner DM channel and mentions of the owner, from conversations.history."""

import re

from .._http import Failure, credential, operation
from ..chat.slack import history

# ponytail: one cursor for every channel. Re-reading 300 s behind it covers a message
# that lands in a channel already read while later ones are read, and bounds the first
# poll; inbox.store dedups the overlap. Per-channel cursors if a gap is ever observed.
LOOKBACK = 300
TS = re.compile(r'\d+\.\d{6}')


@operation('slack.poll')
def poll(since, *, root=None):
    from wuwei import workspace
    if not isinstance(since, str) or since and not re.fullmatch(r'\d+(?:\.\d+)?', since):
        raise Failure('invalid cursor')
    config = workspace.load_config(workspace.find_workspace(root))
    owners = [handle for handle in config['owner']['handles']
              if re.fullmatch(r'[UW][A-Z0-9]+', handle)]
    channels = config['outbound']['work_channels'] + config['outbound']['external_channels']
    if channels and not owners:
        raise Failure('owner.handles has no Slack user id for mentions')
    dm = credential('SLACK_OWNER_DM_CHANNEL')
    seconds = int(since.split('.')[0]) if since else int(workspace.now().timestamp())
    events = []
    for channel in (dm, *channels):
        for row in history(channel, oldest=str(seconds - LOOKBACK)):
            if not isinstance(row, dict):
                raise Failure('invalid history message')
            if row.get('bot_id') or row.get('app_id') or row.get('subtype'):
                continue
            user, text, ts, thread = (row.get('user'), row.get('text'), row.get('ts'),
                                      row.get('thread_ts', ''))
            if not (all(isinstance(value, str) for value in (user, text, ts, thread))
                    and user and TS.fullmatch(ts)):
                raise Failure('invalid history message')
            if channel != dm and (user in owners or not any(
                    f'<@{owner}>' in text or f'<@{owner}|' in text for owner in owners)):
                continue
            events.append({'id': f'{channel}/{ts}', 'source': 'slack', 'channel': channel,
                           'thread': thread, 'sender': user, 'text': text, 'ts': ts})
    return sorted(events, key=lambda event: tuple(map(int, event['ts'].split('.'))))
```

Notes for the builder:

- Order of checks is the "no request without credentials" guarantee: cursor, config,
  owner id, `SLACK_OWNER_DM_CHANNEL`, then `history`, whose first line reads the token.
- `@operation` turns every `Failure`, `OSError` (including a non-429 `HTTPError`),
  `ValueError` (`ConfigError`, `json` errors) and `KeyError` into `Result(2, None,
  'slack.poll: could not run: ...')`, printing only safe text. Do not add another
  try/except.
- The sort key is exact integer comparison; `TS` requires six fractional digits, which
  Slack always sends, so `(seconds, micros)` tuples order correctly.
- `source` must be `"slack"`: the listener keys the cursor by the configured adapter
  name (`listen.py:43`), and `inbox.store` dedups by `(source, id)`.
- The text is returned unredacted; `inbox.store` redacts it before the write.

### 3. `cli/wuwei/commands/config.py` (`requirements`, lines 27-32)

Add one row:

```python
('inbound', 'slack'): [('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN'), ('SLACK_OWNER_DM_CHANNEL',)],
```

The `custom_app` override stays on `('chat', 'slack')` only: reading history uses the
user token when present, like `sent` and `dm`.

### 4. Docs

- `docs/site/adapters.md`: port table row `| inbound | none, slack | none |`;
  credentials table row `| inbound.slack | SLACK_BOT_TOKEN or SLACK_USER_TOKEN, plus
  SLACK_OWNER_DM_CHANNEL. Mentions in work and external channels need your Slack user
  id in owner.handles. |` (backticks as in the neighbouring rows).
- `docs/site/configuration.md`: `adapters.inbound` row reads `Inbound message source:
  none or slack.`; in "Running the listener" add one paragraph: with
  `adapters.inbound = "slack"` the listener reads every message in
  `SLACK_OWNER_DM_CHANNEL` and messages that mention a Slack user id from
  `owner.handles` in `outbound.work_channels` and `outbound.external_channels`;
  top-level messages only (reply in the DM as a new message, not in a thread); bot and
  app posts are skipped; each poll re-reads five minutes behind the cursor and the first
  poll starts five minutes back; a Slack rate limit fails that poll, and the next poll
  retries; the reading token needs `channels:history`, `groups:history` and
  `im:history` and membership of the polled channels.

## Shared helpers reused

`adapters/_http.py` (`operation`, `credential`, `Failure`), `chat.slack.history` (lifted
from `sent`, not copied), `workspace.load_config`, `workspace.find_workspace`,
`workspace.now` (honours `WUWEI_NOW` in tests), `listen.tick` and `inbox.store`
unchanged, the owner chat-id rule from `obligations._owner_login` (same regex; the
function itself returns the code-host login, so it is not callable here).

## Must not change

- `cli/wuwei/listen.py`, `cli/wuwei/inbox.py`, `adapters/redactor/builtin.py`,
  `adapters/inbound/none.py`, `cli/wuwei/registry.py`, `cli/wuwei/env.py`,
  `cli/wuwei/workspace.py` (no new config key, no new default).
- `chat.slack.post`, `dm`, `_send` and `sent`'s results; the outward guard.
- `templates/workspace/config.toml`: no new keys.
- No `time.sleep`, no subprocess, no new state file, no new event kind.

## Test plan

All in existing files. HTTP is replayed; no network.

`tests/fixtures/reference_adapters/recordings.json`: add `slack_history`, a list of two
`conversations.history` bodies:

1. The owner DM channel `D1`: one bot row only (`bot_id`, subtype `bot_message`, a
   draft WUWEI posted), so the acceptance counts exactly the two mentions.
2. Work channel `C1`, newest first as Slack returns: `<@U0OWNER> can you look at this`
   from `U1`; `ping <@U0OWNER|pat>, call +44 20 7946 0958` from `U2` with a
   `thread_ts`; a message from `U3` with no mention; `<@U0OWNER> note to self` from
   `U0OWNER`; a `channel_join` subtype row; a row with `app_id` mentioning the owner.

`tests/test_reference_adapters.py`, a small fixture `slack_case(tmp_path, monkeypatch)`:
`.wuwei/config.toml` with `[owner] handles = ["U0OWNER", "pat-gh"]`, `[outbound]
work_channels = ["C1"]`, `[adapters] inbound = "slack"`; `WUWEI_WORKSPACE`, `WUWEI_NOW`
set; `SLACK_BOT_TOKEN` and `SLACK_OWNER_DM_CHANNEL=D1` set.

- `test_slack_sent_replay` (characterisation, guards the refactor; on main it cannot replay because `sent` binds `urlopen` at import): one
  page with an owner row, a bot row and a row from someone else; `slack.sent('C1',
  ['U0OWNER'])` returns only the owner row; a second call replaying a 429 `HTTPError`
  with `Retry-After: 30` returns exit 2 with `rate limited` and `30` in the reason (this
  half fails on main).
- `test_slack_inbound_two_mentions_once` (issue acceptance): replay both recordings, then
  both again; the first `listen.tick(root)` returns 1 and the inbox holds exactly the two
  mentions, ids `C1/<ts>`, oldest first, the phone number redacted; the second
  `listen.tick(root)` returns 0 and the inbox is unchanged; the second tick's requests
  carry `oldest` = cursor seconds minus 300. On main this fails with
  `unknown adapter 'slack'`.
- `test_slack_inbound_events`: direct `poll('', root=...)` over the same recordings:
  exactly the two mentions, in `ts` order, normalised shape (`source` `slack`, `sender`
  `U1`/`U2`, text unredacted), `thread` set only on the threaded one; every request has
  `oldest` = `WUWEI_NOW` seconds minus 300, `limit=100`, and
  `Authorization: Bearer <token>`.
- `test_slack_inbound_fails_closed` (parametrised): 429 with `Retry-After: 30` (reason
  has `rate limited` and `30`); `{'ok': False, 'error': 'x'}`; a row without `user`; a
  row with `ts` `"1"`; cursor `"abc"`; ten pages that each carry a `next_cursor`; work
  channels set but `owner.handles` without a Slack id. Each: exit 2, data None, reason
  starts `slack.poll: could not run`, no provider text.
- `test_slack_inbound_missing_credentials_never_calls_network` (parametrised over
  `SLACK_OWNER_DM_CHANNEL` and both tokens absent): exit 2, variable named, `replay`
  recorded no request.
- `test_slack_inbound_dm_only`: no work or external channels and no Slack id in
  `owner.handles`; replay an inline `D1` page with an owner row `"approve D-3"` (no
  mention) and a bot row: one request, to `D1`; one event, id `D1/<ts>`, sender the
  owner.

`tests/test_env_credentials.py`: add `('inbound="slack"', '', ('SLACK_BOT_TOKEN',
'SLACK_USER_TOKEN', 'SLACK_OWNER_DM_CHANNEL'))` to the
`test_config_reports_missing_and_set` table.

`tests/test_adapters.py` needs no edit: `test_module_contracts` imports every module
under `adapters/inbound/` and checks `poll(since, root)`.

Full suite: `python -m pytest -q`.
