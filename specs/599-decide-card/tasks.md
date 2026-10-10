# Tasks: A card answer confirms the record command without the session id in the environment

Test first: each test task runs and fails for the expected reason before its implementation
task. While building run only the touched files, for example `python -m pytest -q
tests/test_card_confirms.py tests/test_sessions.py`; run the full suite once in T021.

## Phase 1: the session from state (FR-001, FR-002; US1.1, US1.3, US2.1)

- [X] T001 Test in `tests/test_sessions.py`: `test_caller_reads_the_planner_from_state`. No
  planner registered: None. After `plan session planner-1`, variable unset: a non-terminal
  stdin gives `planner-1`; a `Terminal()` stdin gives None, and `card=True` gives
  `planner-1`; with `WUWEI_SESSION_ID=other` both give `other`. Run: fails (`caller`
  missing).
- [X] T002 Test in `tests/test_card_confirms.py`:
  `test_decide_records_an_asked_card_without_the_session_id` (issue acceptance 1). Route D-1
  and answer it through `config_card()` (the record gate), variable unset, `sys.stdin` an
  `io.StringIO()`, `no_terminal(monkeypatch)`; `main('decide', 'D-1', <label>)` without
  `--card`. Assert exit 0, `Decided-by: owner` and a Notes line with `in the planner
  session`. Run: fails (the host terminal was opened).
- [X] T003 Test in `tests/test_card_confirms.py`: `test_host_terminal_prompts` (issue
  acceptance 2), parametrized not asked and asked: `Terminal()` stdin, no variable, no
  `--card`, `_host_confirm` recording and returning True: exit 0, one prompt, Notes `at the
  host terminal`. Run: passes for not asked; the asked case pins that a TTY caller keeps the
  prompt.
- [X] T004 Test in `tests/test_card_confirms.py`:
  `test_config_set_from_card_without_the_session_id` and
  `test_calibrate_answer_without_the_session_id` (US1.3): the existing `config set
  --from-card D-1` and `calibrate --answer` flows, variable unset, non-terminal stdin,
  `no_terminal`: the key is written. Run: fails.
- [X] T005 Test in `tests/test_mcp.py`: the pending MCP decision asked on a card, variable
  unset, non-terminal stdin, `no_terminal`: `wuwei mcp decide <id> proceed` and `wuwei
  decide <id> proceed` record with no prompt (US1.4). Run: fails.
- [X] T006 Implement `sessions.caller` and switch `sessions.card_answered` and
  `decision.owner_confirm` to it (`cli/wuwei/sessions.py`, `cli/wuwei/decision.py`). Give a
  `Terminal()` stdin to the existing tests that mean a host terminal
  (`test_card_answered_only_for_the_planner_outside_strict`, the `no session` case of
  `test_calibrate_answer_without_the_card_answer_keeps_promote`, any other). Run T001 to
  T005 and `tests/test_card_confirms.py tests/test_decision.py tests/test_mcp.py`: green.

## Phase 2: the card hash in the record command (FR-003, FR-004; US4.1)

- [X] T007 Test in `tests/test_decision.py`: `test_card_hash_names_question_and_options`:
  `card_hash` is 12 lowercase hex characters, the same for the same Question and Options,
  different when either changes, unchanged when `Outcome:`, `Decided-by:` or a Notes line
  changes. Run: fails (`card_hash` missing).
- [X] T008 Test: change the record pins `tests/test_card_confirms.py:354`,
  `tests/test_decision.py:1236` and `tests/test_outbound_learn.py:170` to `wuwei decide D-n
  "<label>" --card <decision.card_hash of that record>`; assert the mcp widget record (in
  `tests/test_mcp.py`) and the config card record stay unchanged. Run: fails.
- [X] T009 Implement `decision.card_hash`, `RECORD` with `--card {card}` and the
  `record_widget` format in `cli/wuwei/decision.py`. Run T007, T008 and the cruise and
  grants widget tests: green.

## Phase 3: --card confirms only the asked card of the record as it stands (FR-005, FR-006; US1.2, US2.2, US2.4, US2.5)

- [X] T010 Test in `tests/test_card_confirms.py`: `test_decide_with_card_never_prompts`,
  parametrized, `_host_confirm` recording, `Terminal()` stdin, no variable, the hash from
  `decision.card_hash` of the routed record: (a) asked: exit 0, Notes `in the planner
  session`, no prompt; (b) asked, the record's Options edited after the card, old hash: exit
  1, `Outcome: pending`, no prompt, reason names `bin/wuwei decision show D-1 --widget`; (c)
  a hash that is not the record's (`--card 000000000000`): as (b); (d) not asked below
  strict: as (b); (e) strict, asked: exit 1, no prompt, reason names `bin/wuwei decide D-1
  A in a host terminal`. Run: fails (`--card` unknown).
- [X] T011 Test in `tests/test_mcp.py`: `wuwei decide <mcp id> proceed --card <hash>` for the
  asked pending MCP decision records with no prompt; a mismatched hash exits 1 with the
  `no_card` reason. Run: fails.
- [X] T012 Implement `--card HASH` in `cli/wuwei/commands/decide.py`; `owner_confirm(...,
  card=None, fields=None)` and `no_card` in `cli/wuwei/decision.py`; `owner_outcome` in
  `cli/wuwei/commands/decision.py`; `mcp.decide(..., card=None)` in `cli/wuwei/mcp.py`. Run
  T010, T011 and `tests/test_decision.py tests/test_mcp.py tests/test_card_confirms.py`:
  green.

## Phase 4: seats cannot reach it (US2.3, issue acceptance 4)

- [X] T013 Test in `tests/test_card_confirms.py`:
  `test_hook_refuses_a_seat_record_command_with_card`: D-1 asked by `planner-1`;
  `protect_state.check_bash` on `bin/wuwei decide D-1 A --card <hash>` with (a) the planner
  payload: exit 0; (b) the planner payload plus `agent_id`: exit 1; (c) `session_id`
  `seat-1` with `WUWEI_SEAT_ROLE=shepherd` set: exit 1. Under strict (d) the planner
  payload: exit 1 naming the host terminal. No implementation task: it pins the existing
  hook rule (I8) that runs before the CLI; it must pass unchanged once T012 exists.

## Phase 5: the missing session id is visible (FR-007, FR-008; US3, issue acceptance 5)

- [X] T014 Test in `tests/test_sessions.py`: `test_session_start_flags_the_env_file`:
  SessionStart with `CLAUDE_ENV_FILE` set gives a `session.seen` payload with `env_file`
  true; unset, false; Stop and SubagentStop rows have no `env_file` key. Run: fails.
- [X] T015 Implement the `export` return and `touch(..., env_file=None)` in
  `cli/wuwei/sessions.py` and the `_seen` keyword pass in `cli/wuwei/guards/lifecycle.py`.
  Run `tests/test_sessions.py` (the #587 read-count test included): green.
- [X] T016 Test in `tests/test_doctor.py`: `test_day_session_id_row`: no flagged event: one
  ok `session id` row; a `session.seen` event with `env_file` false: warn, value names
  `CLAUDE_ENV_FILE`; a later one with true: ok. Run: fails.
- [X] T017 Implement the row in `_day` of `cli/wuwei/commands/doctor.py`. Run
  `tests/test_doctor.py`: green, updating only pins that list the Day rows.

## Phase 6: the planner's next step (FR-009; US4.2)

- [X] T018 Test in `tests/test_guide.py` and `tests/test_charters.py` (where the skill text
  is read): the guide text and `skills/wuwei-plan/SKILL.md` each contain `--card <hash>`,
  `wuwei decision show D-n --widget` and the never-a-host-terminal-command sentence. Run:
  fails.
- [X] T019 Implement the sentence in `cli/wuwei/guide.py` and `skills/wuwei-plan/SKILL.md`
  (and `docs/site/agent.md` where it mirrors the guide); `--card <hash>` in
  `docs/site/reference.md` (decide row, Host terminal actions row, Decision record
  `--widget` sentence). Run `tests/test_guide.py tests/test_charters.py tests/test_docs.py`:
  green.

## Phase 7: invariants (FR-010)

- [X] T020 Test in `tests/test_invariants.py`: `i29` and `i30` on one memo per posture, their
  `INVARIANTS` and `READS` entries, and the `BROKEN` entries `'session id only from the
  environment'` (patch `wuwei.sessions.caller` to read only `current()`) and `'card hash
  ignored'` (patch `wuwei.decision.card_hash` to a constant). Run: `test_table_matches_the_checks`
  fails until the rows exist; the BROKEN walk fails on I29 and I30.
- [X] T021 Implement rows I29 and I30 in `docs/specs/2026-09-24-wuwei-design.md` 9.2, after
  I28. Run `tests/test_invariants.py`: green, the walk within its CPU budget. Then the full
  suite `python -m pytest -q`; check the changed files for em-dashes and emojis.
