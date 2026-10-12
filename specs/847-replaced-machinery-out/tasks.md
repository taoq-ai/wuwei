# Tasks: delete what the derived next replaced

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 71d3f06b.

Run tests with `python -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: Setup

- [X] T001 Delete the autouse `quiet_heartbeat` fixture in `tests/conftest.py:22-29`; run
  `tests/test_cli.py tests/test_hooks.py`: green (the fixture only quieted the heartbeat).

## Phase 2: The log is the only record (US3, P1)

- [X] T002 [US3] Red in `tests/test_state.py`: a write leaves no `state.json` and no
  `state.snapshot.json`; a torn last line is skipped and the records before it read; a pre-#844
  day (a `state.json`, no patch in its log) reads that file and writes nothing; a malformed
  middle line raises DAMAGED naming `bin/wuwei doctor`; `_write_state` takes no `reserved`.
  Run: red.
- [X] T003 [US3] Edit `cli/wuwei/state.py` and `cli/wuwei/exits.py` per plan.md; drop
  `reserved=False` at every caller (`grep -rn "reserved=" cli tests`); delete
  `cli/wuwei/commands/state.py`, `cli/wuwei/commands/event.py`, `tests/test_state_allowlist.py`
  and the state, recover, snapshot, transition-check and event-command tests named in plan.md;
  move `EVENT_PRODUCERS` to `commands/why.py` and `FREE_KINDS` to `obligations.py`; edit
  `memory.py`, `guards/protect_state.py` (snapshot name, hint), `signal.py`, `telemetry.py`
  (`state.recovered`). Remove the `main(['event'|'state', ...])` refusal cases across tests.
  Run `tests/test_state.py tests/test_why.py tests/test_protect_state.py tests/test_loop.py
  tests/test_derive.py tests/test_next.py tests/test_dispatch.py tests/test_build.py
  tests/test_plan.py tests/test_merge.py`: green.

## Phase 3: The kept jobs move (US4, P1)

- [X] T004 [US4] Red: `tests/test_merge.py` asserts `next.run` calls `merge.poll` when it
  refreshes the listing and `report` calls it once; `merge.monitor` makes no tracker call on a
  merge (a `tracker` duty is due instead, `tests/test_derive.py`); `tests/test_telemetry.py`
  asserts `report` records a finished week; `tests/test_ziran.py` asserts `dispatch receive`
  and `close` run `scanner.trace_sweep` (page and park as before). Run: red.
- [X] T005 [US4] Edit `merge.py`, `commands/next.py`, `commands/report.py`, `dispatch.py`,
  `closing.py` (drop `obligations.evaluate`, add the trace sweep), `obligations.py` (delete
  `evaluate`, `sweep` and helpers only they read), `pr_actions.py` (`_watched`). Run the T004
  files plus `tests/test_close_branches.py tests/test_close_parked.py tests/test_pr_actions.py
  tests/test_steward.py`: green.

## Phase 4: No background process, no session registry (US1, P1)

- [X] T006 [US1] Red: `tests/test_doctor.py` `test_day_rows` and `test_guards_rows` over the new
  probes (a refused and an allowed `wuwei hook` probe, exit codes only; state readable; stuck
  seats from the seat ledger); `tests/test_edges.py` the force-push probe row is the doctor
  probe; `tests/test_cli.py` help lists none of the nine commands. Run: red.
- [X] T007 [US1] Delete `heartbeat.py`, `commands/{heartbeat,watch,shepherd,sessions,
  fast_checks,runtime}.py`, the watch templates, `tests/test_watch.py` (after moving its
  survivors per plan.md), `tests/test_heartbeat.py` (survivors), `tests/test_headless_shepherd.py`,
  `tests/test_sessions.py` (survivor), `tests/test_obligations.py` (survivors),
  `tests/test_quiet_sweeps.py`, `tests/test_runtime_cli.py`. Edit `watch.py`, `shepherd.py`,
  `plan.py`, `workspace.py` (`_DAY`, claims), `sessions.py`, `brief.py`, `commands/hook.py`
  (`claimed`), `commands/status.py`, `commands/doctor.py`, `commands/sweep.py`,
  `commands/build.py` strings, `adapters/watch_service.py`, `metrics.py`, `report.py`,
  `retro.py`. Run every test file plan.md names under these modules: green.

## Phase 5: Hooks and guards (US1, US2, P1)

- [X] T008 [US1] Red: `tests/test_hooks.py` asserts `hooks/hooks.json` registers exactly
  PreToolUse, PostToolUse, SubagentStop and SessionStart and `wuwei hook Stop` is refused by
  argparse. Run: red.
- [X] T009 [US1, US2] Delete `guards/stop.py`, `tests/test_stop.py` (after moving the
  `closing.check` cases), `tests/payloads/PreCompact/`, `tests/payloads/Stop/`; edit
  `hooks/hooks.json`, `guards/__init__.py`, `guards/lifecycle.py`, `commands/hook.py`. Run
  `tests/test_hooks.py tests/test_close_branches.py tests/test_e2e_day.py tests/test_path_day.py
  tests/test_headless_e2e.py tests/test_edges.py`: green (the default-branch push rows pass
  unchanged).

## Phase 6: Git hooks, the anchor and the upgrade (US2, US5)

- [X] T010 [US5] Red: `tests/test_worktree_command.py` asserts `worktree add` writes
  `<git dir>/wuwei-workspace` and sets no `core.hooksPath`; `tests/test_config_transition.py`
  asserts `init --upgrade` on a workspace with a hooked worktree (both the shim and the chain
  value) unsets `core.hooksPath`, removes `<git dir>/wuwei-hooks` and `.wuwei/git-hooks/`, keeps
  an owner-set `core.hooksPath`, removes `[watch]`, `[sessions]`, `worktree.git_hooks`, the
  watch and shepherd units and their lock and log files, prints one line each, and changes
  nothing under `--dry-run`. Run: red.
- [X] T011 [US5] Delete `commands/git_hook.py`, `commands/fast_checks.py`,
  `tests/test_git_hook.py`; edit `workspace.py` (`_anchor`, SCHEMA, `RETIRED`,
  `CONFIG_CACHE_VERSION`), `commit_push.py`, `adapters/vcs/git.py` (`unhook`), `registry.py`,
  `tests/fakes/vcs.py`, `commands/init.py` (`_unhook`, `_remove_unit`, `RETIRED_FILES`),
  `templates/workspace/config.toml`. Run `tests/test_worktree_command.py
  tests/test_config_transition.py tests/test_vcs.py tests/test_vcs_guard.py
  tests/test_commit_push.py tests/test_fast_checks.py tests/test_workspace.py
  tests/test_templates_errors.py`: green.

## Phase 7: Docs, charters, spec (FR-014)

- [X] T012 Edit `charters/builder.md:19`, run `bin/wuwei agents build`; edit the constitution,
  the design spec sections plan.md lists, `docs/site/reference.md` command table,
  `docs/site/configuration.md` sections, `scripts/headless_e2e.py`. Delete the LEFT row in
  `tests/test_reasons.py`; re-measure the corpus floor in `tests/test_invariants.py:79` with a
  comment naming part 23. Run `tests/test_docs.py tests/test_charters.py tests/test_agents.py
  tests/test_reasons.py tests/test_invariants.py tests/test_tone.py tests/test_dev_cycle.py`:
  green.

## Phase 8: Polish

- [X] T013 Run the SC-001 grep: empty. Run `bin/wuwei --help`: 36 commands. Run
  `tests/test_e2e_day.py tests/test_path_day.py tests/test_loop.py tests/test_edges.py
  tests/test_derive.py`: green.

## Dependencies

T001 first. Phase 2 before Phases 3 to 6 (every module reads state). T004 to T005, T006 to
T007, T008 to T009, T010 to T011. Phase 7 after the code. Batch 8's fix round: rebase onto it
before T013 (plan.md).
