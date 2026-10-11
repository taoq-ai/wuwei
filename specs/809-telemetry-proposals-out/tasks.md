# Tasks: delete the telemetry proposals; telemetry and DORA stay

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers are at main `221f1f2`.

Rules: test before each behaviour change (see it fail, then change the code). For a pure
deletion the task is "delete the tests with the code, then run the touched test files". Never
relax an assertion that covers kept code. No commits, no pushes, no `gh`. Run tests with
`python -m pytest -q <files>` from the repository root.

## Phase 0: setup

- [ ] T001 (skipped: lead rebases) Rebase onto main after parts 3 to 5 (#800, #801, #808) merge; recheck every line
  in plan.md against the tree; note which "skip if part 3" items remain (plan items 6, 7, 13,
  16) and the tier name part 4 left for `telemetry.ready`.

## Phase 1: `next` has no telemetry row (US1)

- [X] T002 [US1] Test first in `tests/test_next.py` 197-205: replace the telemetry comment and
  the `('telemetry', 'pass')` assertion with `assert 'telemetry' not in {row['state'] for row
  in passed}`. Run `python -m pytest -q tests/test_next.py`; see it fail.
- [X] T003 [US1] `cli/wuwei/commands/next.py` 211-213: delete the row. Update the fixtures
  that skip it: `tests/test_next.py` 55 and the 812 comment, `tests/test_handback.py` 269,
  `tests/test_parallel_dispatch.py` 87. Run those three files; T002 passes.

## Phase 2: the action goes; a stored week still loads (US1, US3)

- [X] T004 [US1, US3] Test first in `tests/test_telemetry.py`: replace
  `test_proposals_command_lists_then_presents_once` with
  `test_a_stored_week_with_proposals_still_loads` (plan item 8): a final week saved with
  `proposals`, `evidence` and `presented` loads; its payload validates without them; preview
  exits 0 with no `proposals` in its output; `main(['telemetry', 'proposals'])` raises
  `SystemExit` with code 2. Run it; see the last assertion fail.
- [X] T005 [US1] `cli/wuwei/commands/telemetry.py`: delete the `proposals` parser, the map
  entry and `_proposals`; docstring and help text (plan item 2). T004 passes.

## Phase 3: final weeks carry no proposals, evidence or presented (US2)

- [X] T006 [US2] Test first in `tests/test_telemetry.py`: 112 becomes
  `assert 'evidence' not in found`; rename and change the week-file test (plan item 8) to
  assert no `proposals`, no carried `presented`, `shared` and `ready` kept. Run it; see both
  fail.
- [X] T007 [US2] `cli/wuwei/telemetry.py`: delete `proposals`, the `evidence` entry, the
  external-wait branch and `zone`; `week_file` drops the proposals lines and `presented` from
  the carry tuple; docstrings (plan item 1). Keep `latest_final`.
- [X] T008 [US2] Delete the rule tests with the rules: `week()`, `REPO`,
  `test_three_proposal_fixtures`, `test_each_rule_at_and_below_its_threshold`; rewrite
  `final_week` without `evidence` and `proposals`; module docstring. Run
  `python -m pytest -q tests/test_telemetry.py tests/test_dora.py tests/test_telemetry_worker.py`.

## Phase 4: the presented event and the registries (US1)

- [X] T009 [US1] Delete `'presented'` from `tests/test_signal_status.py` 879 (and the "six"
  comment), with `'telemetry.presented'` in `cli/wuwei/signal.py` 29 and `'presented'` in
  `cli/wuwei/commands/event.py` 94. Run `python -m pytest -q tests/test_signal_status.py`.
- [X] T010 [US1] Only if part 3 left them: drop `telemetry proposals --widget` from
  `cli/wuwei/guide.py` `WIDGETS`, `telemetry proposals` from `cli/wuwei/commands/__init__.py`
  `WRITES`, the matching text in `docs/site/agent.md` 71, and the guide assertion in
  `tests/test_docs.py` 1410-1412. Run `python -m pytest -q tests/test_docs.py tests/test_guide.py
  tests/test_cli_known_command.py` (those that still exist).

## Phase 5: docs, design spec, constitution

- [X] T011 `docs/site/reference.md` 76 and `docs/site/configuration.md` 220, 224 (plan items
  14, 15). Run `python -m pytest -q tests/test_docs.py`.
- [X] T012 `docs/specs/2026-09-24-wuwei-design.md` 5.13 edits, each marked
  "(owner, 2026-10-11, #789)" (plan item 17).
- [X] T013 `.specify/memory/constitution.md`: delete the proposal sentence, patch version
  bump, Last Amended 2026-10-11 (plan item 18).

## Phase 6: check

- [X] T014 `grep -rn "proposals\|presented" cli/wuwei/telemetry.py cli/wuwei/commands/telemetry.py
  cli/wuwei/commands/next.py cli/wuwei/signal.py cli/wuwei/commands/event.py` finds nothing.
  Run every touched test file once:
  `tests/test_telemetry.py tests/test_dora.py tests/test_telemetry_worker.py tests/test_next.py
  tests/test_handback.py tests/test_parallel_dispatch.py tests/test_signal_status.py
  tests/test_docs.py tests/test_hooks.py`. No full suite; CI is the gate.

## Dependencies

T001 first. T002 before T003, T004 before T005, T006 before T007 and T008. Phases 1 to 4 touch
different files except `tests/test_telemetry.py` (T004, T006, T008: do them in order). Phase 5
any time after T001.
