# Tasks: SubagentStop back under its latency budget

Test first: each test task runs and fails (or, for a regression guard, passes) for the
stated reason before its implementation task. Fixtures are neutral: the latency test's
`seeded_workspace` (`ITEM-1`, seat `builder-1`, session `abc123`) and the `seat` fixture of
`tests/test_build_next.py`.

## Phase 1: one state write per seat stop (US1, the root cause)

- [X] T001 Test in `tests/test_hooks.py`: `test_subagent_stop_writes_state_once` (plan,
  Tests). Run it on the base: it fails with `fsync == 8` and `appends == 4`.
- [X] T002 Test in `tests/test_handback.py`: `test_unmatched_seat_stop_still_records_session`
  (US3.2). It passes on the base; it is the regression guard for the fold.
- [X] T003 Implement in `cli/wuwei/workspace.py`: `atomic_write(..., sync_dir=True)`.
- [X] T004 Implement in `cli/wuwei/state.py`: `_append_jsonl(path, *records)`,
  `_append_event(..., more=())`, `_write_state(..., more=())` with `sync_dir=False` for
  `state.json`, `stop_seat(..., session=None)`.
- [X] T005 Implement in `cli/wuwei/guards/lifecycle.py`: `seen_row`, `RECORDED`, the skip in
  `subagent_stop`.
- [X] T006 Implement in `cli/wuwei/guards/agent_launch.py` (`stop`): keep `data`, compute
  `session` for a stop in today's directory, pass it to both `stop_seat` calls, set the
  marker after a successful call. T001 and T002 pass; `tests/test_handback.py`,
  `tests/test_build_next.py`, `tests/test_sessions.py` and `tests/test_e2e_day.py` pass.

## Phase 2: no unused module on the common path (US1.4)

- [X] T007 Test in `tests/test_hooks.py`: `test_subagent_stop_loads_no_more_than_pretooluse`
  with `SUBAGENT_STOP_MODULES` (spec US1.4). Run it on the base: it fails naming `hashlib`,
  `_hashlib`, `_blake2`, `wuwei.decision` and `wuwei.commands.build`.
- [X] T008 Implement in `cli/wuwei/guards/decision.py`: the `wuwei.decision` names imported
  inside `check_write`, `record_gate` and `check_question`.
- [X] T009 Implement in `cli/wuwei/guards/verdict.py` (`check_retro`): `hashlib` after the
  charter check.
- [X] T010 Implement in `cli/wuwei/brief.py`: `hashlib` inside `last_turn` and `write`.
- [X] T011 Implement in `cli/wuwei/guards/agent_launch.py` (`stop`): import
  `wuwei.commands.build` only when the item has a build record. T007 passes;
  `tests/test_decision.py`, `tests/test_owner_edits.py` and the existing import-graph tests
  in `tests/test_hooks.py` pass.

## Phase 3: the report from the transcript's tail (US2)

- [X] T012 Test in `tests/test_handback.py`: `test_stop_text_reads_the_tail` (cases a and b).
  Run it on the base: case (a) fails with `UnicodeDecodeError` from `last_turn`'s full read.
- [X] T013 Test edit in `tests/test_handback.py`: `test_hook_reads_nothing_for_other_agents`
  also stubs `brief.tail_turn`. It fails on the base with `AttributeError` (no
  `tail_turn`), which is the expected red for a name this phase adds.
- [X] T014 Implement in `cli/wuwei/brief.py`: `_entry`, `last_turn` on `_entry`,
  `tail_turn`, `stop_text` on `tail_turn`. T012 and T013 pass; every test in
  `tests/test_handback.py` passes.

## Phase 4: verification

- [X] T015 Run the full suite with the task's interpreter: all green.
- [X] T016 Run `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency -s` and
  record the printed SubagentStop line in the final report. Check every file written for
  em-dashes, emojis and absolute local paths.
