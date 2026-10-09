# Tasks: The fixture day for autonomous and supervised, and the invariant table checked against what landed

Test first: each test task is written and run before its paired task, and its first run is
recorded (fails for the expected reason, or, for an acceptance test over merged parts, its
result). Fixtures are neutral (`acme/widget`, `example/project`, item `A`, channels `CREVIEW`,
`C0TEAM`, `C0CLIENT`). No edits to `tests/fakes/day.py`. Run only the touched test files:
`python -m pytest -q tests/test_path_day.py tests/test_invariants.py tests/test_merge.py`.

## Phase 0: the base

- [X] T001 Confirm the base (plan, Step 0): `tests/test_invariants.py` with I1 to I18,
  `tests/test_path_day.py`, `specs/524-merge-grant`, `specs/530-setup-autonomy` and an
  `autonomy` row in `cli/wuwei/interview.py` `QUESTIONS`. If any is missing, stop and report
  that the worktree must be brought to main; build nothing else.

## Phase 1: the shared walk (FR-001)

- [X] T002 Refactor in `tests/test_path_day.py`: `prepare(day, skip=())` and
  `walk(day, card, after=None, looks=1)` out of the fixture and
  `test_the_day_closes_walking_only_next`. Run that test before and after: same result,
  same assertions (refactor of test code; the existing test is its test).

## Phase 2: the autonomous day (US1; FR-002 to FR-006)

- [X] T003 Test in `tests/test_path_day.py`: `ask(day, widget, label)` and
  `test_posture_day` parametrized `Autonomous` (plan, `tests/test_path_day.py` item 4;
  US1.1 to US1.7). Run it.
- [X] T004 (no step failed) If T003 fails on a step: a fix of a few lines at the shared spot (FR-010), its
  failing step being the test, with an invariant row if it changes a rule; otherwise a
  Deferred entry in `specs/530-posture-day/spec.md` naming the step and the reason, and stop
  and report. No assertion is weakened, skipped or marked xfail.

## Phase 3: the supervised day (US2)

- [X] T005 Test in `tests/test_path_day.py`: the `Supervised` parameter of
  `test_posture_day` with the deploy step (US2.1 to US2.3). Run it.
- [X] T006 (no step failed) Same rule as T004 for any failing supervised step.

## Phase 4: the invariant table (US3; FR-007 to FR-009)

- [X] T007 Test `test_no_stale_owner_marks` in `tests/test_invariants.py` (US3.6). Run it:
  it fails naming the `#524` and `#529` `OWNED` notes and the I1 `Owned:` clause.
- [X] T008 In `tests/test_invariants.py`: delete the `#524` `OWNED` rows and add them to
  `EXEMPT` with the merge-family note; re-note the `#529` rows to the follow-up. In
  `docs/specs/2026-09-24-wuwei-design.md` 9.2: the I1 note. In
  `cli/wuwei/guards/__init__.py`: the `MERGE` comment. T007 and
  `test_reason_corpus_has_no_wall` pass.
- [X] T009 Test in `tests/test_invariants.py`: `i3` asserts the `--squash` reason names
  `wuwei merge`, and `test_merge_only_at_the_gated_green_head` over posture x grant x head
  (US3.1). Run them.
- [X] T010 Update the I3 row in design 9.2 (checked by, note).
- [X] T011 Test in `tests/test_invariants.py`: `Rules.record` and `i8` add
  `config set cap 2 --from-card D-1` (US3.2). Run the walk.
- [X] T012 Update the I8 row in design 9.2.
- [X] T013 Test in `tests/test_invariants.py`: `i19`, its `READS` and its `BROKEN` entry
  (US3.3). Run `test_table_matches_the_checks`: it fails, the table has no I19.
- [X] T014 Add row I19 to design 9.2.
- [X] T015 Test in `tests/test_invariants.py`: `i20`, its `READS` and its `BROKEN` entry
  (US3.4); the table test fails on I20.
- [X] T016 Add row I20 to design 9.2.
- [X] T017 Test in `tests/test_invariants.py`: `i21`, its `READS` and its `BROKEN` entry
  (US3.5); the table test fails on I21.
- [X] T018 Add row I21 to design 9.2.
- [X] T018a Test in `tests/test_invariants.py`: `i22` (#557, US3.6), `i23` (#556, US3.7),
  `i24` (#552, US3.8), each with its `READS` and `BROKEN` entry, and the `dispatch.depth`
  clause of `pace_rule` (#567, US3.9). Run `test_table_matches_the_checks`: it fails, the
  table has no I22.
- [X] T018b Add rows I22, I23 and I24 to design 9.2 and #567 to the I15 note.
- [X] T019 Run `test_invariants_hold` and `test_broken_rule_is_caught`: the walk passes
  under 1.0 s CPU with I19 to I24 and each new `BROKEN` entry fails it; if over budget,
  narrow I21 first (plan, Risks).

## Phase 5: finish

- [X] T020 Run `python -m pytest -q tests/test_path_day.py tests/test_invariants.py
  tests/test_merge.py tests/test_e2e_day.py`; both posture days under 60 s. Grep every file
  written for em-dashes, emojis and absolute local paths.
- [X] T021 Record in `specs/530-posture-day/spec.md` Deferred every step T004 or T006 could
  not fix; keep the #529 walls and the orientation text entries.

## Dependencies

T001 before all. T002 before T003 and T005. T003 before T004, T005 before T006. T007 before
T008. Each test task before its paired task: T009/T010, T011/T012, T013/T014, T015/T016,
T017/T018, T018a/T018b. T019 after T018b. Phases 2 to 4 are independent of each other after T002.
