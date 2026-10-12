# Tasks: about 20 commands, init --upgrade removes every obsolete file, docs rewritten

**Input**: [spec.md](spec.md), [plan.md](plan.md). Built after part 23 on the same branch.

Run tests with `python -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: The folds (US1, P1)

- [X] T001 [US1] Red: `tests/test_brief.py` and `tests/test_dispatch.py` run briefs through
  `seat brief`; `tests/test_note_fix.py` through `seat note --fix`; `tests/test_spec_mode.py`
  through `build analysis`; `tests/test_process_depth.py` through `build classes`;
  `tests/test_promotion.py` through `retro --promote` (and asserts `memory/index.md` written);
  `tests/test_metrics.py` through `report --week`. Run: red.
- [X] T002 [US1] Move the parsers and `run` functions into `commands/seat.py`,
  `commands/build.py`, `commands/retro.py`, `commands/report.py`; add `memory.write_index` to
  the promotion landing; delete `commands/{brief,note,spec,sweep,promote,metrics}.py`. Run the
  T001 files: green.

## Phase 2: The duplicates go (US1, P1)

- [X] T003 [US1] Red: `tests/test_cli.py::test_help` expects the 20 names of spec US1, `hook`
  and `status --line` runnable but unlisted, the 14 deleted names refused;
  `tests/test_brief.py` expects the lead brief to list discovered candidates with their source
  and an unmeasured source; `tests/test_doctor.py` reconfirms integrity through
  `--fix --apply integrity-reconfirm`. Run: red.
- [X] T004 [US1] Delete `commands/{integrity,verdict,steward,discover,goals,index,memory,
  payload}.py` and the CLI-only cases plan.md names; register `hook` and `status` without
  help; trim `status` to `--line`; delete `pr ping-check`, `pr reviewers`, `tracker done`;
  add the lead brief's candidates. Run `tests/test_cli.py tests/test_brief.py
  tests/test_doctor.py tests/test_integrity.py tests/test_verdict.py tests/test_steward.py
  tests/test_linear_loop.py tests/test_memory.py tests/test_goals_rank.py
  tests/test_signal_status.py tests/test_pr_actions.py tests/test_tracker.py`: green.
- [X] T005 [US1] Replace every printed command name per plan.md; run the SC-003 grep over
  `cli/ adapters/ charters/ skills/ templates/ scripts/`: empty. Run `tests/test_reasons.py
  tests/test_tone.py tests/test_next.py tests/test_plan.py tests/test_e2e_day.py
  tests/test_path_day.py tests/test_agent_launch.py`: green.

## Phase 3: The upgrade and retired keys (US2, P1)

- [X] T006 [US2] Red: `tests/test_config_transition.py` 0.27.0 fixture (plan.md): after
  `init --upgrade` no retired key or file is left except the symlink and the day file, one line
  per removal; `--dry-run` writes nothing. Run: red.
- [X] T007 [US2] Edit `commands/init.py` (`RETIRED_FILES`, one removal loop, index write),
  `workspace.py` (`SURFACES`, SCHEMA, `RETIRED`, cache version), `registry.py`, `telemetry.py`,
  `guards/protect_state.py` (`ziran` tail), the template; delete `adapters/redactor/` and its
  tests. Run `tests/test_config_transition.py tests/test_workspace.py tests/test_config_writer.py
  tests/test_adapters.py tests/test_outward.py tests/test_telemetry.py tests/test_protect_state.py
  tests/test_templates_errors.py`: green.

## Phase 4: Goals block (US3, P2)

- [X] T008 [US3] Red: `tests/test_plan.py` replacement blocks with defined goals reach the gate
  card and, on approve, `memory/goals.md` committed; ids only unchanged. Run: red.
- [X] T009 [US3] Edit `goals.py`, `plan.py`, `guards/protect_state.py` hint, `charters/lead.md`,
  `charters/planner.md`. Run `tests/test_plan.py tests/test_goals_rank.py
  tests/test_protect_state.py`: green.

## Phase 5: Charters, agents, docs (US4, US5, P2)

- [X] T010 [US4] Add the defect-class step to the three sentinel charters (plan.md wording),
  bump versions, run `bin/wuwei agents build`. Run `tests/test_charters.py tests/test_agents.py
  tests/test_tone.py`: green.
- [ ] T011 [US5] Rewrite `docs/site/*.md` and `README.md`, the hero text and SVGs,
  `docs/headless-e2e.md`, `scripts/headless_e2e.py`, the design spec's command names. Run the
  SC-003 grep over `docs/site/ README.md`: empty. Run `tests/test_docs.py tests/test_headless_e2e.py`:
  green.

## Phase 6: Polish

- [ ] T012 `bin/wuwei --help`: 20 commands. Run `tests/test_cli.py tests/test_docs.py
  tests/test_e2e_day.py tests/test_path_day.py tests/test_loop.py`: green.

## Dependencies

Part 23 first. T001 to T002 before T003 (the help list counts the folds). T005 after T004.
Phases 3 and 4 are independent of 1 and 2. Phase 5 last (docs describe the final set).
