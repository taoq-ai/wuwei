# Tasks: a held draft names its rule and id, the owner approves it on a card, and the approved draft goes out through the same MCP tool

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the pipeline names. Signatures, texts and the rule table are in
plan.md; row fields and transitions in data-model.md. Fixtures: `configured` and `payload()`
(`tests/test_outward.py`), `root`, `sink`, `port`, `queued()` (`tests/test_drafts.py`),
`gated()`, `edit()` (`tests/test_owner_edits.py`), `planner` and `gate()`
(`tests/test_decision.py`). Neutral ids (`C1`, `C9`, `dev`) only; no absolute local path, no
em-dash and no emoji in any file.

## The rule (FR-001, FR-002, US1 scenario 2)

- [X] T001 In `tests/test_outward.py`, add a failing table test for `outward.classify(...,
  why=why)` with `why = []`: `Thanks` to `C9` gives `unknown destination C9: not in
  outbound.work_channels`; `Thanks @dev` to `C1` gives `unknown mention @dev: ...`; `I will
  ship it tomorrow` to `C1` gives `approval tier commitment for C1: outbound.commitment_patterns`;
  `WUWEI_SEAT_ROLE=shepherd` gives `headless seat: ...`; `Can you review my PR?` to `C1`
  gives `review ping without a code-host link: ...`; plus `is_dm` (`approval tier direct
  message`) and a chat thread (`approval tier thread`). Each call still returns `(1,
  'draft')`, `why` has exactly one entry, no entry contains `; `, and `fixed in abc1234` to
  `C1` returns `(0, 'send')` with `why == []`. Fails today: `TypeError: unexpected keyword
  argument 'why'`.
- [X] T002 In `cli/wuwei/outward.py`, add `why` to `classify` and route every draft site
  through the local `held(rule)` per the plan's rule table (sensitive keys split, first
  unknown recipient by `next`). Existing `classify` tests stay green unchanged.
- [X] T003 In `tests/test_outward.py`, add a failing test: `outward.check_tier({'text':
  'Thanks', 'channel': 'C9'}, root, config, {'slack'})` returns `(1, APPROVAL_REQUIRED +
  ': unknown destination C9: not in outbound.work_channels')`, and `outward.check_call` with
  the same inputs returns that result (draft detected by prefix, humanize pass only). Fails
  today: the reason is the bare constant.
- [X] T004 In `cli/wuwei/outward.py`, pass `why` from `check_tier` and append the rule; make
  `check_call` detect a draft by prefix.

## The guard stores the draft and names it (FR-003, US1 scenarios 1 to 3)

- [X] T005 In `tests/test_outward.py`, add a failing test: `guards.outward.check_tier` on the
  five T001 payloads (Slack MCP tool) returns exit 1 with a reason matching `^outward: draft
  (draft-[0-9a-f]{32}): <rule>: [^;]*; the owner decides: bin/wuwei drafts show \1 --widget$`,
  five distinct `<rule>` values; each id is a `pending` row with `operation == 'tool'`,
  `adapter == 'mcp'`, the tool name, `channel == 'slack'` and the destination; the same call
  again returns the same id and adds no row. Update `test_send_or_draft` (line 130) and
  `test_recorded_server_tools` (line 859) to assert `outward: draft ` instead of the old
  lines. Fails today: the old channel line and no `drafts` row.
- [X] T006 In `tests/test_why.py`, add a failing test: `wuwei hook PreToolUse` with the `C9`
  payload (as the hook tests pipe it, `WUWEI_WORKSPACE` set) prints the reason as the first
  line and `posture: outward = block (owner-only action; no setting lowers it)` as the
  second; then `wuwei why last refusal` prints `rule: outward: draft <id>: unknown
  destination C9: not in outbound.work_channels` and `fix: the owner decides: bin/wuwei
  drafts show <id> --widget`. Fails today: the old line.
- [X] T007 In `cli/wuwei/drafts.py`, add `TOOL`, `destination()` (extracted from `create`),
  the `tool` argument of `create`, tool-row validation in `read`, `reason()` and `hold()`;
  in `cli/wuwei/guards/outward.py`, replace lines 133-135 with the plan's branch, calling
  only `drafts.hold` for now (T021 adds `spend`).

## The port path keeps one shape (FR-003, US1 scenario 4)

- [X] T008 In `tests/test_drafts.py`, add a failing test: `queued()` returns a reason
  starting `outward: draft <id>: approval tier ` and ending `; the owner decides: bin/wuwei
  drafts show <id> --widget`; change the `'stored draft'` assertions in `tests/test_drafts.py`
  (line 527) and `tests/test_outward.py` (line 555) to `'outward: draft '`; change the two
  fake reasons in `tests/test_decision_digest.py` (lines 20 and 93) to the new shape. The
  tracker, docs and digest tests that read a stored draft id stay as they are. Fails today:
  `stored draft` shape.
- [X] T009 In `cli/wuwei/registry.py`, compare by prefix and return `drafts.hold(...)`; in
  `cli/wuwei/docs.py:199`, `cli/wuwei/tracker.py:124` and `:265`, and `cli/wuwei/watch.py:148`,
  read the new shape.

## The card (FR-004, US2 scenarios 1, 2 and 5)

- [X] T010 In `tests/test_drafts.py`, add failing tests for `wuwei drafts show <id> --widget`
  on an MCP draft (stored through the guard) and a port draft: exit 0, a JSON list of one
  widget with header `Draft`, a question citing the id, the destination, the rule and the
  text, `record == 'bin/wuwei drafts approve <id>'`, labels `Send now (Recommended)`, `Send
  with an edit`, `Keep as draft`, `Drop`, the edit option naming `--file` and the drop option
  naming `bin/wuwei drafts drop <id>`; under `[security] posture = "strict"` an `approval
  tier` draft lists `Keep as draft (Recommended)` first while an `unknown destination` draft
  still lists `Send now (Recommended)` first; with `config['outbound']['learn'] = 'card'`
  (monkeypatched `workspace.load_config`) an `unknown destination` card's `Send now`
  description names `bin/wuwei outbound learn`, and without the key it does not; `drafts show
  <id>` without `--widget` prints the row; an unknown id exits 1 with the `_pending` message.
  In `tests/test_cli_known_command.py` and `tests/test_guide.py` the existing drift tests
  cover `drafts show` once T011 registers it. Fails today: argparse `invalid choice: 'show'`.
- [X] T011 In `cli/wuwei/drafts.py`, add `widget(row, config)`; in
  `cli/wuwei/commands/drafts.py`, the `show` subparser; in `cli/wuwei/commands/__init__.py`,
  `'drafts show'` in `READ_ONLY`; in `cli/wuwei/guide.py`, `'drafts show <id> --widget'` in
  `WIDGETS`.

## The card is a record (FR-005, FR-006, US2 scenarios 3 and 4)

- [X] T012 In `tests/test_decision.py`, add failing tests with the `planner` fixture and a
  pending draft: `check_question` accepts a question `"<id>: send this ...?"` with header
  `Draft` under strict; a question citing an unknown or dropped draft id is refused with
  exit 1 naming `bin/wuwei drafts`; `record_gate` records the id in the planner session's
  `gate_asked` for header `Draft`, and records nothing for another header, a seat
  (`agent_id`) or another session. Fails today: the D-n hint refusal and no `gate_asked`.
- [X] T013 In `cli/wuwei/guards/decision.py`, accept and record cited pending draft ids.
- [X] T014 In `tests/test_owner_edits.py`, add failing tests: after `gated()` and a recorded
  `Draft` card for a pending id, under `observe` and `guarded`, `edit(tmp_path, 'bin/wuwei
  drafts approve <id>')`, `... --file reply.txt` and `bin/wuwei drafts drop <id>` return `(0,
  '')`; an id not asked, `agent_id='a1'` and another session keep the plain owner reason or
  `Run it in a host terminal: <command>`; under `strict` the asked id returns `(1, '<owner
  reason> Run it in a host terminal: bin/wuwei drafts approve <id>')`, and
  `guards.outward.check_tier` on the held call still returns exit 1 with the same draft id.
  Fails today: the owner reason for every case.
- [X] T015 In `cli/wuwei/guards/protect_state.py`, add the two `_GATE_EDITS` entries and the
  draft id to the asked-id check.

## Approve: one confirmation rule, the answer and the hash (FR-008, US3 scenario 3)

- [X] T016 In `tests/test_drafts.py`, add a failing test: with the `port` fixture under the
  default posture, `_host_confirm` monkeypatched to `pytest.fail`, `drafts approve <id>` sends
  once through the adapter and the row records `answer == 'Send now'` and `text_sha256` of
  the sent text; under strict `_host_confirm` is called with today's digest. Set
  `[security] posture = "strict"` in `test_approve_without_terminal_is_owner_action`,
  `test_approve_declined_digest_sends_nothing`, `test_approve_digest_covers_id_and_final_text`
  and every other test that depends on the prompt. Fails today: `_host_confirm` is called
  under guarded.
- [X] T017 In `cli/wuwei/drafts.py` `approve`, confirm only under strict and add `answer` and
  `text_sha256` to the claim.

## Approve with a file (FR-009, US3 scenario 4)

- [X] T018 In `tests/test_drafts.py`, add failing tests: `drafts approve <id> --file
  <tmp_path file>` sends the file's text, records `answer == 'Send with an edit'`, `edit_size`
  and `sent_unedited is False`; a file holding an em-dash is refused by the lint and the row
  stays `pending`; a trailing newline in the file of a single-field draft counts as unedited
  (as `test_editor_trailing_newline_counts_as_unedited`); `--file` with `--edit` exits 2 from
  argparse. Fails today: `unrecognized arguments: --file`.
- [X] T019 In `cli/wuwei/drafts.py`, add `source` to `_edit` and `approve`; in
  `cli/wuwei/commands/drafts.py`, the `--file` option in a mutually exclusive group with
  `--edit`.

## The allowance (FR-007, FR-010, FR-011, US3 scenarios 1, 2 and 5)

- [X] T020 In `tests/test_drafts.py`, add failing tests under guarded:
  - an MCP draft from the guard, then `main(['drafts', 'approve', id]) == 0`: the row is
    `approved` with `answer`, `text_sha256`, `decided` and `expires == now + 3600 s`, a
    `draft.approved` event `{id, tool}` exists, and nothing was sent; `guards.outward.check_tier`
    on the same payload returns `(0, '')`, writes `draft.sent` `{id, tool}` and marks the row
    `sent`; the same payload again returns exit 1 with a new draft id;
  - with an `approved` row, a call with another tool, another channel or another text is
    drafted and the row stays `approved`; with `WUWEI_NOW` past `expires` the same call is
    drafted;
  - `[outward] draft_ttl = 120` gives `expires == now + 120 s`; `draft_ttl = 30` is a config
    error;
  - a port draft from `queued()` (chat adapter `none`) approves to `approved` with no `tool`,
    and a `mcp__slack__post_message` call to `C2` with the same text passes once;
  - an approved MCP row cannot be forged: `main(['event', 'draft.approved', '{}']) == 1`;
  - a held call carrying the workspace canary is refused by the security check even with a
    matching `approved` row.
  Fails today: `drafts approve` raises `KeyError` on `config['adapters']['slack']` (exit 2).
- [X] T021 In `cli/wuwei/drafts.py`, add `ANSWERS`, the `approved` status and its `read`
  checks, the allowance branch of `approve`, and `spend`; in `cli/wuwei/guards/outward.py`,
  call `drafts.spend` before `drafts.hold`; in `cli/wuwei/workspace.py`, `draft_ttl` in the
  `outward` schema and `CONFIG_CACHE_VERSION = 7`; in `cli/wuwei/commands/event.py`, the
  `approved` action; in `templates/workspace/config.toml`, the commented `draft_ttl` line.

## Hook latency (FR-012, SC-003)

- [X] T022 In `tests/test_hooks.py`, add a test after the pattern of
  `test_hook_imports_no_unused_stdlib`: a workspace with an owner name and
  `outbound.work_channels = ["C1"]`, a `mcp__slack__post_message` call `{'channel': 'C1',
  'text': 'Thanks'}` exits 0 with neither `wuwei.drafts` nor `hashlib` in `sys.modules`, and
  the same call to `C9` loads `wuwei.drafts`. It passes once T007 and T021 keep the import
  inside the held branch; run it before and after T021.

## Docs (FR-013, US4)

- [X] T023 In `tests/test_docs.py`, add a failing test: `concepts.md` names `allowance`,
  `card` and `bin/wuwei drafts show <id> --widget`; `daily.md` says a draft is one card away
  from being sent; `security.md` says the owner decides and no longer contains `asks for a
  draft you send yourself`; `configuration.md` has an `outward.draft_ttl` row (the template
  key test also covers it). Fails today: the words are missing.
- [X] T024 Edit `docs/site/concepts.md`, `docs/site/daily.md`, `docs/site/security.md` and
  `docs/site/configuration.md` per the plan.

## Finish

- [X] T025 Run the full suite with the pipeline's interpreter (`-m pytest -q`); fix every
  failure the new reason shape, the strict-only prompt or the allowance status causes in
  tests not listed above, keeping each test's intent.
- [X] T026 Check every file written for em-dashes, emojis and absolute local paths, and remove
  any.

## Review fixes

- [X] T027 (F1) Update `tests/test_outbound.py` to the `outward: draft <id>` reason and
  `tests/test_signal_status.py` for the conditional `draft.sending` / `draft.approved` kinds.
- [X] T028 (F2) Failing tests in `tests/test_decision.py` and `tests/test_owner_edits.py`:
  `record_gate` records `<id>:send`, `<id>:edit` or `<id>:text:<sha256>` from the owner's
  PostToolUse answer; a planner `drafts approve <id>` needs `<id>:send`, `--file` needs
  `<id>:edit`, and `approve --file` outside strict skips the host prompt only when the final
  text matches a typed answer. Then fix `guards/decision.py`, `guards/protect_state.py` and
  `drafts.py`.
- [X] T029 (F3) Add `draft.approved` to `signal.SILENT`.
