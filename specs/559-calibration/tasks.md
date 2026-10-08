# Tasks: Confidence calibration per class and per role

**Input**: `spec.md`, `plan.md` in `specs/559-calibration/`. Test first: each test task runs
red for the expected reason before its implementation task. Run only the named test files.

## Phase 1: Config and record fields

- [X] T001 Test: `calibration_threshold` 0.15 and `calibration_min` 10 defaults; 0, 1 and -0.1
  refused with the budget_share message shape, in `tests/test_calibration_scores.py`.
- [X] T002 Implement the two keys and the range check in `cli/wuwei/workspace.py`.
- [X] T003 Test: a record with `Role: builder` lints OK, `Role: wizard` is refused, a
  two-line Role is refused; `seat_outcome` carries `confidence` and `role`, and a routed
  mandate record's `decision.decided` payload carries both, in
  `tests/test_calibration_scores.py`.
- [X] T004 Implement `Role` in `OPTIONAL`, the one-line check and the role check, and
  `confidence`/`role` in `seat_outcome`, in `cli/wuwei/decision.py`; `Role: builder` in
  `template()` in `cli/wuwei/commands/decision.py`. Fix any exact-dict expectation in
  `tests/test_decision.py` and `tests/test_decision_classes.py` this changes.

## Phase 2: Scoring (US1, US2)

- [X] T005 Test: `calibration_scores.measure` on 12 high with 5 outcomes 0 (0.343,
  uncalibrated), 10 high all 1 (0.01, calibrated), 9 high all 1 (too few), empty (None, too
  few), in `tests/test_calibration_scores.py`.
- [X] T006 Implement `FORECAST` and `measure` in `cli/wuwei/calibration_scores.py`.
- [X] T007 Test: `budget_classes.select(..., every=True)` returns mandate and seat answers
  with confidence, role and undo_until; `every=False` output unchanged on the
  `tests/test_budget_classes.py` fixtures, in `tests/test_calibration_scores.py`.
- [X] T008 Implement the `every` keyword and the three answer keys in
  `cli/wuwei/budget_classes.py`.
- [X] T009 Test: `scored` and `table`: 12 high `defer` answers with 5 reversed or undone give
  a `defer` row uncalibrated with 5 broke labels; an answer inside its undo window and one
  without confidence are not scored; 10 stood `Role: builder` answers give a calibrated
  builder row; a damaged events.jsonl raises ValueError, in
  `tests/test_calibration_scores.py`.
- [X] T010 Implement `scored` and `table` in `cli/wuwei/calibration_scores.py`.

## Phase 3: Stored states, cap and promotion (US1)

- [X] T011 Test: `promotion.calibration` writes the `calibration` key and one ledger line;
  `cruise_level` keeps the key; `cruise.running` refuses an unknown class or a non-list in it;
  `evaluate` writes only when the sets change (second run, no new ledger line), in
  `tests/test_calibration_scores.py`.
- [X] T012 Implement `promotion.calibration` in `cli/wuwei/promotion.py`, the `running`
  validation in `cli/wuwei/cruise.py`, `evaluate` in `cli/wuwei/calibration_scores.py`, and
  the call in `steward.review` in `cli/wuwei/steward.py`.
- [X] T013 Test (acceptance US1.1, US1.2): with `defer` stored uncalibrated and running L3,
  `cruise.level` returns 1; after it returns, 3; a class with 10 agreements and `too few` or
  `uncalibrated` gets no raise card from `cruise.propose`, a calibrated one does, in
  `tests/test_calibration_scores.py`.
- [X] T014 Implement the cap in `cruise.level` and the block in `cruise.propose` in
  `cli/wuwei/cruise.py`.

## Phase 4: Routing and status line (US2, US3)

- [X] T015 Test (acceptance US2.1, US3.1, US3.2): `cisr(..., ambiguous=True)` on a Routine
  record returns Exploratory and on a Consequential one Strategic; `decision route` of a
  `Role: builder` Consequential record goes to the owner (a route row, exit 0, never a
  refusal) while builder is stored uncalibrated and is taken under mandate when calibrated;
  the routed row names `uncalibrated: builder`; the status line shows `uncalibrated builder`
  and drops it after the role returns, in `tests/test_calibration_scores.py`.
- [X] T016 Implement `ambiguous` in `cisr`, `uncalibrated` and its use in `route_owner` in
  `cli/wuwei/decision.py`; its use in `mandate` in `cli/wuwei/commands/decision.py`; the
  status part in `cruise.label` in `cli/wuwei/cruise.py`.

## Phase 5: Command, report, retro (US4)

- [X] T017 Test: `wuwei cruise calibration` prints the header and rows, exits 1 with an
  uncalibrated row, 0 without, 2 on a damaged stream, in `tests/test_calibration_scores.py`.
- [X] T018 Implement the `calibration` action in `cli/wuwei/commands/cruise.py`.
- [X] T019 Test: the day report and the retro carry `## Calibration` with the table and the
  uncalibrated role line naming its broken records, in `tests/test_calibration_scores.py`.
- [X] T020 Implement `lines` in `cli/wuwei/calibration_scores.py` and the section in
  `cli/wuwei/report.py` and `cli/wuwei/retro.py`.

## Phase 6: Invariant, charter, design and docs

- [X] T021 Test: invariant I12 in `tests/test_invariants.py`: `measure` gives the acceptance
  states, a stored uncalibrated class runs at most L1 and a too-few class is not capped, and
  `cisr(..., ambiguous=True)` only moves a record toward the owner (Routine to Exploratory,
  Consequential to Strategic); add `'I12': i12` to `INVARIANTS`.
- [X] T022 Add row I12 to design 9.2 in `docs/specs/2026-09-24-wuwei-design.md`, the 5.8
  `Role:` bullet, the 5.8.1 "Calibration" paragraph, config keys and status part.
- [X] T023 Add `Role:` to `charters/_common.md` line 27 and regenerate `agents/` with
  `python3 -P -m wuwei agents build`; run `tests/test_agents.py tests/test_charters.py`.
- [X] T024 Docs: `docs/site/concepts.md`, `reference.md`, `daily.md`, `configuration.md`;
  run `tests/test_docs.py`.

## Phase 7: Verify

- [X] T025 Run only: `python -m pytest -q tests/test_calibration_scores.py
  tests/test_budget_classes.py tests/test_cruise.py tests/test_decision.py
  tests/test_decision_classes.py tests/test_report_retro.py tests/test_retro.py
  tests/test_signal_status.py tests/test_config_failure.py tests/test_agents.py
  tests/test_charters.py tests/test_docs.py tests/test_invariants.py tests/test_steward.py`.
  Check written files for em-dashes, emojis and absolute local paths.
