# Implementation Plan: decisions and health are visible on both ends

**Branch**: `273-remote-visibility` | **Date**: 2026-10-01 | **Spec**: spec.md

## Summary

Six small fixes, each at the one spot its callers already route through:

- Escalation (F3): one `remote.escalate_new(root, transport)` that sends every pending
  owner decision not yet escalated today; `remote._turn` and `listen.tick` call it.
- Answers (F4): `remote.handle` checks today's first `decision.replied` before recording;
  `status.scan` turns a replied route into a `decision.answered` row, which `nudges`,
  `status.line` and `lifecycle.session_start` show.
- Refused page (F9): `remote.refused` records the pin; `status.scan` drops it once the
  pin changed.
- Sessions (F8): `sessions.rows` carries `stopped`; `status.snapshot` skips it.
- Listener health (F6): `status.scan` collects `listen: clock` in its one pass and runs
  the watch rule for both names.
- Config check (F5): a `Control plane:` section, pin pattern shared with `remote.sender`.

Reused, not copied: `control_plane.pending`, `control_plane.escalate`, `remote._today`
(today's events), `remote._say`, `watch.health` (and its `name=` parameter),
`workspace.watch_unit(name=)`, `state.append_event`, `sessions.rows`,
`status.attention`, `workspace.load_config`, `outward.lint` (via `remote.dm`).

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Tests in process with the existing fakes:
`tests/test_remote.py` (`Transport`, `Runtime`, `ws`, `routed`, `remote_row`, `handled`,
`escalation`, `open_gate`), `tests/test_listen.py` (`case`, `Source`, `later`, `kinds`,
`config`), `tests/test_env_credentials.py` (`case` for `config check`),
`tests/test_sessions.py`, `tests/test_signal_status.py`. `WUWEI_NOW` fixes the clock.

## Constitution Check

- I stdlib only: nothing new imported beyond `re`/`os` already in use.
- II three-state: the tick exits 2 on an escalation that cannot run, with the reason
  printed; a conflicting answer is 1 (refused); `config check` pin findings are 1.
- III one behaviour, one function: escalation in `remote.escalate_new`, first-answer rule
  in `remote.handle` (helper `remote.replied`), answered/listen/refused display in
  `status.scan`, pin pattern in `remote.PIN`.
- IV test first: tasks.md orders every test before its implementation.
- V ponytail: no new module, no new command, no new config key, no new state key; one new
  event kind.
- VII security: DM sends still go through `remote.dm` (security check, outward lint,
  owner-only lint relaxation for a `D` channel). The pin value is never printed by
  `config check`; the TOTP secret value is never printed. `decision.escalated` is
  reserved to the listener, so a seat cannot suppress an escalation through
  `wuwei event`.

## Design

### 1. `cli/wuwei/remote.py`

a) Pin pattern constant, used by `sender` (line 101) and `config check`:

```python
PIN = r'[A-Z0-9]+/[UW][A-Z0-9]+'  # control_plane.owner: <team id>/<user id>
```

b) First DM answer for a decision today (reuses `_today`):

```python
def replied(root, identifier):
    """The option of today's first decision.replied for this id, else None."""
    return next((row['payload'].get('option') for row in _today(root)
                 if row['kind'] == 'decision.replied' and row['payload'].get('id') == identifier), None)
```

c) Escalation, replacing the loop at `_turn` lines 340-344:

```python
def escalate_new(root, transport):
    """Send each owner-pending decision the DM has not had today; record each send."""
    sent_ids = {row['payload'].get('id') for row in _today(root) if row['kind'] == 'decision.escalated'}
    code = 0
    for identifier in control_plane.pending(root):
        if identifier in sent_ids:
            continue
        sent = control_plane.escalate(identifier, root=root, transport=transport)
        if sent.exit == 1:
            sent = transport.dm(f'{identifier} is waiting in the workspace.', root=root)
        if sent.exit == 0:
            state.append_event('decision.escalated', {'id': identifier}, root=root)
        code = max(code, sent.exit)
    return code
```

In `_turn`, keep `before`/`new` (they feed the session row's `decisions` and the
`N decisions waiting` count) and replace the `for identifier in new:` loop with
`code = max(code, escalate_new(root, transport))`. The decisions still go out before the
`Session` line. Side effect by design: a turn also sends any host decision the tick has
not sent yet.

d) `handle`, refused branch (line 217): `state.append_event('remote.refused', {'id':
event['id'], 'pin': config['control_plane']['owner']}, root=root)`; bind
`config = workspace.load_config(root)` once where `sender(...)` is called (line 210).

e) `handle`, decision branch (lines 236-242), before `state.append_event('decision.replied', ...)`:

```python
first = replied(root, identifier)
if first is not None:
    if first != option:
        return _say(transport, root, ANSWERED.format(identifier=identifier, option=first), 1)
    return _say(transport, root, f'Recorded {identifier} option {option}. Confirm it on the host.', 0)
```

with the fixed line next to the other constants:

```python
ANSWERED = ('Not recorded: {identifier} already has option {option} from this DM. '
            'Record the outcome on the host to change it.')
```

It must pass `outward.lint(text, 'D1', config)` like the other fixed lines (add it to
`test_fixed_lines_pass_the_outward_lint` with `D-1`/`A` filled in). If the lint refuses a
word, rephrase; keep "already has option" and the first option in the text.

### 2. `cli/wuwei/listen.py` (`tick`, after the handling loop, inside the responder branch)

```python
if os.environ.get('SLACK_OWNER_DM_CHANNEL'):
    try:
        if remote.escalate_new(root, remote.TRANSPORT) == 2:
            code = 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f'listen escalate unmeasured: {exc}', flush=True)
        code = 2
```

Placed inside `if config['responder']['enabled']:` so the kill switch also stops
escalation. `import os` at the top. A send that returns 1 (nothing sent, the fallback
refused too) is left for the next tick and does not change the tick code, like a refused
command. Call through the module attribute `remote.TRANSPORT` so tests can monkeypatch
`remote.TRANSPORT.dm` as `test_issue_acceptance_stop_all_stops_every_session_in_one_tick`
already does.

### 3. `cli/wuwei/signal.py` and `cli/wuwei/commands/event.py`

Add `'decision.escalated'` to `SILENT` and `'decision.escalated': 'wuwei listen'` to
`EVENT_PRODUCERS`. (Every kind but `note` is already refused by `wuwei event`; the
producer entry gives the refusal its name.)

### 4. `cli/wuwei/commands/status.py`

`scan` (one pass, lines 26-140):

- Before the loop: `listen_clocks, replied, pin = [], {}, None` (use a sentinel for "pin
  not loaded yet").
- In the loop, next to `if kind == 'watch: clock': clocks.append(stamp)`:
  - `if kind == 'listen: clock': listen_clocks.append(stamp)`
  - `if kind == 'decision.replied' and isinstance(payload, dict): replied.setdefault(payload.get('id'), payload.get('option'))`
  - before `classify`: a `remote.refused` whose payload has `pin` is skipped (`continue`)
    when it differs from the current pin, loaded once lazily with
    `workspace.load_config(directory.parents[2])['control_plane']['owner']`. A payload
    without `pin` falls through and pages as today.
- Replace the watch health block (lines 107-115) with a loop over
  `(('watch', clocks), ('listen', listen_clocks))`: same unit check with
  `workspace.watch_unit(root, name=name)`, same `watch.health(root, stamps, name=name)`,
  row key `(f'{name}: health',)`, source `f'{name}: health'`, page for 1, nudge for 2, and
  state `{1: 'dead', 2: 'unmeasured'}.get(code, 'alive' if stamps else 'off')`. Keep the
  lazy `from wuwei import watch` and the line-107 watch-sweep filter as is.
- Decision loop (lines 125-129): when `replied.get(identifier)` is set, the row is
  `{'tier': 'nudge', 'source': 'decision.answered', 'lane': 'Decisions', 'reason':
  f'{identifier} answered from the phone: option {option}, confirm with decision outcome {identifier} {option}'}`;
  otherwise unchanged.
- Return `(rows, watch_state, listen_state)`. The only callers are `attention` (`[0]`) and
  `snapshot`.

`snapshot`:

- `sessions`: count rows with `not row['stale'] and 'stopped' not in row`.
- `active, result['watch'], result['listen'] = scan(...)`.
- `result['answered'] = [row['reason'] for row in active if row['source'] == 'decision.answered']`.
- After `config` is loaded (line 169): `if result['listen'] == 'off' and (config is None
  or config['adapters']['inbound'] == 'none'): result['listen'] = 'none'`.

`line`: after the watch part, `if data['listen'] not in ('alive', 'none'):
parts.append(f'listen {data["listen"]}')`; after the sessions part,
`parts.extend(data['answered'])`.

### 5. `cli/wuwei/sessions.py` (`rows`, line 67)

Add `**({'stopped': row['stopped']} if 'stopped' in row else {})` to the row dict.
`claim` is unchanged (remote sessions hold no claims).

### 6. `cli/wuwei/guards/lifecycle.py` (`session_start`, continuity `try`, after the wake notice)

```python
from wuwei.commands.status import attention
lines.extend(row['reason'] for row in attention(workspace.day_dir(root))
             if row['source'] == 'decision.answered')
```

Informational: the exit code is not raised. `attention` reads absent day state as defaults,
so a fresh day adds nothing and raises nothing. An error falls into the existing
`session continuity unmeasured` handler.

### 7. `cli/wuwei/commands/config.py` (`run`, after the `Owner:` section)

```python
if config['adapters']['inbound'] != 'none':
    from wuwei.remote import PIN
    pin = config['control_plane']['owner']
    print('Control plane:')
    if not pin:
        print('  control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)')
    elif not re.fullmatch(PIN, pin):
        print('  control_plane.owner: invalid (expected <team id>/<user id>)')
    else:
        print('  control_plane.owner: set')
    status = max(status, CLEAN if pin and re.fullmatch(PIN, pin) else FINDINGS)
    print('  WUWEI_TOTP_SECRET: ' + ('set' if os.environ.get('WUWEI_TOTP_SECRET') else
          'missing (confirm replies are the only second factor)'))
```

`import re` at the top.

### 8. Docs

- `docs/site/remote.md`:
  - Section 3: `config check` prints `control_plane.owner: missing (...)` until the pin is
    set; the `remote.refused` page clears once `control_plane.owner` is edited to a
    different value (the refusal records the pin it was checked against); a refusal while
    the pin is right stays paged until the day ends.
  - Section 4: `config check` reports `WUWEI_TOTP_SECRET: set` or `missing (confirm
    replies are the only second factor)`.
  - Section 5: `status --line` shows `listen dead` (and `wuwei nudges` a page), `listen
    unmeasured`, or `listen off` when the listener has not run today; nothing when alive.
  - Section 6: `bin/wuwei sessions` shows a `stopped` field; `status --line` counts live
    sessions only.
  - Section 7: the DM path covers every decision routed to the owner: raised by a `plan`
    session, by `bin/wuwei decision route` or `bin/wuwei pr act` on the host, or by a
    refused tool; host decisions arrive at the next listener poll, each once. After a
    DM answer, `bin/wuwei nudges`, `status --line` and session start show
    `D-3 answered from the phone: option B, confirm with decision outcome D-3 B`. A
    second, different answer gets `Not recorded: D-3 already has option B from this DM.
    Record the outcome on the host to change it.`; the first answer stands until the
    host outcome.
  - Section 8: replace "`listen dead` at session start is the only liveness signal" with
    session start and `status --line`, both on the host only.
- `docs/site/configuration.md`: `listen.dead_seconds` row ("reported dead at session
  start and in `status --line`"); the listener section's closing paragraph (lines
  354-357) adds the status line and nudges; the `config check` paragraph (line 367) adds
  the Control plane lines. `control_plane.owner` row: "Empty handles no command; `config
  check` reports it when `adapters.inbound` is set."
- `tests/test_docs.py::test_remote_runbook_matches_the_code`: add
  `remote.ANSWERED`-derived text (as written in the page) and `answered from the phone`
  to the checked phrases. Every backticked `section.key` in the page must be a SCHEMA key
  or an `EVENT_PRODUCERS` kind (`decision.escalated` is one after step 3). Only use
  `bin/wuwei <command>` for commands that exist (`decision`, `pr`, `nudges`, `status`,
  `sessions`, `config`).

## What must not change

- `control_plane.escalate`, `notify`, `parse`, `render`, `poll_replies`: untouched.
- `decision.route_owner`, `decision route`, `pr act`: they still only write the ledger.
- The `Session ... turn ended, N decisions waiting.` line and the order (decisions first).
- `remote.sender` behaviour (only the pattern moves to `PIN`).
- The remote factor rules, `stop`, `confirm`, the kill switch semantics for commands.
- `watch.health` itself, and the watch part of the status line (`watch off`, `watch dead`,
  `watch unmeasured`, nothing when alive).
- `sessions.claim` and stale semantics.
- The single pass over `events.jsonl` in `status.scan` (#210); no second read.
- SessionStart exit codes.

## Existing tests that change on purpose

- `tests/test_remote.py::test_issue_acceptance_changed_identity_is_refused_and_alerted`:
  the refused payload becomes `{'id': 'D1/1.000001', 'pin': 'T1/U1'}`.
- `tests/test_remote.py::test_fixed_lines_pass_the_outward_lint`: add `ANSWERED`.
- `tests/test_env_credentials.py::test_config_reports_missing_and_set`, the
  `inbound="slack"` row: its settings gain `[control_plane]\nowner="T1/U1"`, since an
  empty pin is now a finding when an inbound adapter is set.
- Any test asserting the exact `events(ws, 'decision.')` list after a turn now also sees
  `decision.escalated`; `payloads(ws, 'remote.')` is unaffected.

## Risks

- A seat running as the owner can still append to `events.jsonl` directly (design 9.1) and
  forge `decision.escalated`; the effect is a missed DM, while the host nudge still shows
  the decision. Accepted.
- An escalation that the outward lint refuses and whose fallback is refused too is retried
  every tick without sending; the fallback text is fixed and passes the lint, so this
  needs a lint change to happen.
