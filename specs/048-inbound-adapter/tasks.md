# Tasks: inbound adapter interface and redactor adapter

Test first: every implementation task follows the test task that must fail before it.
Run tests with `python -m pytest -q <file>` from the repository root.

## Setup

- [X] T001 Probe read-only on main: no `inbound` or `redactor` port in
  `cli/wuwei/registry.py`; `redact.redact` drops a whole message with a phone number and
  keeps an email address (spec, Root cause).
- [X] T002 Write spec.md, plan.md and tasks.md.
- [X] T003 Run the full suite and confirm it is green before any change.

## US3: the ports are declared and every adapter satisfies them

- [X] T004 Test: in `tests/test_adapters.py` add `('inbound', 'poll', ('since',), True)`
  and `('redactor', 'redact', ('text',), True)` to `CALLS`; add `'redactor'` to the kinds
  excluded from `test_none_call`; add `'redactor': 'builtin'` to the expected map in
  `test_registry_loads_config_selection`. In `tests/test_workspace.py:162-165` add
  `'inbound': 'none', 'redactor': 'builtin'` to the expected adapter defaults. Run and
  see `test_module_contracts`, `test_none_call[inbound-poll...]`,
  `test_registry_loads_config_selection` and the workspace defaults test fail.
- [X] T005 Implement: `PARAMETERS['inbound']` and `PARAMETERS['redactor']` in
  `cli/wuwei/registry.py`; `adapters/inbound/none.py` (`poll` through
  `registry.record_none('inbound', 'poll', root)`); a first `adapters/redactor/builtin.py`
  with `redact(text, *, root=None)`; the two defaults in `CONFIG['adapters']` in
  `cli/wuwei/workspace.py`. T004 passes.

## US2: `none` inbound returns no events and records that it did nothing

- [X] T006 Covered by the `inbound` row of `test_none_call` added in T004 (exit 2, data
  None, reason `unmeasured`, one `adapter: none` event per call with `kind: inbound`,
  `call: poll`, argument absent from `events.jsonl`). Confirm it failed before T005 and
  passes after; no extra test.

## US1: inbound text is redacted before it is stored

- [X] T007 Test: in `tests/test_inbox.py` (new) a table test of
  `adapters.redactor.builtin.redact` over the plan's section 3 rows asserting
  `(exit, text, [kinds])`, plus two phone numbers in one message giving two `phone`
  findings and `redact(None)` giving exit 2. Run and see it fail (the T005 stub does not
  redact).
- [X] T008 Implement the patterns and `redact` in `adapters/redactor/builtin.py`, reusing
  `wuwei.redact.PHONE`, `SECRET` and `REDACTED`, with the `ponytail:` comment on the
  secret pattern. T007 passes.
- [X] T009 Test: in `tests/test_inbox.py`, `inbox.store(root, config, events)`:
  - one event with a phone number: the line in `.wuwei/inbox/inbox.jsonl` has redacted
    text and the other six fields unchanged; the day's `events.jsonl` has one
    `inbox.redacted` event `{'id', 'source', 'findings': ['phone']}`; the number is in
    neither file; exit 1.
  - clean text: stored unchanged, no `inbox.redacted` event, exit 0.
  - malformed input (not a list, missing key, extra key, non-string value, empty `id`):
    exit 2, no inbox file.
  - redactor returning `Result(2, None, 'down')` and one returning malformed data
    (monkeypatch `registry.load`): exit 2, no inbox file, reason carried.
  Run and see them fail (`wuwei.inbox` missing).
- [X] T010 Implement `cli/wuwei/inbox.py` (`FIELDS`, `REQUIRED`, `store`) per plan
  section 5. T009 passes.

## US4: agents cannot forge the inbox

- [X] T011 Test: in `tests/test_inbox.py`, `test_inbox_is_protected`: `check_file` with a
  Write to `.wuwei/inbox/inbox.jsonl` and `check_bash` with
  `echo x >> .wuwei/inbox/inbox.jsonl`, both with `cwd` the workspace, return 1. Run and
  see it fail.
- [X] T012 Implement: add `('inbox',)` to the prefix tuple in `_protected_name`,
  `cli/wuwei/guards/protect_state.py:173`; add `'inbox.redacted': 'the inbox store'` to
  `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py`. T011 passes.

## Docs and finish

- [X] T013 `docs/site/adapters.md`: rows for `inbound` (none, default none) and
  `redactor` (builtin, default builtin); inbound no longer listed as planned; one sentence
  on redaction before the inbox. `docs/site/configuration.md`: rows for
  `adapters.inbound` and `adapters.redactor`. Run `python -m pytest -q tests/test_docs.py`.
- [X] T014 Run the full suite (`python -m pytest -q`); everything passes. Check every
  file written for em-dashes, emojis and absolute local paths and remove any.

## Review fixes

- [X] T015 Test first: rows in `test_builtin_redactor` for a realistic Slack token, a short
  `xoxp-` token and an email with a long digit run; they fail while phone runs before
  secret. Fix: `adapters/redactor/builtin.py` runs secret, then email, then phone, and a
  secret match that is only `+` and phone characters is reported as `phone`.
- [X] T016 `test_store_drops_loaded_credential_values`: a value in `redact.VALUES` appears
  in no `.jsonl` file under `.wuwei` after `inbox.store`.
