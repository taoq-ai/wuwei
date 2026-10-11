# Tasks: after a gate blocks, next offers the fix round or the decision card and writes the record the gate asked for

**Input**: `specs/732-next-after-block/spec.md`, `specs/732-next-after-block/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Use the helpers already in `tests/test_dispatch.py` (`root`, `built`, `record`, `gate_fix`,
`caps`, `cli`, `build_next`, `fix_events`); an ESCALATE verdict is
`FIX.replace('Verdict: FIX', 'Verdict: ESCALATE') + 'Simplicity: none\nDesign: none\n'`
for quality, a PARK verdict the same with `PARK`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 and 2 - a decision request is a card, a finding is a fix round (P1)

### Tests first

- [X] T001 [US1] In `tests/test_dispatch.py`, add
  `test_issue_acceptance_escalate_writes_the_card_both_commands_name`: `built(root)`, arch
  and security PASS, quality ESCALATE; `monkeypatch.setenv('WUWEI_WORKSPACE', ...)`;
  `cli(capsys, 'dispatch', 'next', 'A')` returns exit 1 and
  `{'action': 'escalate', 'reason': <starts with 'gate quality ESCALATE: '>,
  'decision': 'D-1', 'command': 'wuwei decision route D-1'}`; `build_next(capsys, root)`
  returns the same exit and object; a second `dispatch next` returns the same and
  `decisions/` holds exactly one `D-*.md`; `decision.evaluate` on `D-1` gives Class `park`,
  Recommendation `fix`, Decided-by `seat`; the `quality` initial record carries
  `decision: 'D-1'`; one `gate.card` event (spec US1.1). Run it; it fails on the bare
  escalate.
- [X] T002 [US1] In the same file, add the strict variant: append
  `[security]\nposture = "strict"\n` to `.wuwei/config.toml`; the card is `Decided-by:
  owner`, `D-1` is in `state['decision_routes']`, and both commands print
  `command: wuwei decision show D-1 --widget` (US1.2). Run it; it fails.
- [X] T003 [US1] In the same file, add `test_card_answered_fix_opens_the_round_and_regates_the_asking_gate`:
  T001's state, `dispatch.next_step` once, then `main(['decision', 'route', 'D-1'])`
  (records `fix` under the default autonomous mode); `dispatch next A` answers
  `{'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}`, the item is
  in `fix` and the build action's feedback names `gate-quality-1.md`; after
  `state.transition('A', 'delta', root)`, `dispatch.next_step` answers `gates` with roles
  `['quality']`, and `record(root, 'quality', 'quality-2', PASS + ..., 'delta')` is
  received (US1.3, FR-007). Run it; it fails.
- [X] T004 [US1] In the same file, add `test_card_answered_park_parks_the_item_and_both_commands_name_it`:
  quality PARK instead (Recommendation `park`), `next_step`, route `D-1`; `dispatch next A`
  and `build next A` both exit 1 with `escalate`, `decision: D-1`,
  `command: wuwei decision show D-1 --widget`; the item is `parked`, `blocked`, with
  `decision: 'D-1'` and `resume_phase: 'gate'` (US1.4, FR-006). Run it; it fails.
- [X] T005 [US1] In the same file, change `test_fix_with_park_or_missing_gate_stays_in_gate`
  (line 700) and add one case: a quality PARK received while security is missing answers
  `gates` with roles `['security']` and writes no card (the early return is gone); after
  security PASS the answer is the card's `escalate` with `decision` and `command`. Run it;
  the first assertion fails.
- [X] T006 [US2] (built as one added assertion, no card written, on the existing #666
  test `test_issue_acceptance_build_next_and_dispatch_next_agree_on_a_gate_fix`, which
  already covers both orders) In the same file, add
  `test_issue_acceptance_blocking_finding_without_a_decision_is_a_fix_round_from_both`,
  parametrized on which command runs first (the #666 test at line 1996 is the model): a
  quality FIX, `dispatch next` answers `fix` with `wuwei build next A`, `build next`
  prints the opened round's builder action, and `decisions/` has no `D-*.md` (US2.1). It
  pins today's behaviour and may already pass; keep it.
- [X] T007 [P] [US1] In `tests/test_dispatch.py`, assert
  `EVENT_PRODUCERS['gate.card'] == 'wuwei dispatch next'` (from
  `wuwei.commands.event`, the pattern of `tests/test_consolidation.py:409`) (FR-010). Run
  it; it fails with a KeyError.
- [X] T008 [US1] In `tests/test_invariants.py`, add `i59(case, rules)` per plan.md Design 9
  (posture only, its own workspace per posture, `next_step` twice, one card, command per
  posture, under strict the card in `decision_routes`); register `'I59': i59` in
  `INVARIANTS` and `'I59': (0,)` in `READS`; add the I59 row to the 9.2 table in
  `docs/specs/2026-09-24-wuwei-design.md` (plan.md Design 9). Run the walk; I59 fails.

### Implementation

- [X] T009 [US1] In `cli/wuwei/dispatch.py`, add `CARD`, `_waiting`, `_parked` and `_card`
  (plan.md Design 1).
- [X] T010 [US1] In `cli/wuwei/dispatch.py` `next_step`, delete the early PARK/ESCALATE
  return (lines 361-364) and replace the tail after `results` with the one blocked-gate
  route (plan.md Design 2): raise, round-cap park through `_parked`, card for PARK or
  ESCALATE, its answer (`fix` falls through to `build.open_fix`, `park` parks the item
  with `decision`). `_fix_feedback` names the record's verdict.
- [X] T011 [US1] In `cli/wuwei/dispatch.py`, the initial-verdict tests at lines 350, 359,
  575 (`delta_due`), 633 (`receive`) and 743 (`opinion`) read `!= 'PASS'` / `== 'PASS'`
  instead of `FIX` (plan.md Design 3).
- [X] T012 [P] [US1] In `cli/wuwei/commands/event.py`, add `'gate.card': 'wuwei dispatch next'`
  to `EVENT_PRODUCERS`. T007 passes.
- [X] T013 [US1] Run T001 to T008 and the rest of `tests/test_dispatch.py`; all pass.

## Phase 2: User Story 3 - no round left is a park with its record (P2)

### Tests first

- [X] T014 [US3] In `tests/test_dispatch.py`, change
  `test_issue_acceptance_blocking_trust_finding_at_round_three_parks` (line 1827): the
  cap answer is `escalate` with the same `round cap 2 reached: security still blocks:`
  reason, `decision: 'D-1'` and `command: wuwei decision show D-1 --widget`; the item is
  `parked` with `decision: 'D-1'` and the record's Context holds the trust finding;
  `next_command.resolve` on the `verdicts` row now returns no `plan park` (the item is
  parked); `build_next` and `cli('dispatch', 'next', 'A')` print the same `escalate` with
  `D-1`; `main(['decide', 'D-1', 'keep'])` under a patched `decision.owner_confirm`
  (as other owner-answer tests patch it) resumes the item to `delta` (US3.1, US3.2).
  Run it; it fails.
- [X] T015 [US3] In `tests/test_dispatch.py`, change the three tests that expect exactly
  `{'action': 'escalate', 'reason': 'fix round already used'}` (lines 110, 179 and the
  residual-note test) to expect that reason with a `decision` and the widget command, and
  the item `parked` with that `decision`. Also change
  `test_a_cap_of_one_escalates_the_first_blocking_delta` (line 1857) to assert the
  `decision` key and the parked item. Run them; they fail.
- [X] T016 [P] [US3] In `tests/test_next.py`, change the `escalate` case of
  `test_verdict_rows_return_the_gate_action` (line 584): the answer carries
  `decision: 'D-7'` and `command: 'wuwei decision route D-7'`; the row command is
  `wuwei decision route D-7` and its `why` names `D-7` (US3.3, FR-008). Run it; it fails.
- [X] T017 [P] [US3] In `tests/test_close_parked.py`, add an assertion that
  `plan.dispose(name, 'parked', ...)` leaves `items[name]['decision']` equal to the
  returned id (FR-005). Run it; it fails.

### Implementation

- [X] T018 [US3] In `cli/wuwei/plan.py` `dispose`, link the record:
  `record.update(phase='parked', status='blocked', decision=path.stem)`. T017 passes.
- [X] T019 [US3] In `cli/wuwei/dispatch.py` `next_step`, return `_waiting` for an item at
  `parked` or `escalated` with a linked `decision` before the phase refusal, and park the
  `fix round already used` branch through `_parked` (plan.md Design 2).
- [X] T020 [US3] In `cli/wuwei/commands/build.py` `run`, ask `dispatch.next_step` when the
  build is `done` and the item is at `gate` or `delta`, or at `parked` or `escalated` with
  a linked `decision` (plan.md Design 5).
- [X] T021 [US3] In `cli/wuwei/commands/next.py` `resolve`, the `verdicts` escalate row
  uses the answer's `command` and names its `decision` (plan.md Design 6). T016 passes.
- [X] T022 [US3] Run T014 to T017, `tests/test_next.py`, `tests/test_close_parked.py`,
  `tests/test_report_retro.py` and `tests/test_why.py`; update an expectation only where it
  asserted `unmeasured` or no decision for a `plan park` item.

## Phase 3: User Story 4 - the retro lists blocks and what followed (P3)

- [X] T023 [US4] In `tests/test_report_retro.py` (where the `retro.compile` tests live), add a test seeding `gate_verdicts` with a FIX record (item with
  `builds.<item>.fix_rounds = 1`), an ESCALATE record with `decision: 'D-1'` and a
  `decision_outcomes['D-1']` option `fix`, and a PARK record for an item `parked` with
  `decision: 'D-2'`; the compiled retro has `## Blocks` with the rows
  `fix round 1`, `card D-1: fix` and `parked: D-2`, and a day without blocks prints
  `| none | | | |` (US4.1). Run it; it fails.
- [X] T024 [US4] In `cli/wuwei/retro.py`, add `_blocks(data)` and append it after
  `_second_opinion` in `compile` (plan.md Design 7). T023 passes.

## Phase 4: Docs and the full suite

- [X] T025 In `docs/specs/2026-09-24-wuwei-design.md`, add the #732 amendment line under the
  "Negotiation budget" bullet (plan.md Design 9). In `docs/site/daily.md` steps 4 and 5,
  say what a PARK or ESCALATE verdict returns and what follows its answer.
- [ ] T026 (left to CI, owner 2026-10-10: run only the changed test files) Run the full suite with the task's interpreter: `python -m pytest -q` from the
  repository root; everything passes, the invariant walk included.
- [X] T027 Check every file this feature wrote or changed for em-dashes and emojis and
  remove any; check no absolute local path was written.

## Dependencies

- T001 to T008 before T009 to T012; T009 before T010; T010 before T019.
- T014 to T017 before T018 to T021.
- T023 before T024.
- T025 to T027 last.
