# Implementation Plan: inbound adapter interface and redactor adapter

**Branch**: `048-inbound-adapter` | **Spec**: `specs/048-inbound-adapter/spec.md`

## Summary

Declare two ports in the registry (`inbound.poll(since)`, `redactor.redact(text)`), ship
`adapters/inbound/none.py` and `adapters/redactor/builtin.py`, add their config defaults,
and add one core function, `inbox.store`, that is the only writer of the inbox and the
one place inbound text passes through the redactor. The builtin redactor reuses the
patterns already in `cli/wuwei/redact.py`. Guard the inbox path in the existing state
guard. Two doc rows each in two pages.

## Technical Context

Python 3.11+, stdlib only at runtime, pytest for tests. No network, no subprocess: the
none adapter records through `registry.record_none`, the builtin redactor is pure regex,
the store writes through `state.append_jsonl` and `state.append_event`.

## Constitution Check

- I Stdlib only: yes (`re`).
- II Three-state exits: none poll is exit 2 `unmeasured`; redactor 0 clean, 1 findings,
  2 non-string; store 0 stored clean, 1 stored with findings, 2 nothing stored (bad
  event, redactor failure) or I/O error.
- III One behaviour, one function: redaction of inbound text lives only in the redactor
  adapter; storage lives only in `inbox.store`; no caller redacts or writes the inbox
  itself.
- IV Test first: every task pair in tasks.md is test then code.
- V Ponytail: no abstract base, no `receive`, no `reply`, no redactor `none`, no new
  template keys, no new helper for appends or events. Patterns reused, not copied.
- VII Security: text is redacted before it is written; findings carry kinds only; a
  redactor failure stores nothing; agents cannot write the inbox through the tools the
  state guard sees.

## Design

### 1. `cli/wuwei/registry.py` (PARAMETERS, lines 12-54)

Add two entries:

```python
'inbound': {'poll': ('since',)},
'redactor': {'redact': ('text',)},
```

`INTERFACES`, `known`, `validate` and `load` need no change.

### 2. `adapters/inbound/none.py` (new)

```python
"""No inbound source configured."""

from wuwei import registry


def poll(since, *, root=None):
    return registry.record_none('inbound', 'poll', root)
```

Signature must be `(since, root)` per `test_module_contracts`; follow `adapters/chat/none.py`
(`root` keyword-only is fine, the test reads parameter names).

### 3. `adapters/redactor/builtin.py` (new)

Reuse `wuwei.redact.PHONE`, `wuwei.redact.SECRET` and `wuwei.redact.REDACTED`. Add one
email pattern. Order is phone, email, secret so an international number is a `phone`
finding, not a `secret` one (`SECRET` also matches `+\d...`).

```python
PATTERNS = (
    ('phone', re.compile(r'\+?' + redact.PHONE.pattern)),
    ('email', re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')),
    # ponytail: the trace SECRET list also catches field words such as `message:`;
    # a message-specific list or WUMING replaces it.
    ('secret', re.compile(rf'(?:{redact.SECRET.pattern})\S*', re.I)),
)


def redact(text, *, root=None):
    if not isinstance(text, str):
        return Result(2, None, 'redactor.builtin: text must be a string')
    findings = []
    def replace(kind):
        def sub(match):
            if kind == 'phone' and sum(c.isdigit() for c in match[0]) < 9:
                return match[0]
            findings.append({'kind': kind})
            return redact.REDACTED
        return sub
    for kind, pattern in PATTERNS:
        text = pattern.sub(replace(kind), text)
    return Result(1 if findings else 0, {'text': text, 'findings': findings})
```

Why the `\S*` suffix on `SECRET`: its field alternatives stop after the first character
of the value (`password=h`); span replacement must cover the whole token. The existing
`redact.redact` never needed that because it drops the whole string. The name `redact`
collides with the module import; import it as `from wuwei import redact as patterns` or
similar. Verified in memory on main with this exact logic:

| input | text | findings |
| --- | --- | --- |
| `call me on +44 20 7946 0958 today` | `call me on [REDACTED] today` | phone |
| `ring 07700900123` | `ring [REDACTED]` | phone |
| `mail a.b@example.com` | `mail [REDACTED]` | email |
| `token: xoxb-123-abc rest` | `[REDACTED] rest` | secret |
| `password=hunter2 ok` | `[REDACTED] ok` | secret |
| `approve D-3` | unchanged | none |
| `PR 1234 at 10:30` | unchanged | none |

### 4. `cli/wuwei/workspace.py` (CONFIG adapters, lines 128-133)

Add `"inbound": (str, "none"), "redactor": (str, "builtin")`. `load_config` already
validates every adapter name through `registry.validate`.

### 5. `cli/wuwei/inbox.py` (new, the only inbox writer)

```python
"""The workspace inbox: normalised inbound events, redacted before they are stored."""

from wuwei import registry, state
from wuwei.registry import Result

FIELDS = ('id', 'source', 'channel', 'thread', 'sender', 'text', 'ts')
REQUIRED = ('id', 'source', 'channel', 'sender', 'ts')


def store(root, config, events):
    ...
```

Behaviour, in order:

1. `events` must be a list; each event a dict whose keys are exactly `FIELDS`, every
   value a `str`, every `REQUIRED` value nonempty. Any failure: return
   `Result(2, None, 'inbox: malformed event')` before any write. Never echo the event.
2. `redactor = registry.load('redactor', config)`; for each event call
   `redactor.redact(event['text'], root=root)`. Accept only `exit in (0, 1)` with
   `data` a dict holding a `str` `text` and a `list` `findings` of dicts with a `str`
   `kind`. Otherwise return `Result(2, None, result.reason or 'inbox: redactor returned
   malformed data')` before any write.
3. For each event: `state.append_jsonl(root / '.wuwei' / 'inbox' / 'inbox.jsonl',
   {**event, 'text': redacted_text})`; if it had findings,
   `state.append_event('inbox.redacted', {'id': event['id'], 'source': event['source'],
   'findings': [f['kind'] for f in findings]}, root)`.
4. `OSError`/`ValueError` from a write: `Result(2, None, f'inbox: could not store: {exc}')`.
5. Return `Result(1 if any findings else 0, len(events))`.

`state.append_jsonl` already creates `.wuwei/inbox/`, locks `state.lock` in that
directory, writes the line atomically and leaves the file `0444`.

### 6. `cli/wuwei/guards/protect_state.py` (`_protected_name`, line 173)

Extend the prefix check: `if tail[:1] in (('integrity',), ('.git',), ('ziran',), ('inbox',)):`.
This covers file tools and the shell redirect path, which both route through `_protected`.

### 7. `cli/wuwei/commands/event.py` (`EVENT_PRODUCERS`)

Add `'inbox.redacted': 'the inbox store'` (there is no `wuwei inbox` command; `inbox.store` is a core function) so a forged `wuwei event inbox.redacted`
names its producer. The kind is already reserved (only `note` is free); this is the
message only.

`cli/wuwei/signal.py`: `inbox.redacted` is in `SILENT` (a redaction is the port working;
the owner has nothing to act on). `tests/test_signal_status.py` requires every emitted kind
to have an intended tier.

### 8. Docs

- `docs/site/adapters.md`: add rows `| inbound | none | none |` and
  `| redactor | builtin | builtin |`; change the sentence "Other ports in the design,
  including inbound messaging and control planes, are **planned**" so it no longer calls
  inbound planned (control planes still are), and add one sentence: inbound text is
  redacted by the redactor port before it is stored in `.wuwei/inbox/inbox.jsonl`.
- `docs/site/configuration.md`: rows for `adapters.inbound` (`"none"`, inbound source:
  none; Slack arrives with #50, so say "none" only) and `adapters.redactor`
  (`"builtin"`, built-in patterns for phone numbers, emails and secrets).

## Shared helpers reused

- `registry.record_none` for the none poll (event, stderr line, exit 2).
- `registry.Result` for every return.
- `wuwei.redact.PHONE`, `SECRET`, `REDACTED` for the patterns.
- `state.append_jsonl` for the inbox line, `state.append_event` for the finding record.
- `registry.load` with the validated config selection.

## Must not change

- `cli/wuwei/redact.py`: trace, event and output redaction keep their behaviour (whole
  string replacement, the all-digit exclusion). Do not move patterns out of it.
- `adapters/chat/*`, `cli/wuwei/outward.py`, `cli/wuwei/drafts.py`: replies stay on the
  chat port.
- `templates/workspace/config.toml`: no new keys (test_docs requires every template key
  to be documented; defaults suffice).
- The existing `test_none_call` table logic; only rows and filters change.

## Test plan

- `tests/test_adapters.py`:
  - `CALLS`: add `('inbound', 'poll', ('since',), True)` and
    `('redactor', 'redact', ('text',), True)`. `test_module_contracts` then covers both.
  - `test_none_call` filter: add `'redactor'` to the excluded kinds (no none adapter, like
    `vcs`). The inbound row runs through the existing table and proves the second
    acceptance scenario: exit 2, data None, `unmeasured`, one `adapter: none` event per
    call with `kind: inbound, call: poll`, argument not logged.
  - `test_registry_loads_config_selection`: add `'redactor': 'builtin'` to the expected
    map.
- `tests/test_workspace.py:162-165`: add `'inbound': 'none', 'redactor': 'builtin'` to
  the expected defaults.
- `tests/test_inbox.py` (new): a workspace from `tmp_path` with `.wuwei/config.toml`
  empty, `WUWEI_WORKSPACE` and `WUWEI_NOW` set, config from `workspace.load_config`.
  - Redactor table test over the rows in section 3, asserting `(exit, text, kinds)`, plus
    two phone numbers giving two findings and non-string input giving exit 2.
  - First acceptance scenario: `inbox.store` with one event whose text holds a phone
    number; the inbox line has the redacted text and the other six fields unchanged; the
    day's `events.jsonl` has one `inbox.redacted` event with the id, source and
    `['phone']`; the number appears in neither file; result exit 1.
  - Clean text: stored unchanged, no `inbox.redacted` event, exit 0.
  - Malformed events (missing key, extra key, non-string value, empty id, not a list):
    exit 2 and no inbox file.
  - Redactor failure: monkeypatch `registry.load` to return a module-like object whose
    `redact` returns `Result(2, None, 'down')`, and one returning malformed data: exit 2,
    no inbox file, reason carried.
  - `protected`: `check_file` Write to `.wuwei/inbox/inbox.jsonl` and `check_bash`
    `echo x >> .wuwei/inbox/inbox.jsonl` both return 1.
- Full suite: `python -m pytest -q`.
