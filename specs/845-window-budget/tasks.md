# Tasks: seats and pauses follow each runtime's usage window (#845)

**Input**: `spec.md`, `plan.md`, `research.md` in `specs/845-window-budget/`.

Every behaviour has a test task (red, run it, see it fail for the named reason) before its
implementation task. Run the touched test files with explicit paths and the interpreter the
task names; CI runs the suite. `[P]` marks a task that touches no file another open task
touches.

## Phase 1: Config (US4, FR-001, FR-012)

- [X] T001 Test: `tests/test_workspace.py`: update the defaults dict (`'budget': {'claude':
  {'five_hour': 0, 'seven_day': 0}, 'codex': {'five_hour': 0, 'seven_day': 0}}`), the
  invalid-value row (`[budget.claude]\nfive_hour = -1` names `budget.claude.five_hour`) and
  the CAP defaults assertion; add that `[budget]\ntokens_per_day = 1` loads with the retired
  key reported, not a typo hint. Red.
- [X] T002 Test: `tests/test_config_transition.py`: `init --upgrade` on a config with
  `[budget]\ntokens_per_day = 200000` removes the key and prints it among the removed keys.
  Red.
- [X] T003 Implement: `cli/wuwei/workspace.py` SCHEMA `budget` per runtime and window;
  `RETIRED` gains `budget.tokens_per_day`. `templates/workspace/config.toml`: commented
  `[budget.claude]` and `[budget.codex]` blocks replace the `tokens_per_day` lines. T001, T002
  green.

## Phase 2: seat.usage names its runtime (FR-002)

- [X] T004 [P] Test: `tests/test_build_next.py`: a recorded builder result appends a
  `seat.usage` row whose payload has `runtime` equal to the build record's runtime.
  `tests/test_dispatch.py`: a second opinion's `seat.usage` row has `runtime` equal to
  `gates.second_opinion.runtime`. Red.
- [X] T005 Implement: `cli/wuwei/commands/build.py` `record_result` and
  `cli/wuwei/dispatch.py` `opinion` add `runtime` to the payload. T004 green.
- [X] T006 [P] Test: `tests/test_metrics.py`: `metrics.seat_tokens(events, 'codex', 'claude')` keeps only
  Codex rows, a row without runtime counting as `claude`; no `runtime` keeps every row. Red.
- [X] T007 Implement: `cli/wuwei/metrics.py` `seat_tokens(events, runtime=None,
  default=None)`. T006 green.

## Phase 3: readings (US3, FR-010, FR-011)

- [X] T008 Test: `tests/test_dispatch.py`: `dispatch.save_windows` writes
  `.wuwei/windows.json` with valid entries, drops an unknown window, a negative or
  non-number percent and an unparsable reset, merges with the runtime's saved windows, and
  does not rewrite the file when nothing changed (mtime unchanged). Red.
- [X] T009 Implement: `cli/wuwei/dispatch.py` `WINDOWS` and `save_windows`. T008 green.
- [X] T010 [P] Test: `tests/test_signal_status.py`: with `sys.stdin` a `StringIO` holding a
  status line payload with `rate_limits.five_hour` and `seven_day` (epoch resets),
  `wuwei status --line` saves both under `claude` as ISO times and prints the same line as
  with empty stdin; with no `rate_limits`, malformed JSON or a stdin whose `read` raises
  `OSError`, it prints the same line, exits 0 and writes no file. Red.
- [X] T011 Implement: `cli/wuwei/commands/status.py` `run` reads stdin and calls
  `dispatch.save_windows(root, 'claude', ...)`. T010 green.
- [X] T012 [P] Test: `tests/test_runtime.py`: with `CODEX_HOME` set to a temp directory
  holding `sessions/2026/10/12/rollout-x-<thread>.jsonl` whose last `token_count` event has
  `primary` (300 minutes) and `secondary` (10080 minutes), the codex `result` returns
  `windows` with `five_hour` and `seven_day` (ISO resets); a window of 60 minutes is dropped;
  no rollout file, a malformed line or a thread id with `/` or `*` gives no `windows` and the
  result still succeeds. Extend `tests/fixtures/runtime/codex-companion.json` `storedJob.result`
  with a `threadId`. Red.
- [X] T013 Implement: `adapters/runtime/codex.py` `_windows(thread)` and its use in `result`.
  T012 green.
- [X] T014 Test: `tests/test_build_next.py`: `record_result` with a result carrying `windows`
  saves them under the record's runtime; `tests/test_dispatch.py`: `opinion` with a runtime
  result carrying `windows` saves them under the second opinion's runtime. Red.
- [X] T015 Implement: `cli/wuwei/commands/build.py` `record_result` and
  `cli/wuwei/dispatch.py` `opinion` call `save_windows`. T014 green.

## Phase 4: room and CAP per runtime (US1, US2, FR-003 to FR-005)

- [X] T016 Test: `tests/test_dispatch.py`, one parametrised table for `dispatch.windows`
  (fixed `WUWEI_NOW`, `usage_day` rows with `runtime`): budget 300000, 250000 counted, 100000
  per seat gives room 0 and `until` the earliest counted row plus 5 hours; 100000 counted
  gives room 2; a reading of 80 percent with 10000 counted gives used 240000 and room 0 with
  the reading's reset as `until`; an expired reading is ignored; a reading of 100 percent and
  no budget gives room 0; no budget and no full reading gives None; per-seat unmeasured gives
  None with "per-seat tokens unmeasured" in `text`; a damaged day log gives None with the
  warning; a damaged `windows.json` is ignored with a warning; Codex rows do not count toward
  Claude; a row without runtime counts toward `adapters.runtime`; the 7-day window counts rows
  from a day six days back and the 5-hour window does not; the smaller window room wins. Red.
- [X] T017 Implement: `cli/wuwei/dispatch.py` `windows`. T016 green.
- [X] T018 Test: `tests/test_dispatch.py`: rewrite `test_token_budget_bounds_cap` to windows:
  `host(..., runtimes=True)` returns `runtimes` with `claude` and `codex` rows whose `cap` is
  `min(cap, room)`, `host` without it returns no `runtimes` and reads no past day log,
  the day `cap` and `bound` keep the memory or `host.seats` rule, and `text` names each
  bounded window; `test_host_falls_back_when_a_past_day_log_is_damaged` asserts the window
  warning instead of the day budget text. Red.
- [X] T019 Implement: `cli/wuwei/dispatch.py` `host`: delete the `tokens_per_day` block, add
  `runtimes`. T018 green.

## Phase 5: routing (US2, FR-008, FR-009)

- [X] T020 [P] Test: `tests/test_dispatch.py`: `dispatch.route` table: primary with room or
  unbounded wins; primary at 0 and alternate with room gives the alternate; both at 0 gives
  the primary; no alternate gives the primary; no row gives the default. Red.
- [X] T021 Implement: `cli/wuwei/dispatch.py` `route`. T020 green.
- [X] T022 [P] Test: `tests/test_plan.py`: a proposal whose seat policy row has `alternate`
  equal to its `runtime`, an unknown runtime or a non-string is refused with the
  `seat_policy` message; `alternate: "codex"` on a `claude` row is accepted. Red.
- [X] T023 Implement: `cli/wuwei/plan.py` validation. T022 green.
- [X] T024 Test: `tests/test_build_next.py`: `build.next_action(item, root=root,
  runtime='codex')` on a new build binds `record['runtime'] == 'codex'`; with no `runtime`,
  a spent policy runtime and an alternate with room, it binds the alternate; an existing
  record keeps its runtime; `open_fix` on a Codex record returns a Codex action;
  `run_loop` on a Codex record runs under a Claude builder policy and refuses a Claude record
  under a Codex policy. Red.
- [X] T025 Implement: `cli/wuwei/brief.py` `seat_action(..., runtime=None)`;
  `cli/wuwei/commands/build.py` `next_action(..., runtime=None)` and `run_loop`. T024 green.
- [X] T026 [P] Test: `tests/test_agent_launch.py`: an Agent launch of a builder brief whose
  build record binds `claude` passes under a Codex builder policy, and one whose record binds
  `codex` is refused under a Claude policy, with the existing refusal text. Red.
- [X] T027 Implement: `cli/wuwei/guards/agent_launch.py` builder runtime from the build
  record. T026 green.

## Phase 6: holding launches and the timed wait (US1, US2, FR-006, FR-007, FR-013)

- [X] T028 Test: `tests/test_parallel_dispatch.py`: rewrite
  `test_token_budget_fitting_two_seats_starts_two` to a Claude window that fits two seats
  (entries `A start`, `B start`, `C wait`, `D wait`, the waits with `until`). Add the
  acceptance test with two runtimes: Claude room 0, Codex room 2, builder policy
  `{"runtime": "claude", "model": "opus", "alternate": "codex"}`, two briefed planned items:
  both entries are `run` with `wuwei build <item> <brief> <worktree>` and runtime `codex`, and
  both build records bind `codex`; parametrised with no alternate (both wait with Claude's
  `until`) and with Codex room 1 and CAP 3 over three items (one Codex run, two waits). Add:
  an unbriefed planned item's `start` entry takes one seat of its routed runtime's room;
  a gate launch on a spent Claude window waits with `until` while a `merge` launch in the
  same set still runs; a running builder seat is untouched (its seat and build record are
  unchanged after the launch set). Red.
- [X] T029 Implement: `cli/wuwei/dispatch.py` `launch_set` (`host(..., runtimes=True)`, `left`,
  per-runtime counting in `add`, routed builder starts) and `resolve_offer` (non-Claude builder launch becomes a
  `run` of `wuwei build`). T028 green.
- [X] T030 Test: `tests/test_next.py`: a workspace whose only launch is a planned item on a
  spent Claude window: `next --json` returns state `wait`, action `background`, `until` the
  reset, command `sleep <n>` with `n` at least the seconds to the reset, and the
  `background` then line; with `WUWEI_NOW` past the reset, `next --json` returns the set with
  the launch; with a due duty or an owner decision in the same day, `next --json` returns the
  set with the duty or the decision and the held launch carrying `until`. Red.
- [X] T031 Implement: `cli/wuwei/commands/next.py` `resolve` timed wait. T030 green.

## Phase 7: docs and governance

- [X] T032 [P] `docs/site/configuration.md`: replace the `budget.tokens_per_day` row with the
  four window rows and a line on readings (status line, Codex rollout) and the timed wait;
  update the `cap` row.
- [X] T033 [P] `charters/lead.md`: the CAP line names window budgets per runtime instead of
  `budget.tokens_per_day`; the seat policy may name a builder `alternate`.
- [X] T034 [P] `docs/specs/2026-09-24-wuwei-design.md` 5.3: an "Amended (owner, 2026-10-11,
  #845)" line under the CAP bullet: window budgets per runtime, readings, per-runtime CAP,
  the builder alternate, the timed wait.

## Phase 7b: review fix round (F1 to F11)

- [X] T036 F1: `next` returns the timed wait when every launch waits and one carries `until`
  (`tests/test_next.py`).
- [X] T037 F2: `run_loop` claims the record (`loop`) with its pid and a second loop exits 0;
  `state.in_flight` counts a live loop (offer-time marker dropped in T048)
  (`tests/test_parallel_dispatch.py`, `tests/test_build_next.py`).
- [X] T038 F3: the second opinion's independence check reads the build record's runtime;
  `plan propose` refuses a builder `alternate` equal to the second opinion's runtime.
- [X] T039 F4: a new build is held by its routed runtime's window before `build next` runs.
- [X] T040 F5: `alternate` is `claude` or `codex` (a runtime with window budgets).
- [X] T041 F6: a test pins room 0 at a full reading with per-seat tokens unmeasured (already
  held; a counted overrun implies measured seats, so room was already 0).
- [X] T042 F7: the per-seat history scan runs only for a budgeted window.
- [X] T043 F8: `status --line` reads stdin only when `select` says it is readable within 0.2 s.
- [X] T044 F9: a malformed rollout line is skipped, not fatal.
- [X] T045 F10: `host(..., runtimes=)` and the per-runtime `cap` removed.
- [X] T046 F11: `init --upgrade` names `budget.<runtime>.five_hour and seven_day` when it
  removes `budget.tokens_per_day`.

- [X] T047 D1: the launch set subtracts each runtime's running seats and live build loops from
  its room (`tests/test_parallel_dispatch.py::test_running_seats_take_their_runtime_room`).
- [X] T048 D2: a claimed loop counts as running for two minutes after it started, so a loop
  that fails at once backs off; the offer-time marker is dropped (the pid claim alone stops a
  second job).
- [X] T050 E1: a dead loop is not in flight; a loop that ended within two minutes of its
  start is a `wait` with `until` (start plus 121 s), so `next` returns the background sleep
  (`test_a_loop_that_died_at_once_is_a_timed_wait`).
- [X] T051 E2: a builder seat counts against its build record's runtime
  (`test_a_routed_builder_seat_takes_its_build_runtime_room`).
- [X] T049 Docs: a window budget holds early only with measured seat tokens.

## Phase 8: verify

- [ ] T035 Run the touched test files, then the full suite with the task's interpreter
  (`python -m pytest -q`); grep `cli/ adapters/ templates/ charters/ docs/site/` for
  `tokens_per_day` (only the retired list and the design history may name it); check the
  diff for absolute local paths, emojis and em-dashes; count runtime lines added (SC-004).

## Dependencies

T003 before every later phase (config keys). T009 before T011, T013, T015 and T017. T007
and T017 before T019. T021 and T017 before T025 and T029. T025 before T029. T029 before T031.
Phase 7 any time after Phase 6.
