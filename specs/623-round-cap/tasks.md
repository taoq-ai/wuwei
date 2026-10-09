# Tasks: a round cap for every item kind

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the existing fixtures in `tests/test_dispatch.py` (`root`, `record`, `built`,
`gate_fix`, `tiered`, `opinion_fix_round`) and neutral item names and paths; no test reaches
git or the network. Cap settings go into the fixture's `.wuwei/config.toml` as a `[gates]`
table. Run the touched test files, then the full suite.

## Phase 1: the cap is configured and read in one place (FR-001; US3.2)

- [X] T001 Tests in `tests/test_dispatch.py`: `dispatch.max_rounds` returns 2 at the
  defaults; `gates.max_rounds = 1` gives 1; `gates.tier_max_rounds.light = 2` with
  `max_rounds = 1` gives 2 for a row whose recorded tier is light and 1 for standard and for
  an untiered row. `dispatch.rounds_used` returns the build record's `fix_rounds`, 0 without
  a build, and at least 1 in phase delta. A `[gates] max_rounds = 0` config fails to load
  (minimum 1).
- [X] T002 Implement the two schema entries in `cli/wuwei/workspace.py` and `max_rounds`,
  `rounds_used` in `cli/wuwei/dispatch.py` (plan, Design). T001 passes.

## Phase 2: `open_fix` counts, caps and opens a round from delta (FR-002, FR-003; US2.2, US3.1)

- [X] T003 Tests in `tests/test_dispatch.py` (the `gate_fix` setup): after the first round
  the build record has `fix_rounds == 1` and the `build.fix_opened` payload has `round: 1,
  cap: 2`; with `max_rounds = 1` a second `build.open_fix` raises `round cap 1 reached`; at
  the default cap, an item in phase delta (build done) opens round two: phase `fix`,
  `fix_rounds == 2`, payload `round: 2`, and each gate that had a `delta` record now has that
  record under `initial` and its round-one record under `round1`, while a gate with no
  delta record is untouched. A fresh round-two brief is named `A-gate-fix-2`. A third
  `open_fix` at the default cap raises `round cap 2 reached`.
- [X] T004 Implement `dispatch.rotate` and the `open_fix` changes in
  `cli/wuwei/commands/build.py` (cap, count, `delta` phase, brief name, rotate inside the
  state write, payload). T003 passes.

## Phase 3: `dispatch next` runs the rounds to the cap (FR-004, FR-005; US1, US2.1, US3.1)

- [X] T005 Test in `tests/test_dispatch.py`, the #623 acceptance for a document item
  (recorded gates `{'tier': 'light', 'roles': ['goal'], ...}`, `built(root)`): goal FIX
  (blocking) at round one gives `fix`; after the move to delta, a blocking goal delta gives
  `fix` for `['goal']` (round two opened, `round1` kept); after the move to delta again the
  action asks for `['goal']` and its delta seat continues the same goal seat with the
  `Re-read:` feedback; a third verdict whose findings are all `blocks: no` gives `raise` with
  those notes; `next.resolve` on the `verdicts` row returns the shepherd brief command
  carrying them as `Review note:` lines.
- [X] T006 Test in `tests/test_dispatch.py`: a standard code item (three gates) at the
  default cap whose security gate still blocks at round three (an agent-surface style
  trust-boundary finding, neutral text) gives `escalate` with a reason starting
  `round cap 2 reached: security still blocks:`, containing the finding's first line and
  `unpark after a design change`; `next.resolve` turns it into
  `wuwei plan park A --reason '<that reason>'`, and `plan.dispose('A', 'parked', reason)`
  writes a record whose `Context:` carries the finding.
- [X] T007 Test in `tests/test_dispatch.py`: with `max_rounds = 1`, a blocking delta after
  the first round gives `escalate` (`round cap 1 reached`), no second `build.fix_opened`.
  Update `test_blocking_delta_escalates_and_bad_verdict_is_unmeasured` and
  `test_second_opinion_fix_opens_the_fix_round_and_its_delta_escalates` to set
  `max_rounds = 1` and expect the new reason.
- [X] T008 Implement `_fix_feedback` and the new `next_step` tail in
  `cli/wuwei/dispatch.py`. T005 to T007 pass.

## Phase 4: readers of the moved records (FR-007)

- [X] T009 Test in `tests/test_pr_guards.py`: after a two-round history (one gate passed at
  round one, one gate moved, its third verdict PASS at the final head), `_recorded_gates`
  returns 0 at the final head; with every gate moved it still returns 0; round-one records
  at different heads still raise `initial gate verdicts disagree on HEAD`.
- [X] T010 Implement the round-one head check in `cli/wuwei/guards/pr.py`. T009 passes.
- [X] T011 Test in `tests/test_report_retro.py`: with a second opinion whose round-one
  record was moved to `round1`, the retro's `## Second opinion` table pairs it with the base
  gate's round-one findings, not the later round's.
- [X] T012 Implement the round-one pairing in `cli/wuwei/retro.py` and the `RESERVED`
  producer text in `cli/wuwei/state.py`. T011 passes.

## Phase 5: no scope widening (FR-006; US4)

- [X] T013 Test in `tests/test_process_depth.py` (next to the feedback assertions at lines
  290-296): the standard delta feedback contains `did not change is blocks: no, unless it is
  a trust-boundary security finding`; the light `Re-read:` feedback does not.
- [X] T014 Implement the sentence in `dispatch._delta_feedback`. T013 passes.

## Phase 6: the report counts rounds (FR-008; US5)

- [X] T015 Tests in `tests/test_report_retro.py`: two `build.fix_opened` events for `A`
  (`round` 1 and 2, `cap` 2) and one for `B` (`round` 1, `cap` 2) give `## Rounds` with
  `- A: 2 fix rounds, round cap 2 reached` and `- B: 1 fix round`; no such event gives no
  `## Rounds` section.
- [X] T016 Implement `round_lines` and the section in `cli/wuwei/report.py`. T015 passes.

## Phase 7: invariant, charters and docs (FR-009, FR-010)

- [X] T017 Test: add `i35` to `tests/test_invariants.py` (plan, I35) and the I35 row to the
  design spec 9.2 table; run it and see it fail only if T002 or T004 is reverted.
- [X] T018 Charter: rewrite `charters/_common.md` rule 5 (plan, Charters and docs), bump its
  version to 1.8.0, run `bin/wuwei agents build`; the charter and agents tests pass.
- [X] T019 Docs: `docs/site/configuration.md` rows, `templates/workspace/config.toml`
  `[gates]` lines, `docs/site/concepts.md` negotiation loops sentence, the hero alt text in
  `README.md`, `docs/site/index.md` and both `docs/site/assets/hero-*.svg` `<desc>`;
  `tests/test_docs.py` passes.

## Phase 8: full suite

- [X] T020 Run the full suite. Fix any other fixture that encoded the one-round budget by
  setting `max_rounds = 1` (walking days in `tests/test_path_day.py` and
  `tests/test_e2e_day.py` included), never by weakening a cap or park expectation. Check every
  written file for em-dashes and emojis.
