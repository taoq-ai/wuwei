# Tasks: a message to the owner's own DM or user id is never a draft

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the pipeline names. Signatures and texts are in plan.md. Fixtures:
`configured` and `payload()` (`tests/test_outward.py`), the #492 learn fixtures
(`tests/test_outbound_learn.py`), the setup fixtures (`tests/test_setup.py`). Neutral ids only
(`U01`, `D01`, `U02`, `C1`, `T01`, `pat@example.test`, `pat-example`, server
`00000000-0000-4000-8000-000000000001`); no absolute local path, no em-dash and no emoji in
any file.

## Phase A: the owner pass (no #492 code needed)

### Config (FR-001, FR-009)

- [X] T001 In `tests/test_outward.py`, add a failing test: a workspace with
  `[outbound.owner.slack]` `user = "U01"`, `dm = "D01"`, `[outbound.owner]` `mail =
  "pat@example.test"` and `[outbound]` `owner_channel = "dm"` loads with those values, and an
  empty workspace loads `owner == {'slack': {'user': '', 'dm': ''}, 'mail': '', 'code_host':
  ''}` and `owner_channel == 'session'`. Fails today: unknown key `outbound.owner`.
- [X] T002 In `cli/wuwei/workspace.py`, add `owner` and `owner_channel` to
  `SCHEMA['outbound']` and bump `CONFIG_CACHE_VERSION` by one.

### The predicate (FR-002)

- [X] T003 In `tests/test_outward.py`, add a failing table test `test_owner_only` for
  `outward.owner_only(context, config, kind)` with the identity of T001: `{'channel': 'D01'}`,
  `{'channel': 'U01'}`, `{'channel': 'u01'}`, `{'recipient': 'U01'}` and `{'recipients':
  ['U01']}` with kind `slack` and `chat` are true; `{'recipients': ['U01', 'U02']}`,
  `{'channel': 'D01', 'recipient': 'U02'}`, `{'channel': 'D01', 'draft': {'text': 'x'}}`,
  `{}` and `{'channel': 'C1'}` are false; `{'recipients': ['pat@example.test']}` is true for
  `mail` and false for `slack`; any context is false for `code_host`, `tracker` and `docs`;
  every context is false with no identity set. Fails today: no attribute `owner_only`.
- [X] T004 In `cli/wuwei/outward.py`, add `OWNER` and `owner_only` per plan section 2.
- [X] T004a (review F2) In `tests/test_outward.py`, add a failing
  `test_owner_only_ignores_non_dm_shapes`: a `slack.user` or `slack.dm` value that is not a DM
  shape (`C1` as either, `D01` as user, `U01` as dm) is never `owner_only`. Then in
  `owner_only`, ignore slack values that do not fullmatch `[UW][A-Z0-9]+` (user) or
  `D[A-Z0-9]+` (dm), so a channel id recorded as the owner never skips the rules.

### The rule and the DM reason (FR-003, FR-004; US1 scenarios 1, 2, 5; US3)

- [X] T005 In `tests/test_outward.py`, add failing tests: with the identity set,
  `classify('Your build is green', ..., {'text': ..., 'channel': 'D01'}, kind='slack',
  why=why)` and the same to `U01` return `(0, 'send')` with `why == []`; so do a text with
  `salary` and `I will ship it tomorrow`; with `WUWEI_SEAT_ROLE=shepherd` it is still `(1,
  'draft')`. Update the `RULES` row for `{'channel': 'C1', 'is_dm': True}` to `unknown DM
  recipient C1: not the owner's DM or user id in outbound.owner.slack` and add a row for
  `{'channel': 'U02'}` with that rule. Add a test that `{'is_dm': True}` with no destination
  keeps `approval tier direct message for ...: every direct message drafts`. Fails today:
  every DM gives the approval tier reason and the owner sends draft.
- [X] T006 In `cli/wuwei/outward.py`, add the owner rule after line 316 and change the DM
  branch per plan section 3.

### The event and the lint (FR-005, FR-006; US1 scenarios 1 and 4)

- [X] T007 In `tests/test_signal_status.py`, add a failing test next to
  `test_outward_ai_tells_is_silent_and_reserved`: `classify({'kind': 'outward.to_owner',
  'payload': {}}, {})[0] == 'silent'` and `main(['event', 'outward.to_owner', '{}']) == 1`.
  Fails today: it is a nudge and the event command accepts it.
- [X] T008 In `cli/wuwei/signal.py` (`SILENT`) and `cli/wuwei/commands/event.py`
  (`EVENT_PRODUCERS`), add `outward.to_owner`.
- [X] T009 In `tests/test_outward.py`, add failing tests: `outward.check_tier({'text': 'Your
  build is green', 'channel': 'D01'}, root, config, {'slack'})` returns `(0, '')` and today's
  `events.jsonl` holds one `outward.to_owner` row with payload `{'channel': 'slack'}`; a send
  to `C1` and a draft to `U02` add none. `outward.check_lint({'text': 'Pat, your build is
  green', 'channel': 'D01'}, ...)` is `(0, '')` while the same to `C1` is a third-person
  finding, and an emoji to `D01` is still refused. Fails today: no event, and the owner's name
  is refused.
- [X] T010 In `cli/wuwei/outward.py`, record the event in `check_tier` and derive `to_owner`
  in `check_lint` per plan section 4.

### The guard end to end (US1 scenario 1, every posture; SC-001)

- [X] T011 In `tests/test_outward.py`, add a failing parametrized test over `observe`,
  `guarded` and `strict`: the guard (`guards.outward.check_tier` then `check_lint`) on
  `mcp__00000000-0000-4000-8000-000000000001__slack_send_message` with `{'channel': 'D01',
  'text': 'Your build is green'}` exits 0 for both, records one `outward.to_owner` event and
  leaves no `drafts` row in state. Without #492 on the branch, use
  `mcp__slack__slack_send_message` and switch to the UUID name at T016. In
  `tests/test_hooks.py`, add a row to `test_only_a_held_call_imports_the_draft_queue` for a
  send to the owner's DM (config with the identity): exit 0 and no `wuwei.drafts`. Fails
  before T006 and T010; after them it passes with no further code (it pins the guard path).

### Setup (FR-010; US5)

- [X] T012 In `tests/test_setup.py`, add failing tests: `setup.identity(config,
  'pat-example', [])` with a repository identity email `pat@example.test` and no
  `outbound.owner` includes `(('outbound', 'owner'), 'code_host', 'pat-example')` and
  `(('outbound', 'owner'), 'mail', 'pat@example.test')`, and neither when both are set;
  `setup.connect` with a pinned `control_plane.owner = "T01/U01"` (fakes as in the existing
  `connect` tests) writes `outbound.owner.slack.user = "U01"` and leaves
  `outbound.owner.slack.dm` empty although `SLACK_OWNER_DM_CHANNEL` is set. Fails today: no
  such settings.
- [X] T013 In `cli/wuwei/commands/setup.py`, change `identity()` and `connect()` per plan
  section 7.

### Skills and docs (FR-009, FR-012; US4)

- [X] T014 In `tests/test_docs.py`, add a failing `test_owner_channel_in_skills`:
  `skills/wuwei-plan/SKILL.md` names `outbound.owner_channel`, `outbound.owner.slack.dm` and
  `outbound learn`; `skills/wuwei-report/SKILL.md` names `owner_channel`;
  `docs/site/configuration.md` names `` `outbound.owner` `` and `` `outbound.owner_channel` ``;
  `docs/site/security.md` names `outward.to_owner` and `unknown DM recipient`. Fails today.
- [X] T015 Write the paragraphs and rows of plan section 8 in
  `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`,
  `docs/site/configuration.md`, `docs/site/security.md` and
  `templates/workspace/config.toml`. `test_every_template_config_key_is_documented` and the
  rest of `tests/test_docs.py` stay green.

## Checkpoint: #492 on the branch

Status (builder): the branch does not hold #492 (`cli/wuwei/commands/outbound.py` has no
`learn`), so Phase B (T016-T021) is blocked on #492. Phase A deviation: T014 and T015 do not
name `outbound learn` in `skills/wuwei-plan/SKILL.md` yet, because the command does not exist
on this branch; the skill shows the `config set` lines for the identity instead. T016 adds
`outbound learn` to that paragraph and its test.

Status (rebase): the branch is rebased on main with #492 and #493; Phase B is done and the
skill paragraph names `outbound learn --tool <tool>` and `--owner <file>` instead of the
`config set` lines.

Phase B edits #492's `outbound learn`. Before T016, the branch must hold #492 (main merged
after #492 lands; the orchestrator does that, not the builder). If
`cli/wuwei/commands/outbound.py` has no `learn`, stop here, run the full suite, and report
Phase B as blocked on #492.

## Phase B: the identity on the #492 card (FR-007, FR-008; US2)

- [X] T016 In `tests/test_outward.py`, switch T011 to the UUID tool name. In
  `tests/test_outbound_learn.py`, add failing tests: with no `outbound.owner`, the guard on the
  UUID send to `D01` holds it and the reason holds `unknown DM recipient D01` and `bin/wuwei
  outbound learn --tool <tool>`; with the identity recorded, a send to `U02` is held without
  `outbound learn` in the reason. Fails today: `unknown_audience` skips every `D`/`U` id.
  Done as merged: #492 landed without `unknown_audience`; the learn command is named on the
  #493 draft card, not in the held reason, so the reason names the rule and the card
  (`bin/wuwei drafts show <id> --widget`) and the card names `outbound learn --tool <tool>
  --owner <file>` (T021a). Owner ids in the learn tests are `U09`/`D09` because the #492
  fixture already uses `U01` for a teammate.
- [X] T017 Not needed: no `unknown_audience` on main; T021a carries the hint.
- [X] T017a (owner comment) In `tests/test_outward.py`, `test_guard_to_owner_floor`: strict,
  outward area `block`, connector mode `draft` and a sensitive word still send the self-DM
  with the event, and so does mode `refuse`; a DM to `U02` still drafts or is refused. In
  `cli/wuwei/guards/outward.py`, mode `draft` or `refuse`
  does not apply when `outward.owner_only` is true.
- [X] T018 In `tests/test_outbound_learn.py`, add failing tests: `outbound learn --tool
  <uuid tool>` with no files prints a step naming `auth_test`, `whoami` and `--owner`;
  `--owner` with `{"user": "x", "dm": ""}`, `{"user": "U01"}`, `{"user": "U01", "dm": "C1"}`
  or a `dm` equal to `SLACK_OWNER_DM_CHANNEL` exits 1 naming the shape; an unreadable file
  exits 2. Fails today: no `--owner` argument.
- [X] T019 In `cli/wuwei/commands/outbound.py`, add `--owner`, `_owner()` and the `learn`
  steps 6 and 7 changes per plan section 6.
- [X] T020 In `tests/test_outbound_learn.py`, add failing tests: `--owner` with `{"user":
  "U01", "dm": "D01"}` writes one decision record and prints one widget whose question holds
  `your identity U01, DM D01`, under `outbound.learn = "auto"` and the observe posture too;
  answering `approve` through `wuwei decide` writes `outbound.owner.slack.user = "U01"` and
  `.dm = "D01"`, records `outbound.learned` with `owner` true, and the guard then passes the
  UUID send to `D01` with the `outward.to_owner` event; answering `keep` writes nothing and
  the send stays held; with `user = "U01"` already recorded the proposal holds only `dm`; with
  both recorded and no channels or people, learn exits 1 with nothing new. Fails today: the
  proposal has no owner.
- [X] T021 In `cli/wuwei/commands/outbound.py`, change `propose`, `record`, `apply` and the
  `card` condition in `learn` per plan section 6.
- [X] T021a (review F1) In `tests/test_drafts.py`, add a failing test next to
  `test_card_names_outbound_learn_when_on`: a draft held for `unknown DM recipient U01` with
  learning on offers `bin/wuwei outbound learn --owner` on its card. Then in
  `cli/wuwei/drafts.py` `widget()`, add `'unknown DM recipient'` to the learn-hint prefixes and
  name `--owner` for it, only while `outbound.owner.slack` is incomplete.

## Finish

- [X] T022 Run the full suite (`python -m pytest -q`); all green. Check every file written for
  em-dashes, emojis and absolute local paths and remove any.
