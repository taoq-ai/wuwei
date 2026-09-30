# Implementation Plan: remote-command guards (pinned identity, second factor, stop all)

**Branch**: `066-remote-guards` | **Date**: 2026-09-30 | **Spec**: spec.md

## Summary

All guard logic lands at the one spot every owner-DM message already routes through:
`remote.handle` and `remote._turn` in `cli/wuwei/remote.py`. Four small guard functions
are added there (`sender`, `code_step`, `confirmation`, `memory_floor`) plus a pure
`totp`. One line changes in the Slack inbound adapter (sender carries the team), one flag
in the headless argv, one config key, one credential name, three event kinds. The #65 gate
(`EXECUTABLE`, `GUARDED`) is removed.

Reused, not copied: `agent_launch.free_memory` (memory floor), `watch.records` (today's
events), `inbox.read` (the pending command's text), `state.append_event`, `parse`,
`_say`, `stop`, `start`, `resume`, `workspace.now`, `workspace.load_config`,
`env.CREDENTIALS` and `env.load` (secret handling), `hmac`/`base64` from the stdlib.

## Technical Context

Python 3.11+ stdlib only (`hmac`, `base64`, `re`); pytest for tests. The core still never
spawns a process. Tests are in process with the #65 fakes (`Transport`, `Runtime`) and
`WUWEI_NOW`; the TOTP tests use the RFC 6238 vectors. `WUWEI_NOW=2026-09-30T12:00:00+00:00`
is epoch `1790769600`, so a fresh message ts in tests is e.g. `1790769590.000100`.

## Constitution Check

- I stdlib only: `hmac.digest`, `base64.b32decode`. II three-state: `handle` returns 0
  (done or ignored), 1 (refused, pending, nothing to confirm, low memory), 2 (no pin,
  bad secret, memory unmeasured). III one behaviour, one function: each guard is one
  function in `remote.py` with one test and one mutation test. IV test first: tasks.md.
  V ponytail: no pin file, no confirm command on the host, no nonce, no new module, no
  budget or quiet-hours code for features that do not exist. VII security: the secret is
  a credential (stripped from child processes, redacted), never in a reason string;
  events carry ids, command words, factor kind and step only.

## Design

### 1. `adapters/inbound/slack.py` (lines 34-42)

Read `team = row.get('team', '')`, add it to the all-strings check, and emit
`'sender': f'{team}/{user}'`. The mention filter keeps comparing `user` with
`owner.handles`. `tests/test_reference_adapters.py:376-396` fixture rows gain `'team':
'T1'` and the expected sender becomes `'T1/U0OWNER'`.

### 2. `adapters/runtime/claude.py` (`headless`, lines 77-82)

Add `'--strict-mcp-config'` to argv after `--allowedTools` and before `--resume` (built:
the resume test reads `--resume <id>` as the last two items; no `--mcp-config`, so no MCP
server loads) and
replace the comment "MCP tools are not built-ins: #66 scopes them." with one saying
`--strict-mcp-config` without `--mcp-config` loads no MCP server. Nothing else changes.

### 3. `cli/wuwei/workspace.py` (SCHEMA line 131)

`"control_plane": {"content": ..., "owner": (str, "")}`. Format validation stays in
`remote.sender` (the schema has no pattern constraint).

### 4. `cli/wuwei/env.py` (line 12)

Add `'WUWEI_TOTP_SECRET'` to `CREDENTIALS` (kept out of seat and headless environments,
redacted in diagnostics even when set in the process environment).

### 5. `cli/wuwei/remote.py`

Remove `EXECUTABLE` and `GUARDED`. Add:

```python
FACTOR = frozenset({'plan', 'ask'})
WINDOW = 120  # seconds: how long a code or a confirmation counts
CONFIRM = 'Reply confirm within 2 minutes to run it, or send it again ending with a current code.'
NOTHING = 'Nothing to confirm from the last 2 minutes.'
CHANGED = 'Refused: this sender does not match the pinned identity. Confirm it on the host.'
LOW_MEMORY = 'Not started: free memory on the host is below the floor.'
```

Every line must pass `outward.lint(text, 'D1', config)` (no `the owner`, `queue`,
`agent`, `seat`, `wuwei`, `claude`, `pending draft`).

Functions (all new unless named):

- `split(text) -> (text, code)`: `m = re.fullmatch(r'(.*\S)\s+([0-9]{6})', text.strip(), re.S)`;
  return `(m[1], m[2])` or `(text, '')`.
- `parse(text)`: add `if lower == 'confirm': return 'confirm', ''`. Nothing else changes.
- `sender(config, event) -> 'owner' | 'changed' | 'other'`:
  `pin = config['control_plane']['owner']`; unless
  `re.fullmatch(r'[A-Z0-9]+/[UW][A-Z0-9]+', pin)` raise
  `ValueError(f'control_plane.owner must pin <team>/<user>; this message came from {event["sender"]}')`.
  `event['sender'] == pin` is `owner`; same text after the last `/` is `changed`; else
  `other`.
- `totp(key, step) -> str` (pure): `digest = hmac.digest(key, step.to_bytes(8, 'big'),
  'sha1')`, `offset = digest[-1] & 15`,
  `f'{(int.from_bytes(digest[offset:offset + 4], "big") & 0x7fffffff) % 10**6:06d}'`.
- `_today(root)`: `watch.records(workspace.day_dir(root) / 'events.jsonl')`.
- `code_step(root, event, code) -> int | None`: `secret =
  os.environ.get('WUWEI_TOTP_SECRET', '')`; `ts = float(event['ts'])`; return None when
  `not code or not secret or workspace.now().timestamp() - ts > WINDOW`. Decode
  `base64.b32decode(secret.replace(' ', '').upper() + '=' * (-len(...) % 8))`; on
  `binascii.Error` raise `ValueError('WUWEI_TOTP_SECRET is not base32')` (`from None`,
  so the value never reaches a traceback or reason). `used` = max `step` over today's
  `remote.confirmed` payloads with `factor == 'code'` (default -1). Return the first
  `step` in `int(ts // 30) + d for d in (-1, 0, 1)` with `step > used` and
  `hmac.compare_digest(totp(key, step), code)`, else None.
  `# ponytail: used steps are read from today's events only; a code accepted in the last
  minute of a day can be replayed in the first minute of the next. Keep the last step in
  the inbox directory if that matters.`
- `confirmation(root) -> dict | None`: from `_today(root)`, the last `remote.pending`
  row whose `payload['command'] in FACTOR`; None when there is none, its id is already in
  a `remote.confirmed` payload, or `(workspace.now() - obligations._time(row['ts']))
  .total_seconds() > WINDOW` (the host clock, pending event to now). Otherwise return the
  inbox line with that id from `inbox.read(root)` (None if absent).
- `memory_floor(root) -> bool`: `config = workspace.load_config(root)`; `return
  agent_launch.free_memory(config, root) >= config['host']['free_memory_mb'] * 1024**2`
  (`from wuwei.guards import agent_launch` inside the function, as built: a module-level
  reference went stale when other tests re-import the guard modules). An unmeasured host raises
  `ValueError` from `free_memory`: exit 2 in `handle`.

`handle` (lines 130-185), new order inside the existing `try` (the channel check and the
`except` block are unchanged):

```python
if event['id'] in sent(root):
    return 0
text, code = split(event['text'])
command = parse(text)
who = sender(workspace.load_config(root), event)
if who == 'other':
    if not any(row['kind'] == 'remote.ignored' and row['payload'].get('sender') == event['sender']
               for row in _today(root)):
        state.append_event('remote.ignored', {'sender': event['sender']}, root=root)
    return 0
if who == 'changed' and command != ('stop', 'all'):
    state.append_event('remote.refused', {'id': event['id']}, root=root)
    return _say(transport, root, CHANGED, 1)
if command == ('confirm', ''):
    line = confirmation(root)
    if line is None:
        return _say(transport, root, NOTHING, 1)
    state.append_event('remote.confirmed', {'id': line['id'], 'factor': 'reply'}, root=root)
    event, command = line, parse(split(line['text'])[0])
elif command and command[0] in FACTOR:
    step = code_step(root, event, code)
    if step is None:
        state.append_event('remote.pending', {'id': event['id'], 'command': command[0]}, root=root)
        return _say(transport, root, CONFIRM, 1)
    state.append_event('remote.confirmed', {'id': event['id'], 'factor': 'code', 'step': step}, root=root)
if command is None:
    ...  # decision reply path, unchanged (uses `text`, the code stripped)
```

Then the existing `run`/`cloud` branch, and the `if verb not in EXECUTABLE` block is
deleted. The `status`, `report`, `plan`, `ask`, `stop` and `reply` branches are unchanged;
`plan` and `ask` use `event['id']` (for a confirmation, the original command's inbox id,
so the session thread is the command message as in #65).

`_turn` (line 216): first statement `if not memory_floor(root): return _say(transport,
root, LOW_MEMORY, 1)`. Applies to start and resume; nothing is registered.

### 6. Producer tables, signal, docs, template

- `cli/wuwei/commands/event.py` line 23: add `'confirmed', 'ignored', 'refused'` to the
  `remote.*` comprehension.
- `cli/wuwei/signal.py`: `remote.confirmed`, `remote.ignored` into `SILENT`;
  `remote.refused` into the page tuple at line 56.
- `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`: the three kinds
  in `expected` (the scanner finds them as literals).
- `templates/workspace/config.toml` `[control_plane]`: `owner = "" # <team id>/<user id>
  pinned for commands from the owner DM; empty handles none.`
- `docs/site/configuration.md`: a `control_plane.owner` row next to
  `control_plane.content` (line 119); rewrite the "Commands from the owner DM" paragraph
  that starts "Until the remote-command guards land" (lines 320-323) to describe the pin,
  ignored senders, the changed-identity refusal, the second factor (`WUWEI_TOTP_SECRET`
  in `.wuwei/env`, base32, a code ending the message, or `confirm` within 2 minutes),
  `stop all`, the memory floor and `--strict-mcp-config`. `docs/site/adapters.md` line 61:
  the inbound sender is `<team>/<user>`. Keep every phrase `tests/test_docs.py` asserts.

### Must not change

- `control_plane.py`, `outward.classify`, the chat port, drafts: unchanged.
- `listen.tick`, the cursor, `sent.json` handling, the kill switch: unchanged.
- `stop`, `start`, `resume`, `deny`, `tools`, `dm`: unchanged except the floor line in
  `_turn`.
- The agent-launch guard: reused (`free_memory`), not edited.
- `inbox.FIELDS`: unchanged; the team rides in `sender`.

### Existing tests this changes (fixtures, and the #65 gate tests replaced)

- `tests/test_remote.py`: `OWNER` gains `[control_plane]\nowner = "T1/U1"\n` (the line in
  `test_status_sends_the_status_line_without_the_prefix` that rewrites the config adds
  `content = "none"` under the same table); `event()` sender becomes `'T1/U1'`; the `ws`
  fixture patches `agent_launch.free_memory` to return `2**40`; `open_gate` becomes a
  fixture that patches `remote.code_step` to return a step (factor satisfied), and tests
  that start sessions through `handle` use it. `test_gate_records_guarded_commands_as_pending`
  and `test_gate_records_a_reply_that_would_resume_a_session` are replaced by the US2 and
  US3 tests; `test_fixed_lines_pass_the_outward_lint` lists the new lines instead of
  `GUARDED`; the reserved-kinds parametrization gains the three new kinds.
- `tests/test_reference_adapters.py`: the Slack inbound fixture rows and expected sender.
- `tests/test_runtime.py`: the expected headless argv gains `--strict-mcp-config`.

## Complexity Tracking

None. One marked shortcut: the day-scoped replay record (ponytail comment in
`code_step`).
