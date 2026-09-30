# Implementation Plan: phone answers as one status segment, an ack for a refused-sender page, and the section 3 quote

**Branch**: `276-remote-polish` | **Date**: 2026-10-01 | **Spec**: spec.md

## Summary

Three small fixes, each at the one spot its callers already route through:

- Status line (finding 1): `status.line` prints `phone answers N` in place of the
  reasons. The DM `status` reply gets it for free (it calls `status.line`).
- Refused page (finding 2): `remote.acknowledge(root)` behind a new `wuwei remote ack`
  owner action, reusing `integrity._host_confirm`; `status.scan` keys refusals by id and
  drops the acknowledged ones in its one pass.
- Section 3 quote (finding 3): the missing-pin line becomes one constant in
  `commands/config.py`; the docs test checks the page against it.

Reused, not copied: `integrity._host_confirm` and `integrity.HOST_TERMINAL` (#227),
`guards/protect_state._OWNER_ACTIONS` (#222), `remote._today`, `state.append_event`,
the `decision.decided` pop pattern and the id-keyed rows in `status.scan`,
`EVENT_PRODUCERS`, `signal.SILENT`, the `__main__` exception-to-exit-2 path.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Tests in process with the existing fakes:
`tests/test_remote.py` (`ws`, `event`, `events`, `payloads`, `Transport`, `remote()`,
`refused_pages`, `OWNER`), `tests/test_signal_status.py` (`day`, `NOW`, `ROUTED`),
`tests/test_owner_actions.py` (`ACTIONS`, `places`, `bash`), `tests/test_env_credentials.py`
(`case`, `write_env`), `tests/test_docs.py`, `tests/test_state_allowlist.py`.
`WUWEI_NOW` fixes the clock. No tty in tests: monkeypatch `integrity._host_confirm`, or
monkeypatch `builtins.open` to raise `OSError` for `/dev/tty` as
`tests/test_decision.py::test_owner_outcome_without_a_terminal_names_the_owner_action`
does.

## Constitution Check

- I stdlib only: `hashlib` only, already used by `state.recover`.
- II three-state: `remote ack` exits 0 done or nothing to do, 1 declined, 2 without a
  terminal or on a read error (the `__main__` handler turns the `OSError` into
  `wuwei remote: <reason>` and exit 2).
- III one behaviour, one function: acknowledgement in `remote.acknowledge`; display in
  `status.scan` and `status.line`; the missing-pin text in `config.PIN_MISSING`.
- IV test first: tasks.md orders every test before its implementation.
- V ponytail: one new command module (the CLI discovers commands by module; there is no
  `remote` group to extend), one new event kind, one constant. No new state key, no new
  config key, no new helper module.
- VII security: the command is an owner action (agent tools refused, typed digest on
  `/dev/tty`); the event is reserved to its producer; the ack names ids, so a new
  refusal after it pages again.

## Design

### 1. `cli/wuwei/commands/status.py`

a) `line` (line 241): replace `parts.extend(data['answered'])` with

```python
if data['answered']:
    parts.append(f'phone answers {len(data["answered"])}')
```

`snapshot` keeps `result['answered']` (the list of reasons, used by `status --json`).

b) `scan`, in the event loop, next to the `decision.decided` branch (before the `SILENT`
check, so it runs even though the kind is silent):

```python
if kind == 'remote.acknowledged' and isinstance(payload, dict):
    for identifier in payload.get('ids', []):
        current.pop(('remote.refused', identifier), None)
    continue
```

c) `scan`, the key rule (line 104): add `'remote.refused'` to the id-keyed kinds:

```python
elif kind in ('decision.one_way', 'draft.created', 'remote.refused') and isinstance(payload, dict):
    key = (kind, payload.get('id', number))
```

The pin filter above it (lines 73-77) is unchanged. Still one pass over `events.jsonl`.
A non-hashable id inside `ids` raises `TypeError`, which `status.run` already reports as
`WUWEI ? unmeasured` (fail closed); no extra validation.

### 2. `cli/wuwei/remote.py` (after `stop`, or next to `replied`)

```python
def acknowledge(root):
    """Owner action: clear today's refused-sender pages after host confirmation; (code, message)."""
    from hashlib import sha256
    from wuwei import integrity
    rows = _today(root)
    done = {identifier for row in rows if row['kind'] == 'remote.acknowledged'
            for identifier in row['payload'].get('ids', [])}
    ids = [row['payload']['id'] for row in rows if row['kind'] == 'remote.refused'
           and row['payload'].get('id') and row['payload']['id'] not in done]
    if not ids:
        return 0, 'remote ack: no refused sender message today'
    token = sha256('\n'.join(ids).encode()).hexdigest()[:12]
    if not integrity._host_confirm(token, prompt=f'Acknowledge the refused sender messages '
                                   f'{", ".join(ids)} on this host. To confirm, type:'):
        return 1, 'remote ack: owner confirmation declined'
    state.append_event('remote.acknowledged', {'ids': ids}, root=root)
    return 0, f'remote ack: acknowledged {len(ids)} refused sender messages'
```

Notes for the builder:

- Call `integrity._host_confirm` through the module attribute (lazy import) so tests can
  monkeypatch it, as `commands/decision.py` and `commands/state.py` do.
- Do not catch the `OSError` from `_host_confirm`; `__main__` prints
  `wuwei remote: this is an owner action: run it in a host terminal` and returns 2.
- A refused row without `id` is skipped. Keep the event order (deterministic digest).
- No re-check after the prompt: the event lists exactly the confirmed ids.

### 3. `cli/wuwei/commands/remote.py` (new, discovered by `__main__` by module name)

```python
"""Owner actions for the remote control plane, run in a host terminal."""

import sys

from wuwei import remote, workspace


def register(subparsers):
    parser = subparsers.add_parser('remote', help='Owner actions for the remote control plane')
    actions = parser.add_subparsers(dest='action', required=True)
    actions.add_parser('ack', help="Acknowledge today's refused-sender pages (owner, host terminal)")
    parser.set_defaults(func=run)


def run(args):
    code, message = remote.acknowledge(workspace.find_workspace())
    print(message, file=sys.stderr if code else sys.stdout)
    return code
```

### 4. `cli/wuwei/signal.py` and `cli/wuwei/commands/event.py`

Add `'remote.acknowledged'` to `SILENT` (so `wuwei signal` and any other classifier call
treat it as silent), and `'remote.acknowledged': 'owner host wuwei remote ack'` to
`EVENT_PRODUCERS` as its own entry (not in the `remote.*` comprehension, whose producer
is `wuwei listen`). `tests/test_state_allowlist.py::test_reader_inventory_cannot_be_written_generically`
picks the kind up automatically from the `kind == 'remote.acknowledged'` comparisons.

### 5. `cli/wuwei/guards/protect_state.py` (`_OWNER_ACTIONS`, line 44)

```python
# An acknowledged refusal stops paging, so a seat could silence an impostor alert.
('remote', 'ack'): 'Remote acknowledgements require the owner terminal, outside agent tools.',
```

`_OWNER_GROUPS`, `_OWNER_VERBS` and the relevance regexes derive from the table; nothing
else changes in the guard.

### 6. `cli/wuwei/commands/config.py`

Module constant, used by the missing branch (lines 68-70):

```python
PIN_MISSING = 'control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)'
```

```python
print('Control plane:\n  ' + ('control_plane.owner: set' if valid else
      'control_plane.owner: invalid (expected <team id>/<user id>)' if pin else PIN_MISSING))
```

Printed output stays byte-identical.

### 7. Docs

- `docs/site/remote.md`:
  - Section 3, line 103: quote the full line, "`bin/wuwei config check` prints
    `control_plane.owner: missing (<team id>/<user id>; see remote operation section 3)`
    and exits 1".
  - Section 3, the refused bullet (lines 128-133): keep the pin-edit sentence; replace
    "A refusal while the pin is right stays paged until the day ends." with: a refusal
    while the pin is right stays paged until you run `bin/wuwei remote ack` in a host
    terminal: it lists today's refused message ids, asks you to type a digest and records
    a `remote.acknowledged` event; a later refusal pages again; agent tools cannot run
    it; without a terminal it exits 2. Otherwise the page ends with the day.
  - Section 7, lines 312-315: `bin/wuwei nudges` and session start show
    `D-3 answered from the phone: option B, confirm with decision outcome D-3 B`;
    `status --line` and the DM `status` reply count them as `phone answers 1`. The rest
    of section 7 (decision and draft owner commands) is unchanged.
- `docs/site/configuration.md` (lines 359-361): nudges and session start show
  "D-n answered from the phone"; the status line counts them as `phone answers N`.
- `docs/site/reference.md`, host terminal actions table: row
  `| \`bin/wuwei remote ack\` | yes |`.
- `docs/site/concepts.md`, host terminal actions list: add `wuwei remote ack`.
- `tests/test_docs.py::test_remote_runbook_matches_the_code`: replace the phrase
  `'control_plane.owner: missing'` with `PIN_MISSING` imported from
  `wuwei.commands.config`, and add `'phone answers 1'`, `'bin/wuwei remote ack'` and
  `'remote.acknowledged'`. Assert the constant sits in section 3 (the `pin` slice already
  computed in the test), not just anywhere on the page.

Every backticked `section.key` in remote.md must be a SCHEMA key or an `EVENT_PRODUCERS`
kind (`remote.acknowledged` is one after step 4); every `bin/wuwei <command>` must be a
file under `cli/wuwei/commands/` (`remote.py` after step 3).

## What must not change

- `status.scan` stays one pass over `events.jsonl`; `status --json` keeps `answered` as
  the list of reasons; `nudges` rows and SessionStart lines are unchanged.
- The #273 pin rule: a refusal whose recorded pin differs from the current pin does not
  page.
- `remote.handle`, `remote.sender`, the `remote.refused {id, pin}` payload, the DM texts.
- `integrity._host_confirm` itself and the other owner actions.
- `config check` output bytes and exit codes.
- The order of the other status line parts.

## Existing tests that change on purpose

- `tests/test_signal_status.py::test_issue_acceptance_a_phone_answer_shows_on_the_host`:
  the `status --line` check becomes `('phone answers 1' in text) == bool(expected)` and
  `reason not in text`; the `nudges` and `--json` checks stay.
- `tests/test_env_credentials.py::test_issue_acceptance_empty_pin_is_a_config_finding`:
  the empty-pin row asserts the full `PIN_MISSING` line.
- `tests/test_docs.py::test_remote_runbook_matches_the_code`: as in section 7 above.
- `tests/test_owner_actions.py`: `ACTIONS` gains `('remote', 'ack')` (IDS derive from its
  length).

## Risks

- `remote` and `ack` become owner relevance words: a command naming the CLI word plus
  both tokens is parsed by the owner-action rule. `bin/wuwei steward ack remote-fix-3`
  parses to the pair `('steward', 'ack')` and passes; add it and `git remote -v` to the
  ordinary-work table to pin that.
- pytest's `tmp_path` holds the test name; a test named with both `_remote_` and `_ack_`
  plus a CLI path in a guard payload could turn relevant. Name new guard tests without
  that pair (the `IDS` comment in `tests/test_owner_actions.py` already warns of this).
- A seat running as the owner can still append `remote.acknowledged` to `events.jsonl`
  directly (design 9.1); accepted, as for `decision.escalated` in #273.
