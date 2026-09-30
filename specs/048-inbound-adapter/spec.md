# Feature Specification: inbound adapter interface and redactor adapter

**Feature Branch**: `048-inbound-adapter`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #48, feat(adapters). Design sections 3.5, 8 and 15.2. Wave G (M5-lite):
one channel, Slack DMs polled with urllib; the Slack inbound adapter (#50) is the first
implementation and the listener (#49) is the first caller.

## Root cause (read on main, a61fe34)

This is a new port, not a regression. What exists today and why it does not cover the
issue:

- `cli/wuwei/registry.py:12-54` (`PARAMETERS`) declares no `inbound` and no `redactor`
  port, so `registry.load('inbound', ...)` raises `unknown adapter kind` and there is no
  `adapters/inbound/` or `adapters/redactor/` directory.
- `cli/wuwei/workspace.py:128-133` (`CONFIG['adapters']`) has no `inbound` or `redactor`
  default, so no configuration can select either.
- The only redaction today is `cli/wuwei/redact.py:77-106` (`redact`), written for the
  trace recorder. Line 96 already names "the M5 redactor port" as the durable path. It
  cannot serve inbound text: probed read-only on main,
  `redact.redact('call me on 07700 900123 please')` returns `'[REDACTED]'` (the whole
  message is lost, lines 102-105 replace the string), `redact.redact('mail me at
  a@b.co')` returns the text unchanged (no email pattern), and it reports no findings.
- Nothing writes an inbox: no `inbox` path or writer exists under `cli/wuwei/`.

The notes for this issue name no dry-run failure; there was nothing to reproduce beyond
the probe above.

## User Scenarios & Testing

### User Story 1 - Inbound text is redacted before it is stored (Priority: P1)

The owner connects an inbound source. Every message the source returns is stored in the
workspace inbox with phone numbers, email addresses and secrets replaced, and a record
says what kind of data was removed, without repeating it.

**Independent Test**: `python -m pytest -q tests/test_inbox.py`.

**Acceptance Scenarios**:

1. Given a message containing a phone number, when it is stored, then the stored event
   text has the number replaced by `[REDACTED]`, the rest of the message is kept, and a
   finding of kind `phone` is recorded in the day's events.
2. Given a message containing an email address or a secret (a token such as `xoxb-...`,
   or `password=...`), then that span is replaced and a finding of kind `email` or
   `secret` is recorded.
3. Given a message with nothing to redact, then it is stored unchanged and no finding is
   recorded.
4. Given the redactor cannot run or returns a malformed result, then nothing from that
   batch is stored and the call exits 2 with the reason.
5. Given an event that is not the normalised shape, then nothing from that batch is
   stored and the call exits 2.
6. The recorded finding never contains the redacted value.

### User Story 2 - The inbound port has an honest `none` (Priority: P1)

A workspace without an inbound source configured polls nothing and says so.

**Independent Test**: `python -m pytest -q tests/test_adapters.py -k none_call`.

**Acceptance Scenarios**:

1. Given `adapters.inbound = "none"` (the default), when the inbound source is polled,
   then no events are returned (data is None, exit 2, reason `unmeasured`), an
   `adapter: none` event with `kind: inbound, call: poll` is recorded, and the argument is
   not logged.

### User Story 3 - The ports are declared once and every adapter satisfies them (Priority: P1)

**Independent Test**: `python -m pytest -q tests/test_adapters.py`.

**Acceptance Scenarios**:

1. The registry declares `inbound.poll(since)` and `redactor.redact(text)`; every module
   under `adapters/inbound/` and `adapters/redactor/` has exactly those operations with
   `root` as the last parameter.
2. A fresh workspace config selects `inbound = "none"` and `redactor = "builtin"`, and the
   registry loads both.

### User Story 4 - Agents cannot forge the inbox (Priority: P2)

**Independent Test**: `python -m pytest -q tests/test_inbox.py -k protected`.

**Acceptance Scenarios**:

1. Given a seat that writes or appends to `.wuwei/inbox/inbox.jsonl` with a file tool or a
   shell redirect, then the state guard refuses it (exit 1), like other workspace state.

### Edge Cases

- An international number (`+44 20 7946 0958`) is one phone finding and the `+` is
  removed with it.
- Digit runs with fewer than 9 digits (`PR 1234 at 10:30`, `D-3`) are not phone numbers.
- A field-style secret (`password=hunter2`) is redacted up to the next whitespace, not
  only its first character.
- One message with two phone numbers yields two `phone` findings.
- Non-string text passed to the redactor is exit 2, never stored.

## Requirements

### Functional Requirements

- **FR-001**: The registry MUST declare the `inbound` port with `poll(since)` and the
  `redactor` port with `redact(text)`, each taking `root` last like every port.
- **FR-002**: `adapters/inbound/none.py` MUST record that it did nothing and return no
  events, through the shared `registry.record_none` (measurement, reason `unmeasured`).
- **FR-003**: `adapters/redactor/builtin.py` MUST replace each phone number, email
  address and secret span in the text with `[REDACTED]`, keep the rest of the text, and
  return `{text, findings}` where `findings` is one `{'kind': 'phone' | 'email' |
  'secret'}` per replaced span. Exit 0 with no findings, exit 1 with findings, exit 2 for
  non-string input.
- **FR-004**: The builtin redactor MUST reuse the existing patterns in
  `cli/wuwei/redact.py` (`PHONE`, `SECRET`, `REDACTED`) and add only an email pattern.
- **FR-005**: A single core function MUST be the only writer of
  `.wuwei/inbox/inbox.jsonl`. It validates that every event is exactly the normalised
  shape `{id, source, channel, thread, sender, text, ts}` (all strings; `id`, `source`,
  `channel`, `sender`, `ts` nonempty), passes each text through the configured redactor,
  and only when every event in the batch validated and redacted does it append the
  events with redacted text and record one `inbox.redacted` event per stored event that
  had findings, carrying the event id, source and the finding kinds.
- **FR-006**: Config defaults MUST be `adapters.inbound = "none"` and
  `adapters.redactor = "builtin"`; both are validated like other adapter selections.
- **FR-007**: The state guard MUST treat `.wuwei/inbox/` like other protected workspace
  state.
- **FR-008**: Existing trace and output redaction (`cli/wuwei/redact.py`) MUST NOT
  change behaviour.

### Key Entities

- **Inbound event**: `{id, source, channel, thread, sender, text, ts}`, all strings.
  `thread` is empty when the message is not in a thread. `id` is unique per source.
- **Redaction result**: `{text, findings}`; `findings` is a list of `{kind}` with kind in
  `phone`, `email`, `secret`. Never carries the matched value.
- **Inbox**: `.wuwei/inbox/inbox.jsonl`, append-only, one normalised event per line with
  redacted text.

## Success Criteria

- **SC-001**: A stored message never contains a phone number, email address or token
  that the built-in patterns match (tested per kind).
- **SC-002**: The adapter contract test covers both new ports with one row per operation
  and no port-specific contract code.
- **SC-003**: The full suite passes; no existing test changes except the rows and default
  maps that enumerate ports and config defaults.

## Assumptions

- **No `receive(request)` in this wave.** The notes (binding) say to design the port from
  what Slack polling needs and nothing more. `receive` exists only for webhook sources
  (WhatsApp, 15.6), which wave G excludes. Deferred to the first webhook adapter.
- **No `inbound.reply(thread, text)` in this wave.** A reply to a Slack message is
  `chat.post(event.channel, text, event.thread)` on the existing chat port, which already
  carries the outward guard, the voice checks and the drafts queue. A second outward path
  on the inbound port would duplicate that and need its own guard. This deviates from the
  issue's scope line and from the section 8 table; the event already carries `channel`
  and `thread`, so a caller has everything `reply` would take. Revisit when an inbound
  source cannot be answered through a chat adapter.
- **`poll(since)` contract.** `since` is the source's own cursor string (for Slack, a
  message `ts`; empty string for the first poll). `poll` returns `Result(0, [event, ...])`
  with events in normalised shape and unredacted text; the caller computes the next cursor
  from the returned `ts` values. Dedup by id and the persisted cursor are #49.
- **The redactor has no `none` adapter.** Design 3.5 allows a fake instead of `none` for
  ports that must answer; the inbox must never hold unredacted text, so a `none`
  redactor could only fail closed. The builtin adapter is the default and the only
  implementation until WUMING ships a CLI.
- **Findings are exit 1.** Following constitution II, a redaction that found something is
  exit 1 with the redacted text still in `data`; callers store on 0 or 1 and fail closed
  on 2.
- **Phone rule.** A phone span is the existing `PHONE` pattern with an optional leading
  `+`, counted only when it holds 9 or more digits. Unlike the trace recorder, an
  all-digit run (`07700900123`) counts: in a message, a false positive costs readability,
  a miss leaks personal data. A 10-digit epoch timestamp in message text is redacted too.
- **The secret rule over-redacts field words.** `redact.SECRET` treats `message:`,
  `text:`, `auth:` and similar assignments as secrets, so `message: can you look` becomes
  `[REDACTED] you look`. Accepted and marked with a `ponytail:` comment; the upgrade path
  is a message-specific secret list or WUMING.
- **The inbox lives at `.wuwei/inbox/inbox.jsonl`.** Design 15.2 says `inbox/inbox.jsonl`;
  every other workspace file is under `.wuwei/`.
- **Storage is in scope, the listener is not.** The acceptance scenario is about the
  stored event, so this issue ships the single inbox writer that redacts. The poll loop,
  dedup, cursor, clock line and kill switch are #49.
- **A partial batch after an I/O error is possible.** Validation and redaction of the
  whole batch happen before the first write, so bad input stores nothing; an `OSError`
  in the middle of appending can leave earlier events stored and returns exit 2. #49's
  dedup by id makes the retry safe.
- **No new config keys in the shipped template.** Defaults apply; the two keys are
  documented in `docs/site/configuration.md` and `docs/site/adapters.md`.

## Deferred

- `inbound.receive(request)` and webhook signature checks: first webhook adapter (not
  wave G).
- Slack inbound polling and its credentials in `config check`: #50.
- Dedup by id, cursor per source, poll loop: #49.
- WUMING redactor adapter: after WUMING ships a CLI.
