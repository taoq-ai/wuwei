# Tasks: Shadow-before-live promotion

**Input**: `spec.md`, `plan.md` in `specs/560-shadow-promotion/`. Test first: each test task
runs red for the expected reason before its implementation task. Run only the named test
files, never the full suite.

## Phase 1: Config and the stored shadow

- [X] T001 Test: `shadow_days` 5 and `shadow_min` 5 defaults; 0 refused for each, in
  `tests/test_cruise.py` (extend `test_cruise_config_defaults_and_ranges`).
- [X] T002 Implement both keys in the `decisions.cruise` schema in `cli/wuwei/workspace.py`.
- [X] T003 Test: `promotion.cruise_shadow` writes a `shadow` row and one ledger line with
  action `shadow`; `cruise.running` raises `ValueError` on an unknown class, a level 0 or 4,
  a negative count and an unknown state in `shadow`; `promotion.cruise_level` drops the
  class's shadow row, in `tests/test_cruise.py`.
- [X] T004 Implement the `shadow` validation in `running` (`cli/wuwei/cruise.py`),
  `cruise_shadow` and the pop in `cruise_level` (`cli/wuwei/promotion.py`).

## Phase 2: The shadow answer at the routing point (US3)

- [X] T005 Test: a class in shadow at L3 (`approach` running at L2): routing a wide-margin
  record gives the same `decision_outcomes` row, `decision.decided` payload, record file and
  output as the same record routed with no shadow; a `decision_shadows` row
  `{class, level 3, option, at}` and one `decision.shadow` event are added. A record that
  leaves `mandate` before `cruise.rule` (one-way) gets no shadow row. Writing
  `decision_shadows` or `decision.shadow` from `wuwei event` is refused as reserved, in
  `tests/test_cruise.py`.
- [X] T006 Implement `rule(..., run=None)`, `cruise.shadow` (`cli/wuwei/cruise.py`), the
  guarded call in `mandate` (`cli/wuwei/commands/decision.py`), and the reserved key and kind
  (`cli/wuwei/state.py`, `cli/wuwei/commands/event.py`).

## Phase 3: Start, score, end, pass (US1, US2)

- [X] T007 Test: update `test_ten_agreements_propose_a_raise`: ten agreements and calibrated
  now start a shadow (row `running`, level 1, scored 0) with a `shadow started` ledger line
  and no card; a second `propose` writes nothing, in `tests/test_cruise.py`.
- [X] T008 Implement the start branch in `propose` (`cli/wuwei/cruise.py`).
- [X] T009 Test: acceptance 1: `approach` at L2 in shadow at L3, five shadowed records whose
  mandate outcomes closed their windows, `WUWEI_NOW` five days after start: `steward.review`
  sets state `passed` with scored 5, agreed 5; the next `propose` writes one raise card whose
  row carries the passed shadow, ends the shadow (`shadow asked D-n`), and a second `propose`
  writes none; `answer(..., 'raise')` lands L3, drops the row, ledger reason
  `raise approved D-n; shadow agreed 5 of 5`. Also: four scored after five days stays
  `running`; five scored on day two stays `running` with counts updated once, in
  `tests/test_cruise.py`.
- [X] T010 Implement `review_shadows` and the passed branch of `propose`, the card row's
  `shadow` key and the `answered` gate and reason (`cli/wuwei/cruise.py`), and the call in
  `steward.review` (`cli/wuwei/steward.py`).
- [X] T011 Test: acceptance 2: one shadowed record undone and answered with another option
  by the owner: `steward.review` sets state `ended`, the ledger line names the record path and
  both options, the level is unchanged, `propose` writes no card and starts no shadow until
  ten fresh agreements after the end; an undone record not yet answered and an open undo
  window are not scored, in `tests/test_cruise.py`.
- [X] T012 Implement the disagreement branch in `review_shadows` and the `since` change in
  `agreements` (`cli/wuwei/cruise.py`).
- [X] T013 Test: update `test_the_owner_raise_lands_and_keep_does_not` and
  `test_a_raise_never_passes_the_configured_level` to go through a passed shadow; a raise
  card without a passed shadow answered `raise` lands nothing, in `tests/test_cruise.py`.
- [X] T014 Make them pass (no new code expected beyond T010; fix only what the tests show).

## Phase 4: The owner sees it (US4)

- [X] T015 Test: `wuwei cruise shadow` prints the header and one row per shadow, `none` when
  empty, exit 0, exit 2 on a damaged `cruise.json`; `cruise shadow` is in
  `commands.READ_ONLY`; the status line reads
  `cruise L2 · shadow approach` for a running shadow; the day report has `## Cruise shadow` with
  the row, `none` otherwise, in `tests/test_cruise.py`.
- [X] T016 Implement the `shadow` action (`cli/wuwei/commands/cruise.py`), its
  `READ_ONLY` entry (`cli/wuwei/commands/__init__.py`), `label` and
  `shadow_lines` (`cli/wuwei/cruise.py`), the report section (`cli/wuwei/report.py`).

## Phase 5: Invariants and docs

- [X] T017 Test: add I13 and I14 checks (`shadow_rule`, memoised raise-card check) to
  `INVARIANTS` in `tests/test_invariants.py`; run it red (table mismatch).
- [X] T018 Add rows I13 and I14 to design 9.2, the 5.8.1 "Shadow promotion" paragraph and the
  status-line and running-level wording in `docs/specs/2026-09-24-wuwei-design.md`; the two
  config rows in `docs/site/configuration.md`; one paragraph in `docs/site/concepts.md`; `cruise shadow`
  in `docs/site/reference.md` and the `docs/site/agent.md` read-only list.
- [X] T019 Run `python -m pytest -q tests/test_cruise.py tests/test_invariants.py
  tests/test_steward.py tests/test_decision.py tests/test_promotion.py
  tests/test_calibration_scores.py tests/test_budget_classes.py tests/test_docs.py` and the
  report and status test files; check written files for em-dashes and emojis.
