# Tasks: delete the MCP registry gate; scanner findings stay for the security gate

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at d60253b8.
Parts 16 (#838) and 17 (#839) are on the base first; confirm with
`grep -rn "_host_confirm\|owner_confirm\|gate_topics\|check_mcp" cli` before Phase 3.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: The scanner findings stay (US3, P1)

- [X] T001 [US3] Run the kept scanner tests before any edit and record them green: the ZIRAN
  adapter tests for `audit`, `gate` and `traces`, `tests/test_dispatch.py` scanner receive
  cases, `tests/test_watch.py` trace sweep cases. They are the regression net for FR-004.

## Phase 2: Launches, the morning plan and `next` (US1, US2, P1)

- [X] T002 [US2] Red: `tests/test_next.py::test_morning_path` expects `lead` right after
  `pr-flow`; `test_a_once_row_is_done...` uses `pr-flow`. Run: red.
- [X] T003 [US1, US2] Delete `cli/wuwei/mcp.py`, `cli/wuwei/commands/mcp.py`,
  `tests/test_mcp.py`. Edit `adapters/scanner/ziran.py`, `adapters/scanner/none.py`,
  `adapters/runtime/claude.py`, `adapters/runtime/codex.py`, `registry.py`,
  `guards/agent_launch.py`, `brief.py`, `plan.py`, `commands/next.py`, `commands/status.py`,
  `commands/init.py`, `commands/event.py`, `signal.py`, `state.py`, `commands/config.py`,
  `guards/protect_state.py`, `commands/doctor.py` (gates rows, fixes) per plan.md. Delete the
  tests plan.md names in `test_agent_launch.py`, `test_brief.py`, `test_doctor.py`,
  `test_quiet_sweeps.py`, `test_guard_mutation.py`, `test_adapters.py`, `conftest.py`; update
  `test_next.py`, `test_path_day.py`, `test_metrics.py`, `test_protect_state.py`,
  `test_signal_status.py`, `test_env_credentials.py`. Run those files plus
  `tests/test_hooks.py tests/test_state_allowlist.py tests/test_cli.py tests/test_plan.py
  tests/test_runtime.py`: green.

## Phase 3: No host-terminal prompt and no D-n record (US4, P1)

- [X] T004 [US4] Red: `tests/test_reasons.py` asserts no source holds `_host_confirm` or
  `/dev/tty` and the part 18 LEFT rows are gone; `tests/test_answers.py` asserts a `D-1`
  header records nothing. Run: red.
- [X] T005 [US4] Delete `integrity.HOST_TERMINAL` and `_host_confirm`, the decision.py record
  library, the D-n branch of `record_gate`, `sessions.caller` and `sessions.gate_topics`,
  doctor `_unrecorded`, `_owner_on_file` and the `answered cards` row. Delete their tests
  (`test_integrity.py`, `test_sessions.py`, `test_answers.py`, `test_decision.py`,
  `test_doctor.py`). Run `tests/test_reasons.py tests/test_answers.py tests/test_integrity.py
  tests/test_sessions.py tests/test_decision.py tests/test_doctor.py tests/test_card_confirms.py
  tests/test_plan.py tests/test_close_parked.py`: green.

## Phase 4: Config (US5, P2)

- [X] T006 [US5] Red: `tests/test_config_transition.py` removes the four retired keys and
  keeps `plugins_file`; `WARNING` and the nearest-key test use a new typo. Run: red.
- [X] T007 [US5] `workspace.py` SCHEMA and `RETIRED`, `integrity.registered` and doctor
  `_hooks` default, `templates/workspace/config.toml`. Update `tests/test_workspace.py`. Run
  `tests/test_config_transition.py tests/test_workspace.py tests/test_spec_mode.py
  tests/test_integrity.py tests/test_canary.py tests/test_docs.py`: green.

## Phase 5: Governance and docs

- [X] T008 Edit the design spec, docs site, README, `skills/wuwei-retro/SKILL.md` and
  `scripts/headless_e2e.py` per plan.md. Run `tests/test_docs.py tests/test_charters.py
  tests/test_tone.py tests/test_skills.py` (if present): green.
- [X] T009 SC-001 grep over `cli/ adapters/ charters/ skills/ agents/ hooks/ templates/
  scripts/ docs/site/` returns nothing; run every test file touched above once more.
