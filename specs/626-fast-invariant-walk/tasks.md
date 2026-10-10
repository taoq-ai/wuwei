# Tasks: the invariant walk runs with headroom under its budget

Test first: each test task runs and fails for the expected reason before its
implementation task. Every file below is `tests/test_invariants.py` unless named. No
production file changes. Run the file, then the full suite.

## Phase 0: baseline

- [ ] T001 Take the baseline per `quickstart.md` on `main` (file alone and suite up to this
  file, at least 10 walks each). Keep the medians for T012.

## Phase 1: the overhead is asserted and named (FR-005, FR-006; US2.1)

- [ ] T002 Test in `tests/test_invariants.py`: add `test_walk_overhead` as in the plan
  (no-op checks over the same READS and PARTS, a dummy world, `elapsed < OVERHEAD * BUDGET`,
  message with the cost per case). Run it: it fails with `NameError` on `OVERHEAD` or
  `BUDGET`.
- [ ] T003 Implement in `tests/test_invariants.py`: the `BUDGET = 1.0` and
  `OVERHEAD = 0.05` constants, and `assert elapsed < BUDGET` in `test_invariants_hold`
  (same value as today). T002 passes; set `OVERHEAD` tiny once to read the message names
  the per-case cost, then restore it.

## Phase 2: nothing but the rules inside the clock (FR-004; US1.3, US2.2)

- [ ] T004 Test in `tests/test_invariants.py`: in `test_invariants_hold`, record
  `set(sys.modules)` after `gc.freeze()` and assert after the clock that the walk imported
  nothing, naming the modules. Run the file alone: it fails listing the modules imported
  inside the walk (about 30, `wuwei.interview` and `zoneinfo` among them).
- [ ] T005 Implement in `tests/test_invariants.py`: `WALK_IMPORTS` (plan, section 4)
  imported with `import_module` before `gc.collect()`, and `workspace._CONFIGS.clear()`
  before the clock with its comment. T004 passes with the file alone and in the suite run
  up to this file (`tests/test_[a-i]*.py`, after `test_hooks` drops the guard modules).

## Phase 3: no repeated rule call (FR-001, FR-002, FR-003; US1.2)

These are behaviour-preserving cuts; the characterisation tests are the existing ones, run
green before and after each change.

- [ ] T006 Test: run `test_invariants_hold`,
  `test_broken_rule_is_caught[host cap of one]` and
  `test_broken_rule_is_caught[a fix round past the cap]` on the unchanged invariants; they
  pass.
- [ ] T007 Implement in `tests/test_invariants.py`: `Rules.record` runs its four
  `check_bash` calls through an inner `checks()` memoised first on `('record checks',
  posture)` only (wrong on purpose): `test_invariants_hold` fails on I8 for the answered
  grants (`grant=asked ... I8 decide passes for the planner False (expected True)`, checked
  on the prototype), so the walk catches a key that drops what the guard reads. Then key it
  `('record checks', posture, grant != 'none')` with the comment from the plan (section 1).
  The T006 tests pass.
- [ ] T008 Implement in `tests/test_invariants.py`: I20 reuses the budget-0 result as
  `plain` (plan, section 2). The T006 tests pass, `host cap of one` included.
- [ ] T009 Implement in `tests/test_invariants.py`: I35's `max_rounds` half parses once per
  cap and rotation (plan, section 3). The T006 tests pass, `a fix round past the cap`
  included.

## Phase 4: verify

- [ ] T010 Run `python -m pytest -q tests/test_invariants.py` and the full suite with the
  pipeline interpreter; everything passes.
- [ ] T011 Cold run (`quickstart.md` step 5): the import assertion still passes.
- [ ] T012 A/B per `quickstart.md` against T001: the medians meet SC-002. If they miss,
  report the figures; do not touch the budget, a case or an assertion.
- [ ] T013 Check the changed files for em-dashes, emojis and absolute local paths.
