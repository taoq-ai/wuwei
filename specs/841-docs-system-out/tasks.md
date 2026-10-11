# Tasks: delete the docs system

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at d60253b8.
Parts 16 (#838) and 18 (#840) are on the branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: Move the shared helper

- [X] T001 Move `_sections` from `docs.py` into `specmode.py`; `governed` uses it. Run
  `tests/test_spec_mode.py`: green.

## Phase 2: The quality gate never blocks on docs (US1, P1)

- [X] T002 [US1] Red: `tests/test_dispatch.py::test_quality_pass_needs_no_docs_value`,
  `tests/test_verdict.py` (a "docs value missing" finding lints clean), `tests/test_next.py`
  (an item at the gate gets `verdicts`). Run: red.
- [X] T003 [US1] `dispatch.py` (receive refusal, `docs.exempt`), `verdict.py` (`DOCS_MISSING`,
  `recorded_docs`, `docs=`), `commands/next.py`. Delete the docs cases in `test_dispatch.py`,
  `test_verdict.py`. Run `tests/test_dispatch.py tests/test_verdict.py tests/test_next.py
  tests/test_hooks.py`: green.

## Phase 3: Delete the docs system (US2, P1)

- [X] T004 [US2] Delete `docs.py`, `commands/docs.py`, `adapters/docs/`,
  `tests/test_docs_system.py`, `tests/test_docs_port.py`, the fixture. Edit `registry.py`,
  `brief.py`, `closing.py`, `report.py`, `commands/report.py`, `commands/retro.py`,
  `commands/plan.py`, `commands/why.py`, `commands/doctor.py`, `commands/config.py`,
  `commands/event.py`, `state.py`, `signal.py`, `plan.py`. Update the tests plan.md names. Run
  `tests/test_adapters.py tests/test_brief.py tests/test_doctor.py tests/test_why.py
  tests/test_state.py tests/test_signal_status.py tests/test_plan.py tests/test_report_retro.py
  tests/test_env_credentials.py tests/test_cli.py tests/test_outward.py tests/test_stop.py`:
  green.

## Phase 4: Config (US3, P2)

- [X] T005 [US3] Red: `tests/test_config_transition.py` removes `[docs]` and `adapters.docs`.
  Then `workspace.py` (SCHEMA, mirror, validation, `RETIRED`, cache version), the template.
  Update `tests/test_workspace.py`, `tests/test_config_set.py`. Run those plus
  `tests/test_config_transition.py tests/test_docs.py`: green.

## Phase 5: Governance and docs

- [X] T006 Charters (quality step 7, builder line 35, versions), `bin/wuwei agents build`,
  design spec, docs site, README. Run `tests/test_charters.py tests/test_agents.py
  tests/test_docs.py tests/test_tone.py`: green.
- [X] T007 SC-001 grep returns nothing; rerun every touched test file.
