# Tasks: delete the setup interview, profiles and calibration cards; the host measure moves into dispatch

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 9639dd8.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: CAP and seats derive exactly as before (US1, P1)

- [X] T001 [US1] Move the host tests from `tests/test_calibrate.py` to `tests/test_dispatch.py`
  (plan.md list), calling `dispatch.host` and `dispatch.processes`. In
  `test_host_falls_back_when_a_past_day_log_is_damaged`, or a new case with `os.cpu_count`
  returning None, expect the unmeasured text `run bin/wuwei doctor, then retry`. Run
  `tests/test_dispatch.py`: red (no `dispatch.host`).
- [X] T002 [US1] Move `SEAT_MIB`, `_gb`, `processes` and `host` into `cli/wuwei/dispatch.py`
  and point every caller at it (`dispatch.py`, `plan.py`, `commands/plan.py`,
  `guards/agent_launch.py`). Delete them from `calibrate.py`. Run `tests/test_dispatch.py
  tests/test_agent_launch.py tests/test_parallel_dispatch.py tests/test_plan.py
  tests/test_hooks.py`: green.

## Phase 2: A workspace is configured in the session (US2, P1)

- [X] T003 [US2] `tests/test_next.py`: rewrite `test_setup_rows` (no repos gives `setup` with
  the `config add-repo` command and `THEN['setup']`; repos without calibration.json reach the
  `session` row) and `test_setup_row_outside_workspace` (`bin/wuwei init --shadow`, run
  action, no `host terminal` in `why` or `then`). Drop the `calibrate` step from the day test
  and `seen(root, 'calibrate')` from `approved`; delete
  `test_unanswered_setup_questions_are_asked_on_any_day`. Run: red.
- [X] T004 [US2] `cli/wuwei/commands/next.py`: `THEN['setup']`, the two rows, no calibration
  gate, no `calibrate` row or `THEN['calibrate']`. Run `tests/test_next.py
  tests/test_parallel_dispatch.py tests/test_path_day.py` after T012's fixture edits: green.

## Phase 3: The config edit frame moves; setup and calibrate go (US3, US4)

- [X] T005 [US3] Move the kept functions from `commands/setup.py` into `commands/config.py`
  (plan.md list) and repoint every importer (`init.py`, `telemetry.py`, `drafts.py`,
  `outbound.py`, `decision.py`, the tests in plan.md). `git mv tests/test_setup.py
  tests/test_config_set.py` and keep only the config set, add-repo, list and show cases. Run
  `tests/test_config_set.py tests/test_config_writer.py tests/test_card_confirms.py
  tests/test_telemetry.py tests/test_drafts.py tests/test_outbound_learn.py
  tests/test_decision.py`: green.
- [X] T006 [US4] Delete `commands/setup.py`, `commands/calibrate.py`, `interview.py`,
  `profiles.py`, `templates/profiles/` and `tests/test_interview.py`, with their tests in
  `tests/test_calibrate.py`, `tests/test_card_confirms.py`, `tests/test_profiles.py`,
  `tests/test_protect_state.py` and `tests/test_workspace.py` (plan.md). Apply the small
  repoints: `tracker.ABSOLUTE`, `note.py`, `decision.ROLES`, `brief.mandate`, `retro.py`,
  `event.py`, `protect_state.py`, `init.py`, `specmode.detect`, `docs.detect`. Run
  `tests/test_cli.py tests/test_calibrate.py tests/test_card_confirms.py tests/test_profiles.py
  tests/test_protect_state.py tests/test_workspace.py tests/test_tracker.py tests/test_brief.py
  tests/test_report_retro.py tests/test_spec_mode.py tests/test_docs_system.py`: green.
- [X] T007 [US3] `tests/test_calibrate.py`: the `config promote` cases without `--keys`, and
  `test_survey_reads_the_pr_baseline`. Run: red. Then trim `calibrate.py` (plan.md) and
  `config.proposal` and `promote`. Run `tests/test_calibrate.py tests/test_steward.py`: green.
- [X] T008 [US4] `tests/test_cli.py` (or `tests/test_config_set.py`): `main(['setup'])` and
  `main(['calibrate'])` raise SystemExit 2. Run: green after T006.

## Phase 4: Doctor, build and the remaining texts (US3, US4)

- [X] T009 [US3, US4] `tests/test_doctor.py` edits from plan.md (rows, FIXES, telemetry,
  shepherd.authors, init --shadow). Run: red. Then edit `commands/doctor.py`. Run
  `tests/test_doctor.py`: green.
- [X] T010 [US4] `tests/test_build_next.py`: `test_strict_builds_without_fast_checks`. Run:
  red. Delete the strict refusal in `commands/build.py:_repo`. Run `tests/test_build_next.py
  tests/test_build.py`: green.
- [X] T011 [US4] `tests/test_reasons.py`: delete the part 12 LEFT rows and swap
  `commands/setup.py` for `commands/config.py` in `PERSON_MODULES`. Run
  `tests/test_reasons.py`: fix any flagged text in `commands/config.py` by naming the step to
  the person ("you"); never add a LEFT or KEEP row. Green.
- [X] T012 [US4] `tests/test_tone.py`, `tests/test_outward.py`, `tests/test_hooks.py`,
  `tests/test_path_day.py`, `tests/test_parallel_dispatch.py`, `tests/test_brief.py` edits from
  plan.md. Run them: green. Re-measure the `cards` budget; do not raise it.

## Phase 5: Governance and docs (FR-009)

- [X] T013 Edit `templates/workspace/config.toml`, the three skills, the design spec, the docs
  pages and README as plan.md lists. Run `tests/test_docs.py tests/test_tone.py
  tests/test_skill_evals.py tests/test_charters.py tests/test_templates_errors.py`: green.
- [X] T014 Run the SC-002 grep; every hit is the sensitive keyword or is fixed.
- [X] T015 Final: run every test file touched above once more. PR body for this part: "Closes
  #832", the process control table from plan.md, and the Risks.
