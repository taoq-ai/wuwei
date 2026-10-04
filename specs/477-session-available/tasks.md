# Tasks: the owner's session is never blocked by work

**Input**: `specs/477-session-available/` (spec.md, plan.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. No absolute local paths, engagement names, emojis or em-dashes
in any file. Every new refusal or reason names a next step (`tests/test_reasons.py`). Live
markers in tests use the pid of a sleeping child process (`subprocess.Popen([sys.executable,
'-c', 'import time; time.sleep(60)'])`, killed in a `finally`); dead markers use a child
that has exited (`Popen(...).wait()`). The current process's pid never counts as running
(plan Design 1).

## Phase 1: US2, fast checks run in the background and are visible (CLI)

- [X] T001 Test, `tests/test_build_next.py` (use the `seat` fixture; launch and stop the
  builder so the build is at `check`): (a) `test_check_in_flight_refuses_next_and_a_second_check`:
  write `builds.A.check = {'started_at': <NOW>, 'pid': <live child pid>}` through
  `state._write_state(..., reserved=False)`; `main(['build', 'next', 'A'])` and
  `main(['build', 'check', 'A'])` each return 2 and stderr names `running since`, the start
  `HH:MM` and `bin/wuwei build next A`; after the child exits, `build next A` prints the
  `check` action (exit 0) and `build check A` runs (exit 0 with a passing result).
  (b) `test_check_in_flight_marker_is_recorded_then_cleared`: monkeypatch
  `wuwei.fast_checks.record` with a wrapper that captures `state.read_state(root)['builds']['A']['check']`
  and calls the original; after `main(['build', 'check', 'A'])` the captured marker has
  `pid == os.getpid()` and `started_at` equal to the fixture's now, a `build.check_started`
  event exists, and the build record has no `check` key, for a pass, a failing check
  (continue) and an environment failure (park).
  Add `'build.check_started'` to the `kinds` of `test_build_evidence_is_producer_only`.
  Run `python -m pytest -q tests/test_build_next.py -k "in_flight or producer_only"` (fails:
  no marker, `build next` returns `check`, `wuwei event build.check_started` is accepted).
- [X] T002 Implement `state.check_running` in `cli/wuwei/state.py` (plan Design 1, first
  function, with its `ponytail:` comment).
- [X] T003 Implement `_busy`, the guard in `next_action`, the marker save in `check` and the
  pop in `complete_checks` in `cli/wuwei/commands/build.py` (plan Design 2); register
  `build.check_started` in `cli/wuwei/signal.py` `SILENT` and
  `cli/wuwei/commands/event.py` `EVENT_PRODUCERS` (plan Design 3). Rerun T001,
  `tests/test_build_next.py`, `tests/test_build.py` and
  `python -m pytest -q tests/test_signal_status.py -k emitted_kinds`; pass.

## Phase 2: US3, the board names what is running

- [X] T004 Test, `tests/test_next.py` `test_running_names_seats_and_checks_with_start_times`
  (issue Acceptance 3): an approved day, CAP 2, items A, B and C in `implement`; running
  builder seats for A (`started_at` `2026-09-30T09:10:00+00:00`) and B (`09:20`); `builds.C`
  at status `check` with a live-child marker started `09:25`. The row is `wait` with command
  `wuwei status --line` and its step contains `Running: builder A 09:10, builder B 09:20,
  checks C 09:25`. With the child exited, the row is `build` for C. Update
  `test_cap_waits_on_running_seat` to assert `builder ITEM-1` instead of the seat name
  `builder-1`. Run `python -m pytest -q tests/test_next.py -k "running or cap_waits"` (fails:
  the row is `build: C ...` and names seats by name only).
- [X] T005 Test, `tests/test_signal_status.py` `test_status_line_names_running_seats_and_checks`:
  the same day through `cli(tmp_path, 'status', '--line')` contains `running builder A 09:10,
  builder B 09:20, checks C 09:25`; `status --json` has `running` equal to
  `[['2026-09-30T09:10:00+00:00', 'builder', 'A'], ...]` (adjust dates to the file's `NOW`);
  a seat without `started_at` shows `start unrecorded`; with nothing running there is no
  `running` part. Run `python -m pytest -q tests/test_signal_status.py -k running` (fails: no
  `running` part or key).
- [X] T006 Implement `state.in_flight` and `state.in_flight_text` in `cli/wuwei/state.py`
  (plan Design 1), the running set and wait rows in `cli/wuwei/commands/next.py` `step`, and
  the `running` key and line part in `cli/wuwei/commands/status.py` (plan Design 4). Rerun
  T004, T005, `tests/test_next.py`, `tests/test_signal_status.py`, `tests/test_board_mcp.py`
  and `tests/test_hooks.py`; pass.

## Phase 3: US1 and US4, background text, the rule, and the text test

- [X] T007 Test, `tests/test_charters.py`: `BLOCKING`, `test_no_blocking_instruction_in_skills_or_charters`,
  `test_blocking_pattern_samples` and `test_never_blocking_rule_is_written_down` (plan
  Design 6). Run `python -m pytest -q tests/test_charters.py -k blocking` (fails: on main the
  pattern matches exactly the plan skill lines 25, 41, 43, 55 and 57 and line 12 of the
  report and retro skills; the rule is nowhere).
- [X] T008 Edit `skills/wuwei-plan/SKILL.md` (the Availability paragraph and lines 25, 35, 41,
  42, 43, 49, 55, 57), `skills/wuwei-report/SKILL.md:12` and `skills/wuwei-retro/SKILL.md:12`
  as plan Design 5 gives them.
- [X] T009 Edit `charters/planner.md` (version 1.2.0, Receive and sweep item 4, the steward
  sentence in item 2) and regenerate `agents/planner.md` with `bin/wuwei agents build`
  (plan Design 5).
- [X] T010 Edit `docs/site/agent.md`, `docs/site/reference.md`,
  `.specify/memory/constitution.md` (bullet, version 1.3.0, Last Amended 2026-10-04) and
  `docs/specs/2026-09-24-wuwei-design.md` 5.2 (plan Design 5). Rerun T007,
  `tests/test_charters.py`, `tests/test_agents.py`, `tests/test_docs.py`,
  `tests/test_skill_evals.py` and `tests/test_next.py`; pass.

## Phase 4: US1 and US2 on the headless fixture day

- [X] T011 Test, `tests/test_headless_e2e.py`: `evidence()` gains a planner `Stop` (exit 0,
  session `planner`) between the builder Agent PreToolUse and its SubagentStop, and after
  that SubagentStop a PreToolUse row (tool `Bash`, `input.command` ending in
  `build check A`), a planner `Stop`, and a `cli` row with `args ['build', 'check', 'A']`
  exit 0; `test_missing_contract_evidence_fails_despite_success_prose` gains `no-builder-yield`
  and `no-check-yield`, each dropping one of those Stops. Run `python -m pytest -q
  tests/test_headless_e2e.py -k "missing_contract or complete_structured"` (fails: the two
  new mutations produce no finding).
- [X] T012 Implement `yielded` and the two findings in `scripts/headless_e2e.py` `validate`,
  the slow fixture check in `prepare` and the step 3 prompt text (plan Design 7). Rerun T011
  and `tests/test_headless_e2e.py`; pass.

## Phase 5: Polish

- [X] T013 Run `python -m pytest -q`; everything passes. Grep the changed files for
  em-dashes, emojis and absolute local paths and remove any.
