# Tasks: A second-opinion gate on a different model

Test first: run each test task, see it fail for the stated reason, then do the implementation
task that follows it. Run tests with `python -m pytest -q <file>` from the repository root using
the interpreter the task names. Signatures, texts and formats are in plan.md. No test calls a real
Codex: use a fake runtime through `monkeypatch.setattr(registry, 'load', ...)` or the fake
companion of `tests/test_runtime.py`.

## Config (FR-001)

- [X] T001 In `tests/test_workspace.py`, add failing tests: a default config gives
  `config['gates'] == {'second_opinion': 'off', 'second_opinion_role': 'quality'}`;
  `second_opinion = "codex:gpt-6-astra"` loads; `"codex"`, `"codex:"`, `"codex:bad model"`,
  `"unknown:m"`, `"claude:opus"` and `"none:m"` each raise `ConfigError` naming
  `gates.second_opinion`; `second_opinion_role = "goal"` raises `ConfigError`; the shipped template
  still loads. Fails today: `KeyError: 'gates'`.
- [X] T002 In `cli/wuwei/workspace.py`, add the `gates` schema and the `load_config` check; in
  `templates/workspace/config.toml`, add the `[gates]` block; in `docs/site/configuration.md`, add
  `[gates]` to Sections and the two key rows. `tests/test_docs.py` passes.

## Tier and gate set (FR-002, FR-003)

- [X] T003 In `tests/test_dispatch.py`, using the `tiered` helper, add failing tests: with
  `[gates] second_opinion = "codex:m1"`, a STANDARD and a FULL item record
  `second_opinion == {'role': 'quality', 'runtime': 'codex', 'model': 'm1'}` and
  `gate_set(row) == ('arch', 'quality', 'security', 'quality@codex')`; `second_opinion_role =
  "security"` gives `security@codex`; a LIGHT item has no `second_opinion` key and
  `gate_set == ('quality',)`; with the option off the tier record has no `second_opinion` key;
  a recorded `second_opinion` with a role outside the roles, a non-dict, or a model with a space
  raises `ValueError('invalid recorded gate set')`. Fails today: no `second_opinion` key.
- [X] T004 In `cli/wuwei/dispatch.py`, extend `tier` and `gate_set`; add `base(gate)`.

## Brief and launch guard (FR-005, FR-007)

- [X] T005 In `tests/test_brief.py`, add a failing test: `brief.write('sentinel-quality', 'A',
  'q-1-codex', body, gate=True, second_opinion={'role': 'quality', 'runtime': 'codex', 'model':
  'm1'})` writes a header line `Model: m1` and logs `second_opinion: 'codex:m1'` in the
  `brief written` payload; without the keyword neither appears. Fails today: unexpected keyword.
- [X] T006 In `cli/wuwei/brief.py` `write`, add the `second_opinion` keyword.
- [X] T007 In `tests/test_agent_launch.py`, add a failing test: a PreToolUse Agent launch of a logged
  second-opinion brief (Claude seat policy) is refused with
  `second-opinion brief runs through wuwei dispatch opinion, not Agent` and no seat is written; a
  first-model gate brief still launches. Fails today: the launch is accepted.
- [X] T008 In `cli/wuwei/guards/agent_launch.py`, add the refusal after the hash check.

## Codex adapter (FR-006)

- [X] T009 In `tests/test_runtime.py`, add failing tests with the fake companion: a brief whose
  header has `Model: m1` dispatches `task` with `--model m1`; a brief without it passes no
  `--model`; a `Model:` line in the body only (after the first blank line) is ignored; the job
  handle carries `brief`; `result` with role `sentinel-quality` ignores a fresh arch verdict file
  `gate-a-1.md` that fails the quality lint and lints the job's own `gate-<brief stem>.md`
  (a bad own file still returns exit 1). Fails today: no `--model`, and the arch file fails the
  result.
- [X] T010 In `adapters/runtime/codex.py`, add the model option, `brief` in the job handle through
  `_started` and `continue_job`, and the own-file lint in `result`.

## Shared helpers from build (refactor under green)

- [X] T011 Run `tests/test_build.py` and `tests/test_e2e_day.py`; they pass before the change.
- [X] T012 In `cli/wuwei/commands/build.py`, extract `wait(runtime, job, config)` from `run_loop`
  and `normalize_usage(reported, model)` from `record_result`; both callers use them. Rerun T011's
  files: they pass unchanged.

## Dispatch next offers the run action (FR-004)

- [X] T013 In `tests/test_dispatch.py`, add failing tests on a STANDARD item with the option on:
  before any gate brief, `next_step` returns `roles == ['arch', 'quality', 'security',
  'quality@codex']` and no `run` seat; after logging the three first-model briefs, `seats` holds
  three `launch` actions and one `{'action': 'run', 'gate': 'quality@codex', 'runtime': 'codex',
  'model': 'm1', 'command': 'wuwei dispatch opinion A'}`; a logged second-opinion brief is never
  offered as a `launch`. Fails today: `gate_set` has no fourth gate, so no run action.
- [X] T014 In `cli/wuwei/dispatch.py` `_seats`, add the primary filter, the `run` action and
  `_delta_feedback`.

## Receive accepts the fourth gate, with usage and findings (FR-008, US3)

- [X] T015 In `tests/test_state.py`, add a failing test: `state.stop_seat` writes `stopped_at`.
  Fails today: no key.
- [X] T016 In `cli/wuwei/state.py` `stop_seat`, set `stopped_at`; update the `seats` producer label.
- [X] T017 In `tests/test_dispatch.py`, add failing tests: a stopped seat registered for
  `sentinel-quality` with a valid quality verdict is received as gate `quality@codex`; the record
  has `runtime: 'codex'`, `model: 'm1'`, `findings` (every finding block) and the seat's `usage`;
  a Claude sentinel record has `usage.duration` equal to its seat stop minus start, its seat-policy
  model, and `unmeasured` cost; receive of `quality@codex` refuses an item whose gate set lacks
  it; a second-opinion verdict at a HEAD different from the sibling records is refused; an arch
  verdict file is refused for `quality@codex` (lint as quality). Fails today:
  `unknown gate role or round`.
- [X] T018 In `cli/wuwei/dispatch.py` `receive`, accept any gate in the gate set, use the base role
  for seat, lint and scanner, iterate the gate set for sibling heads, and add `findings`, `usage`,
  `runtime` and `model`.

## The runner (FR-005, US1 acceptance 1)

- [X] T019 In `tests/test_dispatch.py`, add failing tests with a fake runtime (records calls;
  `dispatch` returns `{'id': 'j1', 'started_at': 0}`, `status` returns `completed` with
  `model: 'm1'`, `result` returns a valid quality verdict text at the item HEAD and usage
  `{'cost': 0.42}`):
  1. `dispatch.opinion('A')` on a STANDARD item with the three first-model briefs logged writes
     brief `q-1-codex` with the quality body and `Model: m1`, calls `dispatch('sentinel-quality',
     <brief>, <worktree>, True)`, writes `gate-q-1-codex.md` from the result text, leaves seat
     `q-1-codex` stopped with `runtime`, `model`, `job` and `usage.cost == 0.42`, appends one
     `seat.usage` event with `gate: 'quality@codex'`, and returns the `A:quality@codex:initial`
     record carrying `runtime: 'codex'` and `model: 'm1'`.
  2. After receiving the three Claude verdicts, four records exist and `next_step` returns
     `raise` (acceptance 1).
  3. A rerun after the record exists returns it and calls nothing; a rerun with the seat
     `running` and a job polls that job and does not call `dispatch`.
  4. A verdict file the seat wrote after `started_at` is kept, not overwritten.
  5. A result text that fails the lint exits through `Refused`; a rerun calls `continue_job` with
     the rejection feedback and records the fixed verdict.
  6. Adapter exit 2 on dispatch, status `failed`, and a poll timeout each raise and record no
     verdict; the host seat ceiling refuses before `dispatch`; no first-model brief refuses with
     `write the quality gate brief first`; an item without a second opinion refuses.
  Fails today: `AttributeError: opinion`.
- [X] T020 In `cli/wuwei/dispatch.py`, add `opinion` as in plan.md section 5.
- [X] T021 In `tests/test_dispatch.py`, add a failing CLI test: `main('dispatch', 'opinion', 'A')`
  prints the record JSON and exits 0; a `Refused` exits 1; a `PortExit(2, ...)` exits 2. Fails
  today: argparse rejects `opinion`.
- [X] T022 In `cli/wuwei/commands/dispatch.py`, add the `opinion` subcommand and exit mapping; in
  `cli/wuwei/commands/event.py`, update the three producer labels.

## Disagreement rule, fix round, delta and PR guard (US1 acceptance 2 to 4)

- [X] T023 In `tests/test_dispatch.py`, add failing tests: first-model gates PASS and the second
  opinion FIX with `blocks: yes` makes `next_step` open the fix round with feedback naming
  `gate-q-1-codex.md` and `roles == ['quality@codex']`; after the fix build, `next_step` in delta
  returns only the `quality@codex` `run` action; the runner calls `continue_job` with the delta
  feedback (same runtime and model) and records the `delta` round; a delta verdict still
  blocking makes `next_step` return `escalate`; a non-blocking residual becomes a review note on
  `raise`; a FULL item gets the same fourth gate; a LIGHT item with the option on returns only
  the quality gate and no `run` action. Before T004 to T020 these fail (no fourth gate); they pin
  the disagreement rule against later changes.
- [X] T024 No production change expected: `next_step` already applies the rule through
  `gate_set`. Fix only what T023 shows.
- [X] T025 In `tests/test_pr_guards.py`, add failing tests on recorded verdicts: with the item gate
  set holding `quality@codex`, `gate_check` returns 1 naming `quality@codex` when its record is
  missing, and when its delta still blocks; it returns 0 with four passing records; the
  second-opinion verdict is linted as a quality verdict (missing `Simplicity:` fails). Fails
  today: the lint flag is `role == 'quality'`, so the second opinion is linted without the
  quality rows.
- [X] T026 In `cli/wuwei/guards/pr.py` `_recorded_gates`, lint with the base role.

## Retro (FR-009, US2)

- [X] T027 In `tests/test_report_retro.py`, add failing tests: a day with initial records
  `A:quality` (findings citing `cli/a.py:1` and `cli/b.py:2`) and `A:quality@codex` (findings
  citing `cli/a.py:1` and `cli/c.py:3`, `runtime: codex`, `model: m1`, `usage.cost 0.42`) compiles a
  retro whose `## Second opinion` section lists `cli/c.py:3` under `quality@codex m1`, `cli/b.py:2`
  under `quality`, not `cli/a.py:1`, and both verdicts' model, cost and duration; a day without a
  second-opinion record has no `## Second opinion` heading; a record without `findings` or
  `usage` renders `none` and `unmeasured`. Fails today: no section.
- [X] T028 In `cli/wuwei/retro.py` `compile`, add the section.

## Docs and final checks

- [X] T029 Update `skills/wuwei-plan/SKILL.md`, `docs/site/reference.md` and
  `docs/site/concepts.md` as in plan.md section 12. Run `tests/test_docs.py`,
  `tests/test_charters.py` and `tests/test_skill_evals.py`.
- [X] T030 With the option off, run `tests/test_verdict.py`, `tests/test_dispatch.py`,
  `tests/test_guard_mutation.py`, `tests/test_state_allowlist.py` and `tests/test_adapters.py`
  (acceptance 5), then the full suite `python -m pytest -q`. Check every written file for
  em-dashes, emojis and absolute local paths.

## Review fixes

- [X] T031 (F1) `receive` binds the seat to the gate: a `role@runtime` verdict needs a seat
  that ran on that runtime and is named `<first seat>-<runtime>`; a plain role refuses a seat
  with a runtime. The record's runtime and model come from the seat. Test:
  `test_receive_binds_the_seat_runtime_to_the_gate`.
- [X] T032 (F2) `opinion` refuses to continue a second-opinion job when the builder runs on the
  same runtime, since the resumed thread could be the builder's. Test:
  `test_opinion_delta_refuses_to_resume_on_the_builder_runtime`.
