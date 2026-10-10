# Tasks: The agent that asked a card records its answer

Test first: each test task runs and fails for the expected reason before its implementation
task. While building run only the touched files, for example `python -m pytest -q
tests/test_owner_edits.py tests/test_card_confirms.py`; run the full suite once in T017.

Phase 3 needs #599 on main (see plan, Starting point). The other phases do not.

Build status: #599 is not on main, so T008 to T010 (the CLI binds the hash to the record)
stay open. T011 and T011a land without it: both commands parse the hash, and the hook
refuses a hash that is not the owner's recorded answer on that card. T017's full suite is
left to CI.

## Phase 1: the hook lets the planner run decision outcome (FR-001, FR-006; US1.2, US1.3)

- [X] T001 Test in `tests/test_owner_edits.py`:
  `test_planner_records_an_asked_decision_outcome`, parametrized `observe` and `guarded`,
  using `asked_decision(tmp_path, monkeypatch, posture, reply='B')` and `edit`. Each of
  `bin/wuwei decision outcome D-3 B` and the same with `--from-card`, `--card` or `--card=`
  and the recorded answer hash (or its prefix), and `bin/wuwei decide D-3 B --from-card
  <hash>` returns `(0, '')`. An unknown hash (`abcdef012345`) or an empty one is exit 1
  naming the hash and `bin/wuwei decision show D-3 --widget`. Refused (exit 1): the same command with `agent_id='a1'`, with
  `session_id='other'` (through `check_bash`), and `bin/wuwei decision outcome D-3 B
  --from-card D-4` (an id not asked). Run: fails (`decision outcome` refused).
- [X] T002 Test in `tests/test_invariants.py`: `Rules.record` (line 241) checks `bin/wuwei
  decision outcome D-1 once` with its two commands, and `i8` (line 446) zips `('decide',
  'decision outcome', 'config set')`. Run `tests/test_invariants.py`: I8 fails for
  `decision outcome` below strict with a card.
- [X] T003 Implement in `cli/wuwei/guards/protect_state.py`: add `('decision', 'outcome')` to
  `_GATE_EDITS` (line 188) and `'decision'` to the asked-id group check (line 278). Run T001,
  T002, `tests/test_owner_edits.py tests/test_decision.py tests/test_launcher_relevance.py`:
  green.
- [X] T004 `docs/specs/2026-09-24-wuwei-design.md` 9.2 row I8: Checked by adds `bin/wuwei
  decision outcome D-1 once`; Notes add `#661; below strict the planner's refusal names the
  card, never a host-terminal command`.

## Phase 2: a card, never a pasted command, below strict (FR-003; US2.1 hook, US3.2, US4.1)

- [X] T005 Tests in `tests/test_owner_edits.py`. Import `CARD_FIRST` from
  `wuwei.guards.protect_state`. Change the below-strict planner refusals to equal `(1,
  CARD_FIRST)`: lines 202, 259, 266, 297, 310 and the refused branch of 312. Keep the strict
  ones (195, 272, 345) and the seat and other-session ones as they are. Add
  `test_unasked_decision_outcome_names_the_card` (guarded, `ask=False`): `edit('bin/wuwei
  decision outcome D-3 B')` is `(1, CARD_FIRST)`, and `'decision show <id> --widget'` is in
  it, `'host terminal'` is not. Add `test_strict_decision_outcome_prints_it_without_the_hash`:
  strict, asked; `bin/wuwei decision outcome D-3 B --from-card abcdef012345` and
  `... --card=abcdef012345` each give a reason ending `Run it in a host terminal: bin/wuwei
  decision outcome D-3 B`. Run: fails.
- [X] T006 Test in `tests/test_card_confirms.py`:
  `test_hook_config_set_below_strict_keeps_its_reason_without_a_command`: guarded,
  `hook(ws, 'bin/wuwei config set cap 5')` returns exit 1 with the `config set` table
  reason, and `'Run it in a host terminal'` is not in it. `test_hook_under_strict_prints_the_host_terminal_command`
  (line 429) stays as is. Run: fails (the suffix is there).
- [X] T007 Implement in `cli/wuwei/guards/protect_state.py`: the `CARD_FIRST` constant next
  to `GUARD_CONFIG`, and the refusal at line 286 as the plan shows (below strict:
  `reason` for `config`, else `CARD_FIRST`; strict: the command with any `--card` or
  `--from-card` hash words dropped for `decide` and `decision`). Run T005, T006 and
  `tests/test_owner_edits.py tests/test_card_confirms.py tests/test_mcp.py
  tests/test_invariants.py`: green.

## Phase 3: decision outcome takes the card hash (FR-002; US1.1, US2.2, US3.1; needs #599)

- [ ] T008 Test in `tests/test_card_confirms.py`:
  `test_decision_outcome_records_from_the_card_hash` (issue acceptance 1), parametrized
  `observe` and `guarded`. Save `test_decision.VALID` with `Decided-by: owner` and
  `Reversibility: one-way` as D-1, `main('decision', 'route', 'D-1')`, answer it with
  `answer(ws, 'D-1', 'D-1: Which fix?', 'Defer until tomorrow')`; `WUWEI_SESSION_ID` unset,
  `sys.stdin` an `io.StringIO()`, `no_terminal(monkeypatch)`. With `card =
  decision.card_hash('D-1', fields)`: `hook(ws, f'bin/wuwei decision outcome D-1 B
  --from-card {card}')` is `(0, '')`; `main('decision', 'outcome', 'D-1', 'B',
  '--from-card', card)` is 0; the record has `Decided-by: owner` and Notes `in the planner
  session`; the same hook call with `agent_id='a1'` is exit 1. Run: fails (argparse rejects
  `--from-card`).
- [ ] T009 Test in `tests/test_card_confirms.py`:
  `test_decision_outcome_with_an_unknown_hash_is_refused` (issue acceptance 3): same setup,
  `main('decision', 'outcome', 'D-1', 'B', '--from-card', '000000000000')` exits 1, stderr
  names `bin/wuwei decision show D-1 --widget`, the record still reads `Outcome: pending`,
  no prompt. Run: fails.
- [ ] T010 Test in `tests/test_card_confirms.py`:
  `test_strict_owner_runs_decision_outcome_as_today` (issue acceptance 2): same setup under
  `strict(ws)`; the hook refuses the planner's `... --from-card <card>` with a reason ending
  `Run it in a host terminal: bin/wuwei decision outcome D-1 B`; `main('decision',
  'outcome', 'D-1', 'B')` with `_host_confirm` recording its call and returning True exits
  0 with one prompt and Notes `at the host terminal`. Run: the CLI half passes (pins today's
  behaviour); the hook half passes after T007.
- [X] T011 Implement: `cli/wuwei/commands/decision.py` `register` (line 29):
  `outcome.add_argument('--card', '--from-card', dest='card', metavar='HASH', help=...)`;
  `cli/wuwei/commands/decide.py`: the same argument (#599 merges onto it). Unused by the CLI
  until #599. Test: `tests/test_decision.py::test_outcome_accepts_the_card_hash` (both
  commands parse `--from-card` and record).
- [X] T011a Implement in `cli/wuwei/guards/protect_state.py` `_owner_action`: below strict, a
  `decide` or `decision outcome` card hash passes only when a gate topic is `D-n=<hash>` or
  starts with it; otherwise exit 1 naming the hash and `bin/wuwei decision show D-n
  --widget` (issue acceptance 3, hook side). Tested by T001.

## Phase 4: the parked-build line names the card (FR-004; US4.2)

- [X] T012 Test in `tests/test_build.py`: `test_build_park_is_recorded_lintable_decision`
  (line 224) also asserts the captured stderr contains `bin/wuwei decision show D-2
  --widget` and does not contain `host terminal` or `decisions/D-2.md`. Run: fails.
- [X] T013 Implement in `cli/wuwei/commands/build.py`: `parked_line(item, action)` as the
  plan shows, used at lines 36 and 497. Run T012 and `tests/test_build.py
  tests/test_build_next.py`: green.

## Phase 5: doctor lists answered cards not recorded (FR-005; US5)

- [X] T014 Test in `tests/test_doctor.py`: `test_answered_cards_row`. With the doctor `ws`
  fixture and today's state: no answer topics gives `answered cards` ok, value `none`. Add
  `D-2` and `D-2=<64 hex>` to a session's `gate_asked` (through `state._write_state`): warn,
  value names D-2, fix names `decision show <id> --widget`. Add an owner outcome for D-2
  (`decision_outcomes.D-2.decided_by = owner`): ok. A topic
  `sessions.card_topic('D-3', 'Undo')` with a mandate outcome for D-3: ok. A pending draft
  (built as `tests/test_owner_edits.asked_draft` builds it) with a `:send` topic: warn naming
  the draft id. `drafts.read` monkeypatched to raise `ValueError('drafts: invalid queue')`:
  unmeasured with that reason. Also add `answered cards` after `traces` in
  `test_day_rows`'s names list (line 595). Run: fails (no row).
- [X] T015 Implement in `cli/wuwei/commands/doctor.py`: `_unrecorded(root)` next to
  `_legacy_traces` and the row in `_day` after `trace decisions`, as the plan shows. Run
  T014 and `tests/test_doctor.py`: green.

## Phase 6: docs and the whole suite (FR-007)

- [X] T016 Docs: `docs/site/reference.md` host terminal table row for `decision outcome`
  (line 421) gets the `decide` row's planner note, and the doctor Day list (line 235) adds
  `answered cards not recorded`; `docs/site/concepts.md` line 212 says an asked decision goes
  in with `wuwei decide` or `wuwei decision outcome`. Run `tests/test_docs.py
  tests/test_guide.py`: green.
- [ ] T017 Run the full suite with `python -m pytest -q`; everything passes and
  `tests/test_invariants.py::test_invariants_hold` stays within its CPU budget. Check every
  file written for em-dashes and emojis and remove any.
