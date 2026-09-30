# Tasks: Hook latency budget and corrupt state recovery

Every behaviour has a test task before its implementation task. Run each new test and see
it fail for the expected reason before writing the code. Tests run in-process unless the
task says subprocess.

## Phase 1: Setup

- [X] T001 Write specs/211-latency-recovery/spec.md, research.md, plan.md and tasks.md from issue #211 and the dry-run reproduction.

## Phase 2: US1 Hooks inside the latency budget (P1)

Independent test: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k workspace_hook_latency` prints p95 CPU and wall for five paths and every wall p95 is under 100 ms.

### Benchmark first

- [X] T002 [US1] Add `wall_budget` to `assert_latency_budget`, a parametrised case to `test_latency_budget_decision` for it, the seeded workspace fixture (repo, bare origin, worktree `worktrees/ITEM-1`, today's day with claimed PR, planner session, running builder seat and brief, fast-check evidence, fresh watch record, about 1000 events, recording `gh` stub on PATH) and `test_workspace_hook_latency` for Stop, SubagentStop (builder), SessionStart, PreToolUse commit and PreToolUse push, restoring the seeded day before each run and asserting exit 0 and no `gh` call, in tests/test_hooks.py. Run with `WUWEI_BENCH=1` and record the failing report (Stop and SubagentStop call `gh`; commit and push over budget).

### Stop fast path

- [X] T003 [P] [US1] Add failing tests in tests/test_pr_actions.py: `check(root)` returns `(0, '')` without calling `evaluate` (monkeypatched to raise) when the watch record is fresh, covers every owned PR and has no overdue episode; it calls `evaluate` when `measured_at` is missing, older than two poll intervals, in the future, when an owned PR is missing from `watch.prs`, when an episode deadline has passed, when there are no owned PRs, and when `closing=True`.
- [X] T004 [US1] Implement `_watched(root)` and the first line of `check` in cli/wuwei/pr_actions.py.
- [X] T005 [P] [US1] Add failing tests in tests/test_watch.py: `poll` saves `measured_at` (the poll start time) when every owned PR is read, and keeps the previous value when one PR read fails.
- [X] T006 [US1] Record `measured_at` in `poll` in cli/wuwei/watch.py.

### Seat-free discovery in the watch

- [X] T007 [P] [US1] Add failing tests in tests/test_dispatch.py: `dispatch.discovery('seat-free', root)` appends `discovery.requested` and does not call `discovery.intake` (monkeypatched to raise); the sweep trigger still calls it with `found`.
- [X] T008 [US1] Run intake only for the sweep trigger in cli/wuwei/dispatch.py.
- [X] T009 [P] [US1] Add failing tests in tests/test_watch.py: `tick` runs `discovery.intake(root, trigger='seat-free')` once when the last discovery event is a seat-free `discovery.requested`, not again after `discovery.intake`, and on failure appends one `discovery.unmeasured` with the reason, returns 2 and does not retry on the next tick.
- [X] T010 [US1] Add the pending-discovery step at the end of `tick` in cli/wuwei/watch.py.

### Concurrent git reads

- [X] T011 [P] [US1] Add failing tests in tests/test_vcs.py that replace `git._run` with a function waiting on a `threading.Barrier` sized to the independent reads (4 for `commit_context`, 5 for `push_context` with a valid remote, 2 for `workspace_changes` with `status` also replaced), so sequential reads break the barrier; assert the returned data is unchanged. Keep the existing single-failure message tests green.
- [X] T012 [US1] Add `_together` and use it in `commit_context`, `push_context` and `workspace_changes` in adapters/vcs/git.py, keeping the existing check order and the `_run` allowlist.

### One config parse per process

- [X] T013 [P] [US1] Add failing tests in tests/test_workspace.py: two `load_config` calls on unchanged text parse once (count `workspace.tomllib.loads`); changed text parses again; mutating a returned config does not change the next result; an invalid config still raises every time.
- [X] T014 [US1] Add the `_CONFIGS` memo with a `ponytail:` comment to `load_config` in cli/wuwei/workspace.py.

### Budget check

- [X] T015 [US1] Rerun T002 with `WUWEI_BENCH=1`; all five wall p95 values under 100 ms and no `gh` call. If a path is still over, apply the lazy-import step from research.md in cli/wuwei/guards/stop.py and cli/wuwei/guards/lifecycle.py and measure again.

### Review fixes

- [X] T026 [US1] Cut the push path from four sequential git rounds to two: one `git config -z --get-regexp` read replaces the three push setting reads in adapters/vcs/git.py (Git booleans parsed locally); the guard reads `push_context` alongside `commit_context` when no repository override is set (cli/wuwei/guards/commit_push.py); `push_commits` reads the tracking ref and both candidate ranges in one round, using the default branch range for a new branch. Tests in tests/test_vcs_guard.py and tests/test_commit_push.py. The owner's quiet-host `WUWEI_BENCH=1` run must pass all five paths before merge.
- [X] T027 [US1] A poll that misses any PR, or fails before reading, clears `watch.measured_at` in cli/wuwei/watch.py so the Stop fast path falls back to a live read. Test in tests/test_watch.py.

## Phase 3: US2 Recover a corrupt state file (P1)

Independent test: truncate today's `state.json`; state reads name `wuwei state recover`; recover with a confirming stub restores the last written state and hooks read it.

- [X] T016 [P] [US2] Add failing tests in tests/test_state.py: a truncated `state.json` makes `read_state` raise a message containing `wuwei state recover`; every `_write_state` leaves `state.snapshot.json` equal to `state.json` with mode 0444.
- [X] T017 [US2] Add `_load`, the message and the snapshot write in cli/wuwei/state.py.
- [X] T018 [P] [US2] Add failing tests in tests/test_state.py for `state.recover(root, confirm=...)`: truncated state and valid snapshot restores it, appends `state.recovered` with the snapshot digest, and `read_state` then succeeds; missing `state.json` with a snapshot also restores; readable state raises `StateError` and changes nothing; declined confirmation raises `StateError` and changes nothing; a confirm that raises `OSError` propagates and changes nothing; missing or invalid snapshot raises a non-`StateError` and leaves `state.json` as it was; a snapshot changed during confirmation is refused.
- [X] T019 [US2] Implement `recover` in cli/wuwei/state.py.
- [X] T020 [P] [US2] Add failing CLI tests in tests/test_state.py (in-process `main`): `wuwei state recover` exits 0 with a monkeypatched `integrity._host_confirm` returning True, 1 when it returns False or state is readable, 2 with no snapshot; and a hook run on the truncated state (for example Stop for the planner session) reports the recovery hint, then passes the state read after recovery.
- [X] T021 [US2] Add the `recover` action in cli/wuwei/commands/state.py and `state.recovered` to `EVENT_PRODUCERS` in cli/wuwei/commands/event.py.
- [X] T022 [P] [US2] Add failing tests in tests/test_protect_state.py: `bin/wuwei state recover` and `python3 -P -m wuwei state recover` through Bash inside a workspace exit 1 with the owner-action message; the same text outside any workspace exits 0; Write and Edit of `.wuwei/days/<date>/state.snapshot.json` are refused.
- [X] T023 [US2] Add the snapshot name to `_protected_name` and the recover clause to `check_bash` in cli/wuwei/guards/protect_state.py.

## Phase 4: Polish

- [X] T024 [P] Add the "State recovery" section to docs/site/reference.md and update the seat-free discovery sentence in docs/site/configuration.md.
- [X] T025 Run `python -m pytest -q` with the task's interpreter; all green. Scan every authored file for em-dashes, emojis and absolute local paths.

## Dependencies

T002 first (it is the red benchmark). Within US1 each implementation task follows its test task; T003 to T014 pairs are independent of each other; T015 after all of them. US2 (T016 to T023) is independent of US1 and may run in parallel; T017 before T018, T019 before T020. T024 and T025 last.

## Implementation strategy

US1 and US2 are both P1 and independent. Land the benchmark and the two network moves first (largest effect), then git concurrency, then the config memo, measuring after each. US2 is a self-contained slice in the state writer, its command and the Bash guard.
