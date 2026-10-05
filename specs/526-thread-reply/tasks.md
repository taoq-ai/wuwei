# Tasks: a thread reply in a work channel sends when the thread's participants are known people

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root
using the interpreter the pipeline names. Signatures and texts are in plan.md. Fixtures:
`configured`, `payload()`, `outbound_line()`, `run_hook()` (`tests/test_outward.py`, whose
config has `default_tier = "ask"` and `work_channels = ["chat", "C1"]`), and `root`,
`configure()`, `learn()`, `answer()` (`tests/test_outbound_learn.py`). Record participants in
outward tests with `state._write_state(..., reserved=False)` (the producer path). Neutral ids
only (`C1`, `C2`, `U01`, `U02`, `U03`, `1.2`, `example.com`); no absolute local path, no
em-dash and no emoji in any file.

## Phase 1: topic and row (FR-001, FR-004)

- [X] T001 In `tests/test_outward.py`, add a failing test: an owner row
  `tiers = [{ channel = "C1", topic = "thread", tier = "send" }]` loads. Fails today: the
  schema refuses topic `thread`.
- [X] T002 In `cli/wuwei/workspace.py`, add `'thread'` to `TOPICS`; bump
  `CONFIG_CACHE_VERSION` to 13.
- [X] T003 In `tests/test_outward.py`, update `test_tier_table` and
  `test_send_umbrella_drops_the_broad_rows`: 11 rows under `ask` (8 under `send`), row 10 is
  `{'audience': 'team', 'topic': 'thread', 'tier': 'send'}`, row 11 the monitoring row. Fails
  today: 10 rows.
- [X] T004 In `cli/wuwei/outward.py`, insert the thread row in `DEFAULT_TIERS` after the
  company row.

## Phase 2: the thread readers (FR-002, FR-003; Stories 1, 2.1, 3)

- [X] T005 In `tests/test_outward.py`, add failing tests:
  - `test_thread_team_participants_send` (parametrized over `ask` and `send` umbrellas):
    `slack:U01` and `slack:U02` as team, `outbound_threads = {'C1/1.2': ['U01', 'U02']}`;
    `classify('Thanks', ..., {'channel': 'C1', 'thread_ts': '1.2', 'text': 'Thanks'},
    kind='slack', tool='mcp__slack__slack_send_message', trace=trace)` is `(0, 'send')`, and
    the trace has `party U01: team`, `party U02: team` and a `rule <n> default { audience =
    "team", topic = "thread", tier = "send" }: matched` line for each of `C1`, `U01`, `U02`, where `<n>` is 10 under `ask` and 7 under `send` (the broad rows drop out).
  - `test_thread_owner_participant_sends`: `outbound.owner.slack.user = "U09"` and `U09` among
    the participants; still `(0, 'send')`.
  - `test_thread_not_learned_names_learn` (`ask`): nothing recorded; `(1, 'draft')` with
    `why == ['ask by rule 9 (audience=company) for C1/1.2: participants of thread 1.2 not
    learned, run bin/wuwei outbound learn --tool mcp__slack__slack_send_message --thread
    <file>, connector default class company']`; with `learn = "off"` the `, run ...` clause is
    absent. Under `send` the same call is `(0, 'send')` (A1).
  - `test_thread_unknown_participant_asks` (`ask`): `C1/1.2: ['U01', 'U07']`, `U07` not in
    people; draft with `for U07: unknown thread participant U07, not an internal person in
    outbound.people, connector default class company`.
  - `test_thread_client_participant` (both umbrellas): `slack:U03` as client recorded in
    `C1/1.2`; draft with `ask by rule 5 (audience=client) for U03: U03 in outbound.people as
    client`.
  - `test_thread_only_for_chat`: a `code_host` comment with `thread = 3` gets no thread topic
    (no `not learned` party and no thread row matched in its trace); a slack call with `thread_ts` and two
    destinations keeps `approval tier thread for ...` under `ask`.
  - Update the `RULES` entry `('Thanks', {'channel': 'C1', 'thread_ts': '1.2'}, ...)` to the
    not-learned reason above with `tool` absent (`--tool <tool>`).
  Fails today: the thread rule holds every case under `ask`, and no row is named under `send`.
- [X] T006 In `cli/wuwei/outward.py`, add `what='mention'` to `_person`, `thread=None` to
  `_parties` with the two thread branches, and the thread lookup and topic in `classify`
  (plan sections 2 and 3).

## Phase 3: learn the participants (FR-005; Story 2)

- [X] T007 In `tests/test_outbound_learn.py`, add failing tests:
  - `test_reserved` gains `outbound.thread` (event refused) and `outbound_threads` (state
    `set_state` refused).
  - `test_thread_records_known_participants`: `slack:U01` team in people; a `thread.json`
    `{"channel": "C1", "thread_ts": "1.2", "participants": [{"id": "U01", "name": "Ada",
    "email": "ada@example.com"}]}`; `learn(root, '--thread', file, listings=False)` exits 0,
    prints `recorded 1 participants of thread C1/1.2`, writes `outbound_threads == {'C1/1.2':
    ['U01']}`, one `outbound.thread` event `{thread, participants}`, no decision record.
  - `test_thread_unknown_participant_card`: `company_domains = ["example.com"]`, participants
    `U01` (`ada@example.com`), `U02` (`bo@other.org`), `U04` (empty email) none in people; one
    decision record whose people lines propose `U01` team, `U02` client and `U04` company with
    `in thread 1.2`; after `answer(root, monkeypatch, 'approve')` the config has
    `slack:U01` team, and the outward reply of T005 (`ask`, participants `U01`) sends.
  - `test_thread_file_guards` (parametrized): unreadable file exits 2 with `cannot read a
    listing`; wrong keys, a bad id, a `thread_ts` of `abc`, an empty participants list, and a non-slack tool exit 1 naming
    the shape or `listings apply to a slack connector`; `learn = "off"` exits 1 as today.
  - `test_thread_records_with_an_open_card`: an open learn card exists; `--thread` still records
    the participants, then prints the open card.
  Fails today: unknown argument `--thread`.
- [X] T008 In `cli/wuwei/state.py` and `cli/wuwei/commands/event.py`, reserve
  `outbound_threads` and `outbound.thread` for `wuwei outbound learn`.
- [X] T009 In `cli/wuwei/commands/outbound.py`, add `--thread`, `_listing` (split from
  `_rows`), `_thread`, the record step in `learn` and the participants branch in `propose`
  (plan section 4).

## Phase 4: Always send in this channel's threads (FR-006; Story 4)

- [X] T010 In `tests/test_drafts.py`, add a failing test: a tool draft held with the
  not-learned thread reason for `C1` offers `Always send in this channel's threads`;
  `drafts.approve(root, id, always=True)` adds `{ channel = "C1", topic = "thread", tier =
  "send" }` to `outbound.tiers`; then a reply in thread `C1/9.9` (nothing recorded) under `ask`
  classifies `(0, 'send')`. Fails today: `always_row` returns None.
- [X] T011 In `cli/wuwei/drafts.py`, add the thread branch to `always_row` and the thread text
  in `widget` (plan section 5).

## Phase 5: posture line (FR-007; Story 5)

- [X] T012 In `tests/test_outward.py`, update `test_hook_refusal_names_draft_and_why_reads_it`:
  the second line is `posture: outward = block; a draft is one card away`, and no line holds
  `no setting lowers it`. In `tests/test_hooks.py`, assert an outward security refusal (the
  canary in the text) keeps `(owner-only action; no setting lowers it)` and the publish lines
  stay. Fails today: the floor sentence.
- [X] T013 In `cli/wuwei/commands/hook.py`, add the draft line override in `posture` (plan
  section 6).

## Phase 6: docs (FR-008)

- [X] T014 In `tests/test_docs.py`, add a failing test: `skills/wuwei-plan/SKILL.md` holds
  `outbound learn --tool <tool> --thread <file>` and `thread_ts`; `docs/site/reference.md`
  holds `a draft is one card away`; `docs/site/concepts.md` holds `topic = "thread"`.
- [X] T015 Update `docs/site/concepts.md`, `docs/site/security.md`, `docs/site/reference.md`,
  `docs/site/configuration.md`, `templates/workspace/config.toml` and
  `skills/wuwei-plan/SKILL.md` (plan section 8).

## Phase 7: verify

- [X] T016 Run the full suite (`python -m pytest -q`); fix any pinned rule number, row count or
  tiers printout (`tests/test_outbound.py`) the new row moved. Check the changed files for
  em-dashes, emojis and absolute local paths.

## Dependencies

T001-T002 before T003-T006 (the row needs the topic). T006 before T007's last assertion (the
reply sends after the card). T008 before T009. T011 needs T006. Phases 5 and 6 are independent
of 2 to 4.
