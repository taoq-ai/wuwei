# Tasks: fix rounds from a fresh Agent launch, analysis.md through the CLI

Test first: each test task runs and fails for the expected reason before its implementation
task. Hooks are driven with recorded-style payloads (`agent_launch.check`, `agent_launch.stop`,
the scripted day's `hook`); no test runs a real Agent. Run only the touched test files, then
the full suite.

## Phase 1: builder fresh continue (FR-001, FR-003, FR-004, US1.1 to US1.3, US1.5, US1.6)

- [X] T001 Test in `tests/test_build_next.py`: after a failed check, a launch of the same
  prompt without `resume` exits 0 and the build and seat are `running`; a stop from the
  replaced id records nothing; a stop with a new id records `check` and that id; passing
  checks reach `done`; a fresh launch then is refused with `brief already used`. Move the
  "consumed brief" assertion of `test_claude_launch_check_continue_done_idempotent` after
  `done`.
- [X] T002 Implement the builder branch of `reserve` in `cli/wuwei/guards/agent_launch.py`,
  `started(..., fresh)` and the `replaced` check in `stopped` in `cli/wuwei/commands/build.py`.

## Phase 2: sentinel fresh delta continue (FR-001, FR-002, US1.4)

- [X] T003 Test in `tests/test_e2e_day.py` with `tests/fakes/day.py`: the scripted day with
  fresh launches (no `resume`, new agent ids and transcripts) after the initial gates
  completes the fix round, receives the delta verdict and returns `raise`, with no
  `seat stop unmatched` event.
- [X] T004 Implement `dispatch.delta_due`, use it in `_seats` and in the sentinel branch of
  `reserve`.

## Phase 3: planner text (FR-005)

- [X] T005 Test in `tests/test_next.py`: a build `continue` row's `then` is
  `THEN['continue']`, which names a fresh Agent and `resume`.
- [X] T006 Implement `THEN['continue']` and the `set` clause in `cli/wuwei/commands/next.py`;
  update `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`,
  `docs/site/reference.md`, `docs/site/daily.md`, `docs/site/concepts.md`.

## Phase 4: spec analysis command (FR-006, FR-007, US2)

- [X] T007 Test in `tests/test_spec_mode.py`: `spec analysis A` writes stdin and `--file`
  reports to `specs/001-a/analysis.md` (exit 0, relative path printed) and the analyze step
  is done; exit 2 and no file for no spec directory, two directories, no `spec.md`, a
  symlinked `analysis.md`, an empty report; a builder seat's Bash call (redirect and heredoc)
  passes the PreToolUse hook with no `hook.refusal`; the brief spec line names the command.
- [X] T008 Implement `cli/wuwei/commands/spec.py`, `WRITES`, `GROUPS`, the specmode step text,
  the reference row, configuration.md, `charters/builder.md` and the generated agent.

## Phase 5: verify

- [X] T009 Full suite `python -m pytest -q`; adversarial review (correctness, security,
  ponytail).
