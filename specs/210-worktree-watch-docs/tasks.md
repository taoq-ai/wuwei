# Tasks: Worktree command, watch install safety and operator docs

Each test task is written, run and seen failing for the stated reason before its implementation task.

## Phase 1: Anchored item worktree [US1]

- [X] T001 [US1] Add a failing end-to-end test in tests/test_worktree_command.py: temporary workspace with a `git clone --shared` repository configured under `[[repos]]`, a bare origin, gate approved, `.wuwei/executable` pointing to a stub that records its argv and `WUWEI_WORKSPACE` then exits 1; run `main(['worktree', 'add', 'X'])` with `WUWEI_WORKSPACE` unset; commit in `worktrees/X`; run `git push origin x` from the worktree with `WUWEI_WORKSPACE` and `GIT_*` removed from the environment; assert the push fails, the stub saw `git-hook pre-push` and the workspace path, and the printed JSON names branch `x` and the worktree path. Expected failure: `worktree` is not a command.
- [X] T002 [US1] Add failing table tests in tests/test_worktree_command.py with the fake vcs from tests/fakes/vcs.py (patch `registry.load`): no gate approval exits 1 with no vcs call; one repo needs no `--repo`; two repos without `--repo` exit 2 naming `--repo`; `--repo <name>` selects that repo path; unknown `--repo` exits 2; item `../x` exits 2 with no vcs call.
- [X] T003 [US1] Implement cli/wuwei/commands/worktree.py (`register`, `run`) calling `workspace.create_worktree` with the selected repo path, `item.lower()`, `root / 'worktrees' / item` and `registry.load('vcs', config)`; validate the item with `brief.identifier`; map `state.StateError` to exit 1.

## Phase 2: Safe watch install and uninstall [US2]

- [X] T004 [US2] Add failing tests in tests/test_quiet_sweeps.py: `watch install --dry-run` on Linux and macOS exits 0, prints the unit path, rendered unit and service argv, creates no file and never calls the service adapter.
- [X] T005 [US2] Add failing tests in tests/test_quiet_sweeps.py: a service adapter that raises on `launchctl bootstrap` (macOS) and on `systemctl --user enable` (Linux) makes install exit 2 with the reason and leaves no unit file; a second install with a working adapter exits 0 and the unit exists.
- [X] T006 [US2] Add a failing test and update `test_mac_watch_installer_escapes_values_and_reports_service_failure` in tests/test_quiet_sweeps.py: uninstall with a failing stop command exits 0, prints the failure as a warning on stderr and removes the unit; uninstall with no unit exits 0.
- [X] T007 [US2] Implement in cli/wuwei/commands/watch.py: `--dry-run` on `install`, the shared `_remove(path, platform, service)` teardown with warning-only service failures, uninstall through `_remove`, and install that writes, loads, and on failure calls `_remove` then re-raises.

## Phase 3: Dead watch is visible [US3]

- [X] T008 [US3] Add failing tests in tests/test_quiet_sweeps.py: with day state and no clock line, `attention` has one page with source `watch: health`, `snapshot` has `watch == 'dead'`, `status --line` contains `watch dead`, and `main(['nudges'])` lists the page; a later partial `sweep obligations` event (`obligations.sweep` payload) still leaves the page; a full sweep with `watch_dead: 1` followed by a fresh `watch: clock` shows no watch row and `watch == 'alive'`; a clock line in the future gives a `watch: health` nudge, `watch == 'unmeasured'` and `watch unmeasured` in the line.
- [X] T009 [US3] Add a fresh `watch: clock` event to the fixtures of tests/test_quiet_sweeps.py (`test_nudges_show_current_conditions`, `test_nudges_clear_pr_action_and_mcp_finding`, `test_three_sweep_obligations_make_three_nudges`) and tests/test_signal_status.py (`test_status_line_and_json_share_snapshot`, `test_status_counts_escalation_from_current_state`) so they keep asserting their own counts.
- [X] T010 [US3] Implement in cli/wuwei/commands/status.py: live `watch.health(directory.parents[2])` row in `attention` replacing sweep watch rows, `snapshot()['watch']` derived from the active rows, and the `watch dead` or `watch unmeasured` line part.

- [X] T010a [US3] Add failing tests: no clock line today (a clock yesterday only) gives `watch.health` `(0, 'watch off: ...')`, empty attention, `watch == 'off'`, `watch off` in the line and no nudge; a clock today gone stale pages `watch dead` until a fresh clock; SessionStart says `watch off` with exit 0 when never started and `watch dead` with exit 1 when stale; sweep tests that expect `watch_dead: 1` start from a stale clock today. Implement `watch.health(root, clocks=None)` over today's clock lines only and `status.scan` reading events once (no second read through `watch.health`, no per-event `workspace.now()`), restoring the status line latency budget; document `watch off` versus `watch dead` in reference.md and configuration.md.

- [X] T010b [US3] Add failing tests: an installed unit (under tmp_path) with only yesterday's clock gives `watch.health` code 1, one `watch: health` page, `watch dead` in the line and one nudges row; `watch uninstall` turns it into `off` with no rows; an installed unit with a fresh clock is alive. Move the unit path into `workspace.watch_unit(root, platform)` used by install, uninstall and `watch.health`; make an installed unit without a fresh clock dead; update the Watch state docs.

- [X] T010c [US3] Add failing table tests in tests/test_quiet_sweeps.py: `bin/wuwei watch uninstall`, `python3 -P -m wuwei watch uninstall`, `python3 -P -mwuwei watch uninstall` and `sh -c` form exit 1 inside a workspace; `watch install --dry-run`, `watch --once`, `grep uninstall docs/`, `python3 -m pytest -q`, a `for` loop and `export X=1` exit 0; uninstall outside a workspace exits 0. Refuse `watch uninstall` in cli/wuwei/guards/protect_state.py beside the drafts and MCP owner actions; document it and correct the uninstall clearing rule in reference.md and configuration.md.

## Phase 4: Operator reference [US4]

- [X] T011 [US4] Add failing tests in tests/test_docs.py: the fenced verdict example in docs/site/reference.md passes `verdict.lint(text, quality=True, class_sweep=True)` with exit 0; every `state.PHASES` key appears as a table row with its next phases joined by `, `; reference.md mentions `worktree add`, `stdin` and `sentinel-arch`; configuration.md mentions `--dry-run` and `watch dead`; skills/wuwei-plan/SKILL.md mentions `wuwei worktree add`.
- [X] T012 [US4] Write the Item worktrees, Seat briefs, Item phase order and Gate verdict layout sections in docs/site/reference.md.
- [X] T013 [US4] Update "Running the watch" in docs/site/configuration.md and "Item dispatch and receive" in skills/wuwei-plan/SKILL.md.

## Phase 5: Verify

- [X] T014 Run `python -m pytest -q` from the repository root; everything passes. Check every changed file for em-dashes, emojis and absolute local paths.
