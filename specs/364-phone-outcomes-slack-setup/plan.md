# Implementation Plan: phone answers to two-way decisions are outcomes, and `wuwei setup slack` connects the DM in one command

**Branch**: `364-phone-outcomes-slack-setup` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

Small changes at the spots everything already routes through:

1. `remote.handle` (the one place a DM answer lands) reads the pending record's
   `Reversibility:`. Two-way: it calls the existing owner-outcome writer,
   `commands/decision.owner_outcome`, with the workspace root and a confirmation that the
   pinned DM sender already gave. One-way or `unsure`: evidence as today, with a coaching
   line that names the host command.
2. `owner_outcome` gains two keyword arguments, `root` and `confirm`, so a caller that is
   not the host terminal can reuse every check and write it does. No second writer.
3. `env.write(root, values)`: the one writer for `.wuwei/env` lines (mode 0600).
4. `setup slack`: a positional target on the existing `setup` command and two functions in
   `commands/setup.py` (`slack`, `connect`) plus one wait helper. They reuse `getpass`,
   `env.write`/`env.load`, the inbound port's `poll`, `setup._edit` (the owner config edit
   frame), `commands/watch.service` (listener install and uninstall) and `config.run`
   (config check). `_setup` calls `connect` when this run's interview answered Slack.
5. Interview rows for chat and tracker gain the unsupported tools and one backlog line;
   `discover` adds one line for a non-GitHub remote.
6. Docs: remote.md leads with the command; section 7, daily.md and configuration.md say
   which DM answers are outcomes.

No new module, no new config key, no new state key or event kind, no new guard, no new
Slack API method or scope.

## Technical Context

Python 3.11+ stdlib only (`getpass`, `secrets`, `base64`, `time`); pytest for tests. The
core never imports `subprocess` or an adapter module directly: the DM wait goes through
`registry.load('inbound', ...)`, the listener install through `commands/watch.service`
(already used by setup for the watch). Every config value still lands through the one owner
confirmation (`setup._edit` then `config.offer`). Tests use the existing fakes:
`tests/test_remote.py` `Transport` (lints every DM), `Runtime`, `routed`, `remote_row`;
`tests/test_setup.py` `project`, `host`, `terminal` fixtures; monkeypatched `getpass.getpass`,
`registry.load` for `inbound`, `commands.watch.service` and `service_platform`.

## Build order and #354

Build after #354 (`354-owner-confirm`) merges when it has; it rewrites the same lines in
`commands/decision.owner_outcome`, `docs/site/remote.md` section 7 and `daily.md`. The plan
below is written against `main` (b2a4557). When #354 is on the base, make these swaps and
nothing else:

| On main | After #354 |
| --- | --- |
| `owner_outcome(args, *, root=None, confirm=None)`; `(confirm or _host_confirm)(digest, prompt=...)` | `owner_outcome(args, note=None, *, root=None, where=None)`; `where = where or owner_confirm(root, args.id, digest, prompt)` |
| `remote.handle` passes `confirm=lambda *args, **kwargs: True` | passes `where='in the owner DM'` (written to the record Notes by `owner_record`) |
| `NOTED` ends `confirm it on the host: decision outcome {identifier} {option}.` | ends `confirm it on the host: decide {identifier} {option}.` |
| `setup slack` confirmation is the digest from `config.offer` | the same call asks y/N |
| docs name `bin/wuwei decision outcome` for one-way | docs name `bin/wuwei decide` |

## Changes by file

### `cli/wuwei/commands/decision.py`

- `owner_outcome(args)` becomes `owner_outcome(args, *, root=None, confirm=None)`:
  `root = root or workspace.find_workspace()` (line 92) and
  `if not (confirm or _host_confirm)(digest, prompt=...)` (line 114). Nothing else changes:
  the option check, `already answered`, the route check, the prior-outcome check, the
  re-read after confirmation, the state update that resumes linked parked or escalated
  items, the `decision.decided`/`decision.reversed` event and `set_outcome` stay as they
  are. The CLI path (`run`) passes neither argument.

### `cli/wuwei/remote.py`

- Two fixed lines next to `ANSWERED`:
  - `RECORDED = 'Recorded {identifier} option {option} as your outcome; it can be undone, so no host step is needed.'`
  - `NOTED = 'Noted {identifier} option {option}. {identifier} cannot be undone, so confirm it on the host: decision outcome {identifier} {option}.'`
- In `handle`, the `command is None` branch (lines 267-284):
  - read `decisions = control_plane.pending(root)` once and pass it to
    `control_plane.parse`;
  - `two_way = decisions[identifier]['Reversibility'] == 'two-way'`;
  - the first-answer rule (`replied`, `ANSWERED`) applies only when not `two_way`; its
    same-answer reply becomes `NOTED`;
  - append `decision.replied` as today (the trail of where the answer came from);
  - when `two_way`: `code, reason = decision_command.owner_outcome(SimpleNamespace(id=identifier, option=option), root=root, confirm=lambda *args, **kwargs: True)`
    with a comment that the pinned DM sender is the confirmation for a two-way door and a
    one-way door keeps the host (#364). A non-zero `code` raises `RuntimeError(reason)`, so
    the existing `except` prints `listen remote unmeasured: <reason>`, DMs `FAILED` and
    returns 2;
  - no live session: `return _say(transport, root, (RECORDED if two_way else NOTED).format(...), 0)`;
  - live session: when `two_way`, send `RECORDED` first, then resume as today; return the
    highest of the send and the resume.
- Import `from wuwei.commands import decision as decision_command` inside the branch, like
  the existing lazy `status` import.

### `cli/wuwei/commands/event.py` and `cli/wuwei/state.py`

- `EVENT_PRODUCERS['decision.decided']` and `['decision.reversed']`:
  `'wuwei decision outcome or wuwei listen (two-way DM answer)'`.
- `STATE_PRODUCERS['decision_outcomes']`: append `or wuwei listen (two-way DM answer)`.
  Both stay reserved; the listener is a CLI producer, not the `event` command.

### `cli/wuwei/env.py`

- `write(root, values)`: refuse a symlinked `.wuwei/env`; read the existing lines (empty
  when the file is missing); for each name, which must be in `CREDENTIALS` and whose value
  must match `[^\s"'#\\]+`, drop lines whose name before `=` equals it and append
  `NAME=value`; `workspace.atomic_write(path, text, mode=0o600)`. Other lines and comments
  are kept in order. About ten lines; no parsing beyond the name.

### `cli/wuwei/interview.py`

- `BACKLOG = 'https://github.com/taoq-ai/wuwei/issues/370'` and
  `LATER = f'Not supported yet, so WUWEI sets the adapter to none. Integrations backlog: {BACKLOG}'`.
- Tracker row choices: `None`, `Linear` (unchanged), `GitHub Issues` and `Jira`, both
  `(LATER, {'adapters.tracker': 'none'})`.
- Chat row: question `Which tool does your team use for messages? Your DM and review pings
  go there.`; choices `Slack` (`{'adapters.chat': 'slack'}`, description saying setup
  connects the DM next with `bin/wuwei setup slack` and that typing the review channel ID
  sets it too), `Microsoft Teams` and `Discord` (`LATER`, `{'adapters.chat': 'none'}`),
  `None` (unchanged effect). Free text `_chat` (replaces `_channel`):
  `[CG][A-Z0-9]*[0-9][A-Z0-9]*` is a Slack channel id (unchanged effect); otherwise one tool
  name `[A-Za-z][A-Za-z0-9 .+-]{0,39}` that is not `calibrate.instruction_like` gives
  `{'adapters.chat': 'none'}`; anything else raises naming both forms. Hint:
  `a Slack review channel ID such as C0123ABCD, or another tool such as Email (not supported yet)`.
- The table invariant (2 to 4 choices, header at most 12) is unchanged.

### `cli/wuwei/commands/setup.py`

- `register`: `parser.add_argument('target', nargs='?', choices=('slack',), help='slack: connect the owner DM: token, pin, second factor, listener')`.
- `run`: inside the existing `try`, `return slack(confirm) if getattr(args, 'target', None) == 'slack' else _setup(args, confirm)`.
  The existing `except` arms give the same exit codes and reasons.
- `slack(confirm=None)`: refuse without a terminal
  (`OSError(integrity.HOST_TERMINAL)`, as `_setup`); `root = workspace.find_workspace()`;
  `code = connect(root, confirm)`; return
  `max(code, config.run(SimpleNamespace()))`.
- `connect(root, confirm=None)`, returning an exit code, one printed
  line per step:
  1. Token: `SLACK_BOT_TOKEN` already in the environment is kept (`SLACK_BOT_TOKEN: already
     set, kept`); else `getpass.getpass('Slack bot token (starts with xoxb-; Enter to skip): ')`.
     Empty: say where to find it (the Slack app's OAuth & Permissions page, Bot User OAuth
     Token; remote operation section 2) and to run `bin/wuwei setup slack` again, return 1.
     Not `xoxb-[A-Za-z0-9-]+`: the same hint without echoing the value, return 1.
  2. Channel: `SLACK_OWNER_DM_CHANNEL` kept when set; else `input(...)` naming where the
     `D...` id is shown. Empty or not `D[A-Z0-9]+`: hint, return 1. Both values are
     validated before anything is written.
  3. `env.write(root, new)` for the values typed, then `env.load(root)`; print
     `Saved SLACK_BOT_TOKEN and SLACK_OWNER_DM_CHANNEL to .wuwei/env (mode 0600)`.
  4. Pin: a valid `control_plane.owner` (`remote.PIN`) is kept; else
     `sender = _first_dm(root, channel, sleep)`. `None` (timed out): print the Messages Tab
     and `im:history` hint, return 1. A poll failure returns 2 with the adapter's reason and
     the same hint. Print `Message from <team>/<user>: pin it as control_plane.owner so only
     this sender can command WUWEI from the DM.`
  5. Settings `adapters.chat`, `adapters.inbound` = `"slack"` and the pin through
     `_edit('setup slack', 'Slack settings', confirm, change)`, where `change` is
     `calibrate.settle` plus `calibrate.apply` (as in `set_value`; an edit that is not a
     one-line assignment raises naming the key). A non-zero result is returned (declined is
     1, nothing else runs).
  6. TOTP: when `WUWEI_TOTP_SECRET` is unset,
     `base64.b32encode(secrets.token_bytes(20)).decode()`, `env.write`, `env.load`, and print
     the authenticator lines with
     `otpauth://totp/WUWEI:owner?secret=<secret>&issuer=WUWEI&algorithm=SHA1&digits=6&period=30`
     and "never paste it into a website"; else `WUWEI_TOTP_SECRET: already set, kept`.
  7. Listener: on `darwin` or `linux`, when `workspace.watch_unit(root, platform,
     name='listen')[1]` exists call `watch.service(SimpleNamespace(listen_action='uninstall',
     once=False, dry_run=False), 'listen', None)`, then the same with `'install'`; an
     `OSError` or `ValueError` prints `wuwei setup slack: listener: <reason>` with
     `bin/wuwei listen install` and makes the result 1. Other platforms: print that the
     listener runs with `bin/wuwei listen` in a terminal that stays open.
- `_first_dm(root, channel)`: `inbound = registry.load('inbound', {'adapters':
  {'inbound': 'slack'}})`; `start = int(workspace.now().timestamp())`; print `Send any
  message to the app in Slack now; waiting up to 5 minutes.`; up to
  `WAIT_SECONDS // POLL_SECONDS` polls of `inbound.poll(str(start), root=root)`: a non-zero
  exit returns it to the caller as unrun; the first event with `channel == channel` and
  `float(ts) >= start` gives its `sender`; else `time.sleep(POLL_SECONDS)` (tests monkeypatch `time.sleep`; no parameter). Constants
  `WAIT_SECONDS = 300`, `POLL_SECONDS = 3` with a `ponytail:` comment (fixed wait; a flag
  if owners need longer). The poll's own 300 s lookback is why the `start` filter exists.
- `_setup`: keep the interview answers (`picked = {}` before the interview,
  `picked = interview.ask(...)`, then `interview.record(..., picked)`). After `optional = []`:
  when `picked.get('chat')` maps to `adapters.chat = "slack"` through `interview.effects` and
  the applied config still has `adapters.inbound == "none"`, print `Slack: connecting your
  DM now (bin/wuwei setup slack)` and call `connect(root, confirm)`; a non-zero result adds
  `bin/wuwei setup slack` to `optional`. Doctor and the ending line run after, unchanged.
- `discover`: when the remote URL is not empty and not GitHub, append
  `{path}: {host} is not GitHub; WUWEI reads GitHub only today (other code hosts:
  {interview.BACKLOG})`, where `host` is the part after any scheme and `user@` and before
  the first `/` or `:`, or `its origin` when there is none. Never print the URL (it can
  carry credentials). The owed line is unchanged.

### Docs

- `docs/site/remote.md`:
  - Introduction: one sentence that `bin/wuwei setup slack` does the Slack part.
  - New `## Connect Slack in one command` before `## 1. Remote Control, no setup`: create
    the Slack app first (section 2), run `bin/wuwei setup slack` in a host terminal, then
    the five steps it takes and says (token and DM id to `.wuwei/env`; one DM message, the
    sender shown and pinned on your confirmation with both adapters; TOTP secret and the
    `otpauth://` URI; listener installed or restarted; `config check`). Run it again after
    editing `.wuwei/env`. Sections 2 to 5 are the same steps by hand, for reference.
  - Section 1, line 37: `How a phone answer becomes your outcome: section 7.`
  - Sections 2 to 5: one line each saying `setup slack` does this step; the manual text,
    the scope table, the Python one-liner and the `otpauth://` URI stay.
  - Section 7 from "The reply is recorded as" (line 335): two-way answers are your
    outcome, the `RECORDED` line verbatim, parked items resume, nothing on the host;
    one-way and `unsure` answers are evidence, the `NOTED` line verbatim, then the
    existing text about the first answer, nudges, `phone answers 1` and the host command,
    now scoped to one-way answers.
- `docs/site/daily.md` (lines 295-299) and `docs/site/configuration.md` (lines 555-558):
  the same rule in one sentence each; `phone answers` stays in daily.md section 5.

## What must not change

- `cli/wuwei/control_plane.py` and `cli/wuwei/listen.py` (no production caller of
  `poll_replies`; the listener reaches answers through `remote.handle`).
- The pin check (`remote.sender`), the `changed` refusal and page, `FACTOR`, `code_step`,
  `confirmation`, the vocabulary, `more`, `stop`, `escalate_new`.
- `decision.route`, `decision.answered`, `control_plane.pending`/`parse`/`render`, the
  `decision outcome` CLI path and its host confirmation, the MCP decision path.
- `guards/protect_state.py`: `('setup', '')` already makes every `setup ...` an owner
  action; `.wuwei/env` and the inbox stay protected as today.
- The Slack adapters, their four scopes, `registry`, `outward` and its default patterns.
- `status.py` and the nudge rules: an answered decision already drops out of
  `phone answers`.

## Constitution check

- I stdlib: `getpass`, `secrets`, `base64`, `time` only.
- II exits: `setup slack` 0/1/2 with a reason on every non-zero; the DM writer failure is
  exit 2 with FAILED.
- III one behaviour, one function: the owner outcome stays in `owner_outcome`; `.wuwei/env`
  gets one writer; the listener install stays in `watch.service`.
- IV test first: tasks.md orders each test before its change.
- V ponytail: two keyword arguments instead of a second writer; one positional target
  instead of a new command module; no new config, state or event.
- VII security: the token is read without echo, written only to the 0600 file and added
  to the redaction set by `env.load`; never printed or logged. A DM can record only a
  two-way door, only from the pinned sender, through the same checks as the host path.
