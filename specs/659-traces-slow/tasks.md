# Tasks: A slow traces hook is a warning, the trace read uses the writer's digest, and the status line keeps its budget

**Input**: `specs/659-traces-slow/spec.md`, `specs/659-traces-slow/plan.md`

**Tests**: test first for every behaviour. Write the test, run it, see it fail for the
stated reason, then implement. Run tests with `python -m pytest -q` from the repository
root (the interpreter your task names). `[P]` marks tasks on different files with no
dependency on an unfinished task.

Fixture for the traces tests: a workspace with `[security]\nrequired = true\nposture =
"<posture>"\n` in `.wuwei/config.toml` and `security.initialize(root / '.wuwei')`,
`WUWEI_WORKSPACE` and `WUWEI_NOW` set as `tests/test_traces.py::trace_workspace` does.
Neutral names only; no owner paths.

## Phase 1: Foundational

- [X] T001 Test in `tests/test_traces.py`: `state.append_event('x.y', {}, root,
  timeout=0)` while another open file description holds `state.lock` raises
  `TimeoutError` at once (hold the lock with `fcntl.flock` on a second open of the lock
  file). Fails today with `TypeError` (no `timeout` keyword).
- [X] T002 Implement in `cli/wuwei/state.py`, `append_event`: keyword `timeout=30` passed
  to `lock_ex`. T001 passes.

## Phase 2: User Story 1, a slow traces hook warns (P1)

- [X] T003 Test in `tests/test_traces.py`, parametrized over observe, guarded and strict:
  a PostToolUse payload through `hook.run` (the file's `run_hook` helper) with
  `wuwei.security.trace_findings` replaced by a function raising
  `TimeoutError('state.lock remained locked for 30s')`. Assert exit 0 below strict and 2
  under strict; stderr matches `wuwei traces: did not finish in time after \d+ ms` and
  does not contain `remained locked`; one `traces.slow` event whose payload has
  `elapsed_ms` (int), `span` and `session`; no `traces.gap`. Fails today: exit 2 with
  `cannot inspect or record workspace security evidence` in every posture, no event.
- [X] T004 Test in `tests/test_traces.py`: the same with `state.append_jsonl` raising
  `TimeoutError` (the record path) under observe gives exit 0 and `traces.slow`; with it
  raising `OSError` the result is today's (`traces.gap`, exit as before). Fails today on
  the first half (`traces.gap`).
- [X] T005 Test in `tests/test_traces.py`: under observe with the trace read raising
  `TimeoutError` and `state.lock` held by another open file description, the guard returns
  within 3 s (the `traces.slow` append gives up after 1 s) and stderr says
  `could not log traces.slow`. Fails today (no slow path).
- [X] T006 Implement in `cli/wuwei/guards/traces.py`, `check`: `started`, `except
  TimeoutError: raise` ahead of the inner handler, the slow reason and kind in the outer
  handler and tail, `timeout=1` on the slow append, the strict-only return; add
  `_strict(root)` (or reuse #601's when `main` has it). T003 to T005 pass; the existing
  `tests/test_traces.py` and `tests/test_guard_mutation.py` pass unchanged.
- [X] T007 [P] Test in `tests/test_traces.py`: `'traces.slow' in event.EVENT_PRODUCERS`
  and `main(['event', 'traces.slow', '{}']) == 1`, as the `traces.gap` check at the end of
  `test_trace_gap_on_status_line_and_doctor` does. Fails today.
- [X] T008 [P] Test in `tests/test_signal_status.py`: add `'traces.slow': 'nudge'` to the
  expected map of `test_emitted_kinds_have_intended_tiers` (fails after T006 until the
  entry exists, because the kind is now emitted).
- [X] T009 Implement in `cli/wuwei/commands/event.py`: reserve `'traces.slow': 'wuwei hook
  PostToolUse'`. T007 and T008 pass.

## Phase 3: User Story 2, the digest replaces the rescans (P1)

- [X] T010 Test in `tests/test_steward.py`: with the default interval,
  `steward.maybe_run_for_tool_calls(10, root, 0)` returns 0 and does not call
  `watch.records` (replace it with a counter); with `every_tool_calls = 2`,
  `maybe_run_for_tool_calls(2, root, 0)` appends `steward.due` and returns 2, and after a
  `steward.run` at 3, `maybe_run_for_tool_calls(4, root, 2)` returns 3 with no new due.
  Fails today (no `base` argument).
- [X] T011 Implement in `cli/wuwei/steward.py`, `maybe_run_for_tool_calls`: the `base`
  gate and the returned base. T010 passes; `test_default_interval_is_250_tool_calls`
  passes unchanged.
- [X] T012 Test in `tests/test_traces.py`: five traced calls with the default interval on
  a day that already has events: `watch.records` is never called (counter), and
  `traces.digest.json` reads `{"tool_calls": 5, "steward": 0}`. Fails today
  (`watch.records` called five times, no digest).
- [X] T013 Test in `tests/test_traces.py`: a day with three span lines in `traces.jsonl`
  and no digest, then one traced call: the digest's `tool_calls` is 4. The same with a
  digest of `{"tool_calls": -1}` and with non-JSON text. Fails today (no digest).
- [X] T014 Implement in `cli/wuwei/guards/traces.py`: `_digest`, the `started` keyword on
  `_record`, and the replacement of the line count and steward call at `:75-80` with the
  digest and the gated steward call. T012 and T013 pass, and
  `tests/test_steward.py::test_trace_threshold_marks_steward_due_without_launch` passes
  unchanged (dues at 2 and 5).
- [X] T015 Test in `tests/test_traces.py`: with `every_tool_calls = 1` and
  `traces.BUDGET_MS` set to 0 by monkeypatch, a traced call appends no `steward.due`; with
  the default budget the next call appends it. Fails until the budget skip exists.
- [X] T016 Implement in `cli/wuwei/guards/traces.py`: `BUDGET_MS = 1000` and the skip.
  T015 passes.
- [X] T017 Test in `tests/test_traces.py`: a seat in state whose `brief` the transcript's
  first user line names; three traced calls from the same session add exactly one
  `state.write` event (the first bind) and the seat holds the transcript and session.
  Fails today (three `state.write` events).
- [X] T018 Implement in `cli/wuwei/guards/traces.py`, `_record`: read state first and skip
  `_write_state` when already bound. T017 passes.
- [X] T019 [P] Test in `tests/test_protect_state.py`: a Write to
  `.wuwei/days/<date>/traces.digest.json` is refused like `traces.jsonl`. Fails today.
- [X] T020 Implement in `cli/wuwei/guards/protect_state.py:370`: add
  `'traces.digest.json'`. T019 passes.

## Phase 4: User Story 3, the status line keeps its budget (P2)

- [X] T021 Test in `tests/test_heartbeat.py`: after `heartbeat.beat(root)` on the `ws`
  fixture, `watch.saved(root)['status_line']` is a string matching
  ` · as of \d\d:\d\d$` and at most `status.WIDTH` long. Fails today (no key).
- [X] T022 Implement in `cli/wuwei/heartbeat.py`, `beat`: render and save `status_line`
  with the heartbeat record. T021 passes; the other heartbeat tests pass unchanged.
- [X] T023 Test in `tests/test_heartbeat.py`: with `watch.save(root, {'status_line':
  'cached line · as of 12:00'})` and `status.snapshot` replaced by a fake that waits on a
  `threading.Event` for up to 5 s, `status.run(SimpleNamespace(line=True, json=False,
  width=status.WIDTH))` returns 0 in under 1 s and prints the cached text; set the event
  in a `finally`. Fails today (waits 5 s and prints the computed line).
- [X] T024 Test in `tests/test_heartbeat.py`: with no cached line and the same fake
  released after 0.3 s, `status.run` prints the computed line; with a fake raising
  `ValueError` at once and a cached line present, it prints `WUWEI ? unmeasured` and
  returns 2. Passes today; it pins the unchanged paths.
- [X] T025 Implement in `cli/wuwei/commands/status.py`: `LINE_BUDGET_MS = 100` and the
  thread and cache fallback in `run` for the default width. T023 and T024 pass.

## Phase 5: Invariant, docs, suite

- [X] T026 Test in `tests/test_invariants.py`: the new invariant I50 (reserved for this
  item): per posture, `traces.check` in its own security-enabled workspace with
  `security.trace_findings` swapped for a `TimeoutError` raiser by plain assignment and
  restored in `finally`; below strict `(0, '')`, strict `2` with `did not finish in time`
  in the reason; memoised per posture; registered in `INVARIANTS` and `READS` with
  `(0,)`. It passes after T006; check it fails with T006 reverted.
- [X] T027 [P] Docs: the 9.2 row in `docs/specs/2026-09-24-wuwei-design.md` and the two
  sentences in `docs/site/reference.md` (around line 217). Run the docs tests.
- [X] T028 Run the full suite; everything passes, the invariant walk inside its budget.
  Check every file you wrote for em-dashes and emojis and remove any.
