# Tasks: An answer on an Ask card is the confirmation of a config write

Test first: each test task is written, run and seen failing for the expected reason before
its implementation task. Fixtures are neutral (`acme/widget`, planner session `S-planner`,
records built like `tests/test_decision.py`'s `VALID`). New tests go in
`tests/test_card_confirms.py` unless a task names another file; PostToolUse payloads and
the planner registration are built as in `tests/test_owner_edits.py` (`gate`,
`record_gate`); hook checks call `check_bash` in process as `tests/test_owner_actions.py`
does. Commands run as `run(Namespace(...))`, never a subprocess.

## Phase 1: the card answer is recorded (FR-001, FR-002)

- [X] T001 Test: `sessions.card_topic('CAP', ' 5 (Recommended) ')` equals
  `card_topic('CAP', '5')` and is `CAP=<64 hex>`; `card_answered` is true for the planner
  session after the topic is in its `gate_asked`, false for another session, false with no
  session id, false under strict.
- [X] T002 Implement `card_topic` and `card_answered` in `cli/wuwei/sessions.py`.
- [X] T003 Test: `record_gate` with a Morning gate question (header `CAP`, citing today's
  `plan.md`) answered `5` adds `card_topic('CAP\n<question>', '5')` (keyed to the exact
  question) to the planner row; a `D-1`
  question answered `cap = 5 (Recommended)` adds `D-1` and `card_topic('D-1', 'cap = 5')`;
  an unanswered question adds no answer topic; a seat payload (`agent_id`) and a non
  planner session add nothing; the Goals, Voice and draft topics of the existing tests in
  `tests/test_owner_edits.py` and `tests/test_drafts.py` are unchanged.
- [X] T004 Implement `_answer` and the answer topic in `record_gate`
  (`cli/wuwei/guards/decision.py`); `_draft_answer` calls `_answer`.

## Phase 2: interview cards (US1; FR-003, FR-004, FR-005)

- [X] T005 Test in `tests/test_interview.py`: the id list gains `cap`, `seats`, `tier`,
  `learn` (update the pinned list); every header in `QUESTIONS` is unique; the key
  assertion accepts the top-level schema key `cap`; `effects('cap', '7') == {'cap': 7}`,
  `effects('cap', '0')` and `effects('seats', 'x')` raise; `settings({'cap': '5'}, config)
  == [((), 'cap', 5)]` and `describe` prints `cap = 5`; each new choice settles into a
  config that `load_config` accepts.
- [X] T006 Implement the four rows, `_count`, the `gates` header `Review depth`, the
  `settings`/`describe` key test and `card_for` in `cli/wuwei/interview.py`.
- [X] T007 Test (US1.4): `calibrate --questions` with no ids prints only unanswered rows
  (as today); after `cap` is recorded in an earlier day's `interview.json`,
  `calibrate --questions cap seats` prints the `CAP` and `Seats` widgets, each with record
  `wuwei calibrate --answer "<id>=<label>"`.
- [X] T008 Implement `--questions [ID ...]` in `cli/wuwei/commands/calibrate.py`
  (`nargs='*'`, `is not None` tests) and `widgets(root, repos, ids=())` in
  `cli/wuwei/interview.py`.
- [X] T009 Test (US1.1, US1.2): guarded, planner session, the `CAP` card answered `5`
  through `record_gate`; `calibrate --answer cap=5` exits 0, `config.toml` has `cap = 5`,
  the injected confirm is never called and `/dev/tty` is not opened (monkeypatch
  `integrity._host_confirm` to fail the test), one `config.set` event
  `{"keys": ["cap"], "card": "cap"}`; the same for `seats=6` (`host.seats = 6`),
  `tier=Ask` (`outbound.default_tier = "ask"`) and `learn=Off` (`outbound.learn = "off"`).
- [X] T010 Test (US1.3, US3.4): the card answered `3` and `calibrate --answer cap=5`, or
  strict with the card answered `5`: `interview.json` records the answer, `config.toml` is
  unchanged, no `config.set` event, and the output has the `bin/wuwei config promote`
  `Next:` line.
- [X] T011 Implement the card write in `_interview` (`cli/wuwei/commands/calibrate.py`) and
  `setup.card_write` in `cli/wuwei/commands/setup.py`.

## Phase 3: decision cards (US2; FR-006, FR-010)

- [X] T012 Test: `setup.assignment('cap = 5') == ('cap', 5)`,
  `assignment('outbound.default_tier = "ask"') == ('outbound.default_tier', 'ask')`;
  `assignment('Keep')`, `assignment('cap = five')` and `assignment('repos.0 = 1')` are
  `None`.
- [X] T013 Test (US2.1): guarded; today's `D-1` (`Class: other`, `Decided-by: owner`, options
  titled `cap = 5` and `cap = 3`), routed with `decision route D-1` under the default
  autonomous mode (it prints `owner`); the planner asked it and the owner answered `cap = 5`;
  `config set cap 5 --from-card D-1` with `WUWEI_SESSION_ID` the planner exits 0,
  `config.toml` has `cap = 5`, `_host_confirm` is never called, `decision_outcomes['D-1']`
  is the owner's with the `cap = 5` option, events hold `decision.decided` and
  `config.set` `{"keys": ["cap"], "card": "D-1"}`; a rerun exits 0 with `No config.toml
  changes` and no second `decision.decided`.
- [X] T014 Test (US2.2, US2.3, edge cases): answered `cap = 3` then `config set cap 5
  --from-card D-1`; no option `cap = 7` for `config set cap 7 --from-card D-1`; a card
  never asked; an `Other` text answer: each exits 1, writes nothing, and the message names
  `bin/wuwei decision show D-1 --widget`. A `D-1` not routed: config written, exit 1 with
  `route this pending owner decision first`; after `decision route D-1` a rerun records it.
- [X] T015 Implement `setup.assignment` and the card path of `set_value` in
  `cli/wuwei/commands/setup.py`, and `--from-card` in `cli/wuwei/commands/config.py`
  (`register`).
- [X] T016 Test (US2.4): `decision show D-1 --widget` on the config record prints record
  `wuwei config set <key> <value> --from-card D-1`; on `VALID` it prints
  `wuwei decide D-1 "<label>"` (unchanged).
- [X] T017 Implement `CONFIG_RECORD` in `cli/wuwei/commands/decision.py` (`show`).

## Phase 4: the hook and strict (US2.5, US3; FR-007, FR-009, FR-012)

- [X] T018 Test in `tests/test_owner_actions.py` style: the planner session with `D-1` in
  its gate topics, guarded: `bin/wuwei config set cap 5 --from-card D-1` and
  `--from-card=D-1` pass `check_bash`; `config set cap 5` (no card), `--from-card D-2`
  (not asked), a seat payload (`agent_id`) and an `xargs` form are refused as today; under
  strict the planner's call is refused and the reason ends `Run it in a host terminal:
  bin/wuwei config set cap 5 --from-card D-1` (the command as typed); a guard key (`outbound.default_tier`) with an asked card passes.
- [X] T019 Implement the `_GATE_EDITS` entry, the `--from-card` pass and the reason texts
  in `cli/wuwei/guards/protect_state.py`.
- [X] T020 Test (US3.2, US3.3): strict, session set: `config set cap 5 --from-card D-1`
  exits 1 naming `bin/wuwei config set cap 5` for a host terminal, nothing written; strict,
  no session id, injected `confirm` returning True: the card is ignored, the confirm is
  called once and the value is written (prompt path as today).
- [X] T021 Implement the strict branch of `set_value` (`cli/wuwei/commands/setup.py`).

## Phase 5: no empty answer in a session (US4; FR-008)

- [X] T022 Test: session set, guarded, no card: `config set cap 5` exits 1, nothing
  written, `_host_confirm` not called, stderr names `bin/wuwei calibrate --questions cap`;
  `config set owner.name '"Pat"'` names the decision form `--from-card D-n`; strict names
  `bin/wuwei config set cap 5` for a host terminal; no message contains `empty answer` or
  `run it again`. No session id with an injected confirm: today's prompt path.
- [X] T023 Implement the session branch of `set_value` (`cli/wuwei/commands/setup.py`).

## Phase 6: event kind and docs (FR-011, FR-013)

- [X] T024 Test: `bin/wuwei event config.set '{}'` is refused naming its producer
  (`tests/test_cli.py` or the existing event-command test file); `signal.classify` on a
  `config.set` event returns the same tier as `decision.decided` (`SILENT`).
- [X] T025 Implement the producer row in `cli/wuwei/commands/event.py` and the kind in
  `cli/wuwei/signal.py`.
- [X] T026 Test in `tests/test_docs.py`: design 5.2 `Records` names `#529` and
  `--from-card`; `skills/wuwei-plan/SKILL.md` names `calibrate --questions cap seats` and
  `--from-card`; `docs/site/security.md` no longer says guard settings never change from an
  agent tool without naming the card.
- [X] T027 Update `docs/specs/2026-09-24-wuwei-design.md` (5.2), `skills/wuwei-plan/SKILL.md`,
  `docs/site/concepts.md`, `docs/site/security.md`, `docs/site/configuration.md`;
  regenerate the guide output if a test pins it.

## Phase 7: finish

- [X] T030 Review fix: an unrelated Morning gate question with header `Posture` answered
  `Observe` confirms no write for `calibrate --answer posture=Observe` (calibrate keys the
  card to the widget question); a `D-n` card that also cites the gate still records `D-n`.

- [X] T028 (not applicable: no `tests/test_invariants.py` on this base) If `tests/test_invariants.py` exists on the base, add the FR-006, FR-007 and
  FR-009 invariants to design section 9 and to that test (test first).
- [X] T029 Run `python -m pytest -q` from the repository root; everything passes. Check
  the changed files for em-dashes, emojis and absolute local paths.
