# Tasks: the internal-state lint applies by kind and audience

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the pipeline names. Signatures and texts are in plan.md. Fixtures:
`configured`, `payload()`, `outbound_line()`, `write_config()`, `set_posture()`, `run_hook()`,
`events_of()`, `opaque()` (`tests/test_outward.py`; config has profile `strict`, posture
`guarded`, `default_tier = "ask"`, `work_channels = ["chat", "C1"]`). Neutral text only:
`TEXT = 'Notes for I-12 in src/app/main.py'`, patterns
`[r'\bI-[0-9]+\b', r'[a-z_]+/[a-z_/]+\.py']`, channels `C1` (team), `C2` (client via
`external_channels`), `C4` (public via `outbound.channel_classes`), `C7` (unknown, company).
No absolute local path, no em-dash and no emoji in any file.

## Phase 1: the helper, and never on records (FR-001, FR-002; Story 1)

- [X] T001 In `tests/test_outward.py`, add failing tests:
  - `test_internal_word`: with the patterns above, `internal_word(TEXT, config) == 'i-12'`;
    `internal_word('tests passed', config) is None`; the pattern `internal state` matches
    `'internal_state'` (underscore view); `patterns = [1]` raises `TypeError` and `['[']`
    raises `re.error`. Move the four `patterns` rows out of `test_configured_lint` into this
    test, and add a row there: `({'patterns': [r'\bI-[0-9]+\b']}, TEXT, 'chat', 0)` (lint no
    longer checks them).
  - `test_internal_state_never_on_records` (parametrized over postures `observe`, `guarded`,
    `strict`): patterns set, `[tracker]\nauto = ["items"]`; `outward.check_call({'title':
    'Follow-up', 'body': TEXT, 'category': 'items'}, root, config, {'tracker'}, port=True) ==
    (0, '')`; `check_lint` from `wuwei.guards.outward` on `payload(root, TEXT,
    tool=opaque('createJiraIssue'))` (tracker), `opaque('create_page')` (docs) and
    `mcp__github__add_issue_comment` (code host by the default `tool_patterns`) returns
    `(0, '')`; `events_of(root, 'outward.lint') == []`.
  - `test_internal_state_not_on_pr_text`: `lint('Adds I-12\nTouches src/app/main.py',
    'code_host', config) == (0, '')` with the patterns set (the `shepherd` call).
  Fails today: no `internal_word`; the others exit 1 with `internal state pattern`.
- [X] T002 In `cli/wuwei/outward.py`, add `internal_word` (plan section 1) and delete the
  pattern compile and loop from `lint()` (plan section 2).

## Phase 2: client and public hold (FR-003; Story 2.2 to 2.4, 3.2)

- [X] T003 In `tests/test_outward.py`, add failing tests:
  - `test_internal_state_client_holds` (parametrized over `default_tier` `send` and `ask`,
    and `autonomy.mode` `autonomous` and `supervised`): `outbound_line(root,
    'external_channels = ["C2"]')`; `why = []`; `outward.classify(TEXT, root, config,
    {'channel': 'C2', 'text': TEXT}, kind='slack', why=why) == (1, 'draft')` and
    `why == ['internal state word "i-12" for the client audience of C2 (outward.patterns), rewrite that line']`;
    through the hook `check_tier(payload(root, TEXT, channel='C2'))` is exit 1 with that text
    and a draft id (`held_channel(root, reason) == 'slack'`).
  - `test_internal_state_public_and_send_row_hold`: `C4 = "public"` in
    `[outbound.channel_classes]` holds with `public audience of C4`; an owner row
    `tiers = [{ channel = "C2", tier = "send" }]` still holds `C2` with the word reason; a row
    `tiers = [{ channel = "C2", tier = "block" }]` returns `(1, 'block')`.
  - `test_internal_state_client_without_word`: `C2` with `'Thanks'` keeps today's reason
    (no `internal state word`).
  - `test_internal_state_client_approved_sends`: the port path holds a `C2` chat
    (`check_call(..., {'chat'}, port=True)` reason starts with `APPROVAL_REQUIRED`); then
    `check_lint({'text': TEXT, 'channel': 'C2'}, root, config, {'chat'})` (what
    `drafts.approve` runs) is `(0, '')` under guarded.
  Fails today: the reason is a tier rule without the word, and under `send` with a send row
  the call sends.
- [X] T004 In `cli/wuwei/outward.py` `classify`, hoist `parties` and add the outside check
  (plan section 3).

## Phase 3: team and company warn, strict refuses (FR-004; Stories 2.1, 2.5, 3.1, 4)

- [X] T005 In `tests/test_outward.py`, add failing tests:
  - `test_internal_state_team_warns_when_supervised`: `default_tier = "send"`,
    `[autonomy]\nmode = "supervised"`; `run_hook` with `payload(root, TEXT, channel='C1')`
    returns 0; `check_call({'text': TEXT, 'channel': 'C1'}, root, config, {'chat'},
    port=True) == (0, '')`; `events_of(root, 'outward.lint')` payloads are
    `{'kind': 'slack', 'word': 'i-12'}` (hook) and `{'kind': 'chat', 'word': 'i-12'}` (port);
    stderr has `warning: outward: internal state word "i-12" in a`; no `guard.would_refuse`
    event. Same for `C7` (company) under `default_tier = "send"`.
  - `test_internal_state_team_silent_when_autonomous`: the default autonomy; same calls pass,
    no `outward.lint` event, no warning line.
  - `test_internal_state_mail_warns`: supervised, `check_lint({'text': TEXT, 'to':
    'dev@example.test'}, root, config, {'mail'})` is `(0, '')` with one `outward.lint` event of
    kind `mail`.
  - `test_internal_state_to_owner_never`: `outbound.owner.slack.dm = "D01"`, supervised;
    `check_lint({'text': TEXT, 'channel': 'D01'}, ..., {'slack'}) == (0, '')` and no event.
  - `test_internal_state_strict_refuses`: `set_posture(root, 'strict')`; team `C1` chat
    `check_lint` returns `(1, 'outward: internal state word "i-12" in a slack message (outward.patterns); remove it or change the list')`;
    a tracker write still `(0, '')`.
  - Rewrite `test_owner_internal_state_pattern_names_the_word` to assert the strict
    `check_lint` reason naming `the agents` instead of `lint()`.
  Fails today: the port refuses under guarded with `internal state pattern`, the hook records
  `guard.would_refuse`, and no `outward.lint` event exists.
- [X] T006 In `cli/wuwei/outward.py` `check_lint`, add the warning block (plan section 4) with
  the `ponytail:` note.

## Phase 4: the event kind (FR-005)

- [X] T007 In `tests/test_signal_status.py`, add `'outward.lint': 'silent'` to the expected
  map of the emitted-kinds test, and assert `main(['event', 'outward.lint', '{}']) == 1` next
  to the `outward.ai_tells` reservation test. Fails today: the kind is emitted (after T006)
  but neither classified nor reserved.
- [X] T008 Add `'outward.lint'` to `EVENT_PRODUCERS` in `cli/wuwei/commands/event.py` and to
  `SILENT` in `cli/wuwei/signal.py`.

## Phase 5: docs (FR-006)

- [X] T009 Edit `docs/specs/2026-09-24-wuwei-design.md` 4.3 and the `outward.patterns` and
  `autonomy.mode` rows of `docs/site/configuration.md` (plan section 6). Prose only, no
  behaviour, so no test task; `tests/test_docs.py` runs in T010.

## Phase 6: verify

- [X] T010 Run `python -m pytest -q` from the repository root; all pass. Grep the changed
  files for em-dashes, emojis and absolute local paths; remove any.
