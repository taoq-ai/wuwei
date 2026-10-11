# Tasks: delete discovery intake, the spec guard and rank; the spec check stays in dispatch

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at d60253b8.
Parts 17 to 20 are on the branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: The spec check stays in dispatch (US1, P1)

- [X] T001 [US1] Add to `tests/test_dispatch.py`: standard item refused naming the step with no
  `gates`; light item gets the gates without a spec. Run: they pass at the base (a regression
  net); confirm by breaking `specmode.check`'s call in a scratch copy that they fail.

## Phase 2: The PreToolUse spec guard goes (US2, P1)

- [X] T002 [US2] Delete `check_edit`, its `GUARDS` row, `MODULES['spec']['PreToolUse']`,
  `specmode.own`/`OWN`; delete the guard tests (`tests/test_spec_mode.py`,
  `tests/test_guard_mutation.py`); update `tests/test_hooks.py`, `tests/test_e2e_day.py`.
  Run `tests/test_spec_mode.py tests/test_hooks.py tests/test_guard_mutation.py
  tests/test_enforce.py tests/test_e2e_day.py tests/test_build.py tests/test_dispatch.py`: green.

## Phase 3: Intraday intake goes (US3, P1)

- [X] T003 [US3] Move the owner and finding `plan add` cases and `candidate` from
  `tests/test_intraday_intake.py` to `tests/test_plan.py`; update the two importers. Run them:
  green.
- [X] T004 [US3] Delete the intake code (plan.md) and its tests (`test_intraday_intake.py`,
  `test_goals_rank.py` intake cases, `test_dispatch.py`, `test_agent_launch.py`,
  `test_watch.py`, `test_quiet_sweeps.py`, `test_heartbeat.py`, `test_plan.py`, `test_why.py`,
  `test_signal_status.py`). Run those files plus `tests/test_linear_loop.py
  tests/test_operator_records.py tests/test_records_after_dryrun4.py tests/test_state_allowlist.py
  tests/test_shepherd.py`: green.

## Phase 4: `rank` goes; `plan propose` ranks (US4, P1)

- [X] T005 [US4] Red: `tests/test_templates_errors.py` asks `plan template` for RICE components
  with `candidate_template` imported from `wuwei.commands.plan`. Run: red.
- [X] T006 [US4] Move `candidate_template`, delete `commands/rank.py`, its tests, the
  `fakes/day.py` call; re-text the off-path examples. Run `tests/test_templates_errors.py
  tests/test_goals_rank.py tests/test_e2e_day.py tests/test_metrics.py tests/test_headless_e2e.py
  tests/test_plan.py tests/test_cli.py`: green.

## Phase 5: Config and governance (US5, P2)

- [X] T007 [US5] Red: `tests/test_config_transition.py` removes `[discovery]`. Then
  `workspace.py`, template; `tests/test_workspace.py`. Run those plus `tests/test_docs.py`:
  green.
- [X] T008 Charters (lead, builder), `bin/wuwei agents build`, design spec, docs site, hero
  regeneration. Run `tests/test_charters.py tests/test_agents.py tests/test_docs.py
  tests/test_tone.py`: green.
- [X] T009 SC-001 grep; rerun every touched test file.
