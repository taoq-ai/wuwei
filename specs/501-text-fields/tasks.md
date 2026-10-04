# Tasks: the outward lint reads text and destinations from any connector payload shape

**Input**: `specs/501-text-fields/` (spec.md, plan.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. Build after #495 merges (plan, Build order). Fixtures only (plan,
Fixtures). No absolute local paths, emojis or em-dashes in any file.

## Phase 1: US1, a connector write is read whatever its shape

- [X] T001 Test, `tests/test_outward.py`: add `CORPUS`, the recorded `tool_input` shapes
  with their expected destinations: Slack `{channel: 'C1', text}` -> `['C1']`; Jira
  `{issue_key: 'DEMO-12', comment}` -> `['DEMO-12']`; Confluence `{pageId, body: {storage:
  {value, representation: 'storage'}}}` -> `[pageId]`; Notion `{page_id, children: [{object:
  'block', type: 'paragraph', paragraph: {rich_text: [{type: 'text', text: {content}}]}}]}`
  -> `[page_id]`; GitHub `{owner: 'acme', repo: 'widgets', pull_number: 7, body}` ->
  `['widgets', '7']`; Sentry `{issue_id: 'PROJ-1', status: 'resolved'}` -> `['PROJ-1']`;
  mail `{to: 'someone@example.test', subject, body}` -> `['someone@example.test']`. Add
  `test_text_fields_corpus` (spec US1 scenario 4, FR-001 to FR-003): `outward._text` reads
  each without error, the text of each (none for Sentry, and never `block`, `paragraph`,
  `resolved` or an id) is found, the destinations match; with `salary` placed in each one's
  nested text (not Sentry), `outward.check_send(shape, root, config, {channel})` returns 1
  with `outbound.sensitive_keywords` in the reason. Add `test_connector_writes_through_the_guard`
  (spec US1 scenarios 1 and 2): `mcp__notion__append_block_children` with `salary` in a
  nested rich-text block is held by `check_tier` with a #493 reason (`HELD` matches, the
  rule starts `approval tier sensitive` and names `outbound.sensitive_keywords`); a Jira
  `{issue_key, comment: 'tests passed'}` through a UUID connector aliased to `tracker` with
  mode `send` returns `(0, '')` from `check_tier` and `check_lint`. Run `python -m pytest -q
  tests/test_outward.py -k "corpus or connector_writes"` (fails: `unsupported input field`
  and `expected plain text`).
- [X] T002 Test, `tests/test_outward.py`: `test_text_fields_keep_known_checks` (FR-004,
  FR-005): `{'title': 'a', 'draft': {'description': 'b', 'teamId': 't'}, 'channel': 'C1',
  'recipients': ['dev'], 'is_dm': False, 'issue_number': 3, 'thread': None}` returns texts
  `['b', 'a']` and destinations `['C1', 'dev']`; each of `is_dm: 'false'`, `recipients:
  'dev'`, `channel: {'text': 'hidden'}`, `issue_number: True`, `draft: 'x'`, `draft:
  {'draft': {}}`, `parent: {'page_id': 'p'}` still raises `ValueError`. Run `python -m
  pytest -q tests/test_outward.py -k keep_known_checks` (fails: destinations are `['C1']`).
- [X] T003 Test, `tests/test_outbound.py` and `tests/test_outward.py`: update the bypass
  rows the plan lists that Design 1 changes (plan, Existing tests whose expectations
  change), except the `{}` and `''` rows (T005): `test_routing_and_bypass_table` (`blocks`,
  `approved`, `approved_draft_id`, `attachments`, `title: None`, `text` list to 1),
  `test_humanize_lint_gates` (`{'text': 1}` to 0),
  `test_acceptance_and_audience` (`approved`, `in_scope` to `(0, 'send')`),
  `test_guard_tiers_and_bypasses` (`blocks: []`, `approved` to 0), `test_cli_tier`
  (`approved` to 1), `test_hook_translation` (code 2 uses `is_shared: 'false'`). Add to
  `test_acceptance_and_audience` the FR-008 rows `('Thanks', {'channel': 'Cwork',
  'issue_key': 'DEMO-12'}, (0, 'send'))` and `('Thanks', {'channel': 'Cwork', 'repo':
  'Dashboard'}, (0, 'send'))` (a destination that starts with D is not a DM). Run `python
  -m pytest -q tests/test_outward.py tests/test_outbound.py -k "routing or humanize_lint_gates
  or acceptance_and_audience or guard_tiers or cli_tier or hook_translation"` (fails: the
  unknown fields still refuse). The `repo: 'Dashboard'` row passes on main; it is the
  regression guard for Design 3 once destinations widen.
- [X] T004 Implement plan Design 1 (`DESTINATIONS`, `NOT_TEXT`, `_strings`, `_text`) and the
  second bullet of Design 3 (`classify` reads chat channel ids from `channel` and
  `channel_id` only) in `cli/wuwei/outward.py`. Rerun T001 to T003; pass. Run `python -m
  pytest -q tests/test_outward.py tests/test_outbound.py tests/test_drafts.py`; pass.

## Phase 2: US1, a write without text has nothing to lint

- [X] T005 Test, `tests/test_outward.py` and `tests/test_outbound.py`:
  `test_textless_write` (spec US1 scenario 3, FR-006, FR-007, FR-009): a Sentry
  `{issue_id: 'PROJ-1', status: 'resolved'}` through `opaque('resolve_issue', <uuid>)` returns
  `(0, '')` from `check_tier` and `check_lint`; `outward.check_lint({'issue_id': 'PROJ-1'},
  root, config, {'other'}) == (0, '')`; `outward.check_lint({'text': '', 'channel': 'C1'},
  root, config, {'chat'})[0] == 2` and `outward.check_tier({'text': ' ', 'channel': 'C1'},
  root, config, {'chat'})` returns 2 with `nonempty text required` (a blank text still
  refuses); with the owner's mode `draft` for that server, `check_tier` holds it (`HELD`
  matches) and `drafts.read(state.read_state(root))` returns the row with `text == ''`.
  Update `test_routing_and_bypass_table` `{}` to 1, `test_reusable_classification` `''` to
  `(1, 'draft')` and `test_acceptance_and_audience` `('', {'channel': 'Cwork'})` to
  `(1, 'draft')`; in `tests/test_guard_mutation.py` the two outward probes use `[]` instead
  of `{}` (an empty object stops being a refusal in T006; `[]` is refused before and after).
  Run `python -m pytest -q tests/test_outward.py tests/test_outbound.py -k "textless or
  routing or reusable_classification or acceptance_and_audience"` (fails: lint
  refuses the empty text, the draft queue read raises `invalid record`, `classify` returns 2
  for `''`, `check_tier` gives the classify reason for the blank text).
- [X] T006 Implement plan Design 2 (`check_lint` in `cli/wuwei/outward.py`; delete the
  mode-`send` no-text branch in `_check`, `cli/wuwei/guards/outward.py`), the first two
  bullets of Design 3 (`classify` accepts an empty text, `check_tier` refuses a blank one,
  `cli/wuwei/outward.py`) and Design 4 (`drafts.read`, `cli/wuwei/drafts.py`). Rerun T005;
  pass. Run `python -m pytest -q tests/test_outward.py tests/test_outbound.py
  tests/test_drafts.py tests/test_guard_mutation.py`; pass
  (`test_invalid_call_does_not_create_draft[empty]` included).

## Phase 3: US2, an unreadable payload says so

- [X] T007 Test, `tests/test_outward.py`: `test_tool_input_not_an_object` (spec US2, FR-010):
  for `check_tier` and `check_lint` from `wuwei.guards.outward`, an
  `opaque('slack_send_message')` call with `tool_input` `[]` returns `(2, 'outward:
  tool_input is not an object; got list; pass the tool arguments as a JSON object')`, with
  `'x'` the reason has `got str`, and neither reason contains `config check`. In
  `test_hook_integration` the code-2 case uses `tool_input = []`. Run `python -m pytest -q
  tests/test_outward.py -k "not_an_object or hook_integration"` (fails: the config-check
  reason).
- [X] T008 Implement plan Design 5 in `_check`, `cli/wuwei/guards/outward.py`. Rerun T007
  and `python -m pytest -q tests/test_reasons.py`; pass.

## Phase 4: US3, docs

- [X] T009 Write the plan Design 6 paragraph in `docs/site/security.md`. Run `python -m
  pytest -q tests/test_docs.py`; pass.

## Phase 5: Finish

- [X] T011 Review F1: `owner_only` counts `cc`, `bcc` and, for mail, every address in the
  payload text as a reader. Tests in `tests/test_outward.py` (`test_owner_only` cc, bcc and
  ccRecipients rows, `test_guard_owner_mail_with_outside_cc_is_not_owner_only`) fail first,
  then pass.
- [X] T010 Run the full suite, `python -m pytest -q`; everything passes. Check every file
  changed for em-dashes, emojis and absolute local paths and remove any.
