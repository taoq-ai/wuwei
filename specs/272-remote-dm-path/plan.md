# Implementation Plan: The DM path works from the runbook alone

**Branch**: `272-remote-dm-path` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

## Summary

Five small fixes at the shared spot for each finding. F1: a one-name exemption from
redaction in `env.py`, plus one log line in `remote.handle`. F2: a `to_owner` keyword on
the shared outward lint that only `remote.dm` passes. F7: `listen.tick` returns 0 or 2.
F11: one base-URL helper in `adapters/chat/slack.py`, which inbound already reads through.
F10 and the runbook: doc edits pinned by the existing docs test. No new module, no new
config key, no new event kind.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime.
**Testing**: pytest, run as `python -m pytest -q` from the repository root.
**Constraints**: redaction stays on for every real credential; the outward lint stays on
for every message to anyone but the pinned owner; no network in tests (fake Slack behind
a monkeypatched `urllib.request.urlopen`).

## Constitution Check

- I stdlib only: `urllib.parse.urlsplit` is the only new import. Pass.
- II exits: `listen --once` becomes 0 clean or 2 unrun; a bad `SLACK_API_BASE` fails closed
  as exit 2 without echoing the value. Pass.
- III one behaviour, one function: the lint change lives in `outward.lint`; config check
  and the listener print one shared constant. Pass.
- IV test first: every task pair in tasks.md is test then code. Pass.
- V ponytail: one tuple, one keyword, one helper; nothing speculative. Pass.
- VII security: tokens, TOTP secret and `SLACK_API_BASE` stay redacted; only the channel
  id (an identifier) leaves the redaction set; it is still kept from seats. Pass.

## Changes, file by file

### F1: `cli/wuwei/env.py`

- Add `SLACK_API_BASE` to `CREDENTIALS` (kept from seats, redacted when set in the process
  environment).
- Add, next to `CREDENTIALS`:
  `PUBLIC = ('SLACK_OWNER_DM_CHANNEL',)  # identifiers: kept from seats, never redacted`
- `session()` (`env.py:33`): skip names in `PUBLIC` when seeding `redact.VALUES` from the
  process environment.
- `load()` (`env.py:79` and `env.py:85`): skip names in `PUBLIC` in both places that add
  to `redact.VALUES` (the file values, then the effective environment values).
- `child_environment()` unchanged: `SLACK_OWNER_DM_CHANNEL` stays in `CREDENTIALS`.

### F1: `cli/wuwei/remote.py:handle`

- At `remote.py:200-201`, before `return 0`, print one line, flushed, with no message
  text: `listen remote.unmatched: {event.get("id")} is not in the owner DM channel`.
  Printing goes through `redact.Output`, so a real credential in an id is still filtered.

### F2: `cli/wuwei/outward.py`

- `lint(text, channel, config, *, root=None, to_owner=False)`: when `to_owner`, skip the
  `outward: owner name must be configured` return (`outward.py:39-40`) and the
  third-person loop over owner names, handles and pronouns (`outward.py:59-62`). The
  config reads above stay, so a malformed `owner` table is still exit 2. Patterns, emoji,
  banned characters, lengths and the voice lint are untouched.
- `check_lint(inputs, root, config, channels, *, to_owner=False)`: pass `to_owner` to
  `lint`. `cli/wuwei/guards/outward.py:check_lint(payload)` is not changed, so no hook
  payload can reach the keyword.
- Add one constant shared by config check and the listener:
  `OWNER_UNSET = 'owner.name: not set; the outward lint refuses every outward message except replies in the owner DM'`.

### F2: `cli/wuwei/remote.py:dm`

- `remote.py:153-155`: call `outward.check_lint(..., {'chat'}, to_owner=True)`.
- Update the comment at `remote.py:16` (fixed lines pass the lint for the owner DM; the
  third-person rules do not apply there).

### F2: `cli/wuwei/commands/config.py:run`

- After the Credentials loop (`config.py:60`) and before `Host protections:`, print
  `Owner:` and then `  owner.name: set` or `'  ' + outward.OWNER_UNSET`. The status is not
  changed by this line.

### F2 and F7: `cli/wuwei/listen.py`

- `run()` (`listen.py:78-82`): load the config once; when `config['owner']['name']` is
  blank, print `'listen ' + outward.OWNER_UNSET` (flushed) once, before `watch.serve`.
- `tick()` `listen.py:51`: delete `code = int(bool(stored.data))`; a stored batch leaves
  `code` at 0.
- `tick()` `listen.py:70`: replace `code = max(code, remote.handle(root, rows[index]))`
  with `if remote.handle(root, rows[index]) == 2: code = 2`.
- `cli/wuwei/commands/listen.py` unchanged: `adapters.inbound = "none"` already exits 2.

### F11: `adapters/chat/slack.py`

- Keep `URL = 'https://slack.com/api/'` as the default. Add one helper:

  ```python
  def _url(method):
      base = os.environ.get('SLACK_API_BASE') or URL
      parts = urlsplit(base)
      if parts.scheme != 'https' and not (
              parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost', '::1')):
          raise Failure('SLACK_API_BASE must be https, or http to a loopback host')
      return base.rstrip('/') + '/' + method
  ```

- `_send` (`slack.py:22`): `request(_url('chat.postMessage'), token, payload)`.
- `history` (`slack.py:52`): `_url('conversations.history') + '?' + urlencode(...)`.
- `adapters/inbound/slack.py` unchanged: it reads through `chat.slack.history`.

### Tests support: `tests/conftest.py`

- Also `monkeypatch.delenv('SLACK_API_BASE', raising=False)`, so a developer's value never
  redirects the recorded adapter tests.

### Docs

- `docs/site/remote.md` section 2: after the `.wuwei/env` block, one short paragraph:
  optional `SLACK_API_BASE=<base URL>` for a fake Slack or a proxy, default
  `https://slack.com/api/`, `https` only or `http` to `127.0.0.1` or `localhost`, treated
  as a credential and never printed.
- `docs/site/remote.md` section 3: name `owner.name` in `.wuwei/config.toml`: used by the
  outward lint for messages to other people; replies in the owner DM send without it;
  until it is set, `bin/wuwei config check` and the listener log print
  `owner.name: not set`. Say the no-pin `listen --once` run exits 2.
- `docs/site/remote.md` section 5: `bin/wuwei listen --once` exits 0 when it polled, with
  or without new messages, and 2 when it could not run (configuration, credentials, the
  pin, the Slack API), with the reason printed. Channels other than the owner DM log a
  `remote.unmatched` line and are never commands.
- `docs/site/configuration.md:299-300`: the same exit-code sentence after
  "`bin/wuwei listen --once` runs one poll."
- `docs/site/adapters.md:25`: replace "Other ports in the design, including control
  planes, are **planned** and have no config keys in the shipped template." with a
  sentence that the control plane is configured under `[control_plane]` (`content`,
  `owner`) and sends through the chat adapter, linking [Remote operation](remote.html).
- `docs/site/adapters.md` config check paragraph (line 53-56): add the `Owner:` line.
  `chat.slack` and `inbound.slack` rows: optional `SLACK_API_BASE`.

## Tests that change because behaviour changed

- `tests/test_listen.py`: every `tick(root) == 1` for a stored batch (lines 102, 111, 153,
  193, 209, 379, 404) becomes `== 0`; `test_once_returns_the_tick_code` (line 343)
  expects 0 then 0.
- `tests/test_reference_adapters.py:347` and `:359`: `listen.tick(slack_case) == 0`.
- `tests/test_remote.py:test_dm_lint_finding_sends_nothing` (line 138): "Robin should
  look." now sends in the owner DM; use a text that hits a rule still on for the owner,
  for example `'wuwei is busy.'` (default pattern `\bwuwei\b`).
- `tests/test_docs.py:test_remote_runbook_matches_the_code`: add `SLACK_API_BASE` to the
  credential tuple (asserts it is in `env.CREDENTIALS` and on the page) and assert the new
  runbook text (`owner.name: not set`, the `listen --once` exit sentence).

## What must not change

- `redact.known_values`, `state._append_jsonl`, `inbox.store` and the redactor adapter.
- The outward lint for every caller other than `remote.dm`: `guards/outward.py`,
  `outward.check_call`, `check_tier`, `classify`, drafts and `drafts approve`.
- `CREDENTIALS` membership of `SLACK_OWNER_DM_CHANNEL` (seats still do not inherit it).
- `config check` exit codes; `listen` loop behaviour (the loop ignores tick codes).
- The default Slack base URL and the request shapes the recorded adapter tests replay.
- The inbox format; pre-fix `[REDACTED]` lines are not migrated.

## Project Structure

No new files outside `specs/272-remote-dm-path/`. research.md, data-model.md,
contracts/ and quickstart.md are omitted: the root cause is in spec.md and nothing here
adds an entity or an interface beyond the `to_owner` keyword and `SLACK_API_BASE`.
