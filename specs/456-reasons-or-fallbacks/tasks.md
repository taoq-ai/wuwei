# Tasks: the next-step test also collects `x or 'literal'` fallbacks

**Input**: `specs/456-reasons-or-fallbacks/` (spec.md, plan.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. No absolute local paths, emojis or em-dashes in any file.

## Phase 1: US1, the collector sees `or` fallbacks

- [X] T001 Test, `tests/test_reasons.py`: add `test_collector_finds_an_or_fallback_wall`
  (plan Design 2; spec US1 scenarios 1 to 4). Run `python -m pytest -q
  tests/test_reasons.py -k or_fallback` (fails: the collector returns `[]` for the three
  `or 'literal'` sources).
- [X] T002 Implement the `BoolOp(Or)` branch in `_text`, `tests/test_reasons.py` (plan
  Design 1). Rerun T001; pass.

## Phase 2: US2, the fallbacks it finds name a next step

- [X] T003 Test (no new code; the T002 collector is the test): run `python -m pytest -q
  tests/test_reasons.py -k every_reason_names_a_next_step` (fails: 19 walls, including
  `shepherd.py:168: branch protection unmeasured` and `shepherd.py:178: branch protection
  unmeasured`; spec US2 scenario 1). Record the list in the build notes.
- [X] T004 Implement the two shepherd fallbacks in `cli/wuwei/shepherd.py` `ping_gate`
  (plan Design 3, first row). Rerun T003; the shepherd lines are gone from the list.
- [X] T005 Implement the seat-facing fallbacks (plan Design 3), one file at a time:
  `cli/wuwei/brief.py`, `cli/wuwei/commands/build.py`, `cli/wuwei/commands/config.py` (two
  sites), `cli/wuwei/commands/runtime.py`, `cli/wuwei/consolidation.py`,
  `cli/wuwei/control_plane.py` (two sites), `cli/wuwei/inbox.py`, `cli/wuwei/integrity.py`,
  `cli/wuwei/obligations.py`, `cli/wuwei/registry.py`, `cli/wuwei/scanner.py`,
  `cli/wuwei/steward.py`. Rerun T003 after each; the list shrinks.
- [X] T006 Implement the three person-facing fallbacks in `cli/wuwei/commands/doctor.py`
  (`_dry`, `_reconfirm_preview`, `_promote_preview`; plan Design 3). Rerun `python -m pytest
  -q tests/test_reasons.py`; all pass (spec US2 scenarios 2 and 3).

## Phase 3: Polish

- [X] T007 Run the tests of the touched modules: `python -m pytest -q tests/test_shepherd.py
  tests/test_brief.py tests/test_build.py tests/test_build_next.py
  tests/test_config_failure.py tests/test_doctor.py tests/test_runtime.py
  tests/test_runtime_cli.py tests/test_consolidation.py tests/test_control_plane.py
  tests/test_inbox.py tests/test_integrity.py tests/test_obligations.py
  tests/test_steward.py`; pass.
- [X] T008 Run the full suite, `python -m pytest -q`; pass. Check every changed file for
  em-dashes, emojis and absolute local paths; remove any.
