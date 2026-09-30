# Tasks: The loop's joints between build, gates, delta and push

Each test task is written and run red before its implementation task. Run tests with
`python -m pytest -q` from the repository root.

## Joint 1: build done hands the item to the gates (US1)

- [X] T001 Add failing tests in `tests/test_build_next.py`: a Claude step loop started on an
  item in `planned` moves it to `implement` at launch (a repeated `build next` writes no
  event); after `build check` passes and `build next` returns done the phase is `gate`;
  a build started in `fix` ends in `delta` with no `fix_rounds` set. Extend the `seat`
  fixture vcs with `commit_context` (needed from T010 on) and start the item in `planned`
  where the test needs it.
- [X] T002 Change `tests/test_e2e_day.py` (both tests) to drop the planner's
  `transition('implement')`, `transition('gate')` and `transition('delta')`; keep the
  asserted transition list `implement, gate, fix, delta, raised, merged`. Update
  `tests/test_build.py::test_green_on_second_iteration_records_two_usages` to expect
  `gate`. Run: red.
- [X] T003 Implement in `cli/wuwei/commands/build.py`: `next_action` transitions
  `planned -> implement` after saving a new build record; `complete_checks` on green maps
  `implement -> gate` and `fix -> delta` through `state.transition`, replacing the
  `fix_rounds == 1` condition. Run T001 and T002 green.

## Joint 2: brief accepts dispatch role names (US2)

- [X] T004 Add failing tests in `tests/test_brief.py`: `quality`, `arch` and `security` with
  `--gate --worktree tree` exit 0, the `brief written` event role is `sentinel-<role>`,
  the header cites the `sentinel-<role>` charter, and `sentinel-quality` still works.
- [X] T005 Implement the alias in `cli/wuwei/commands/brief.py` using `dispatch.ROLES`.

## Joint 5: brief body without blocking (US5)

- [X] T006 Add failing tests in `tests/test_brief.py`: `--body TEXT` and `--file PATH`
  write that body; `--file -` reads stdin; neither option exits 2 with a reason naming
  `--body` and `--file` while `sys.stdin.read` is patched to fail the test if called;
  both options together exit 2 (argparse). Switch the `brief` helper to `--file -`.
- [X] T007 Implement `--body` and `--file` in `cli/wuwei/commands/brief.py`. Update
  `tests/fakes/day.py` (`Day.brief`) and `tests/test_headless_e2e.py` (brief step) to pass
  `--file -`, and `tests/test_operator_records.py` (from main) to pass `--body`. Run green.

## Joint 3: a delta continues the same sentinel (US3)

- [X] T008 Add failing tests in `tests/test_agent_launch.py`: after a sentinel launch and a
  SubagentStop with `agent_id`, the seat records that `agent_id`; the same brief launched
  with `resume` equal to it returns 0 and the seat is running again with `head` set to the
  current measured HEAD (change the fake HEAD before continuing); `resume` with another id
  and a launch without `resume` both return 1 `brief already used`; a builder `resume`
  still follows the build record (existing test unchanged). Add a failing test in
  `tests/test_dispatch.py`: a delta receive from a seat whose brief says the old head and
  whose seat `head` is the new head is recorded; a verdict head matching neither is
  refused `verdict HEAD differs from dispatched brief`.
- [X] T009 Implement: `state.stop_seat` optional `agent_id` in `cli/wuwei/state.py`;
  `agent_launch.stop` passes it and `reserve` accepts the non-builder continuation, measures
  HEAD once per worktree brief and stores it on the seat in
  `cli/wuwei/guards/agent_launch.py`; `receive` also accepts the seat head in
  `cli/wuwei/dispatch.py`. Run green.

## Joint 4: build check satisfies the push guard (US4)

- [X] T010 Add failing tests in `tests/test_fast_checks.py` (with `workspace_case`): a build
  record awaiting checks for `repo`, `build check A` exit 0 writes `fast_checks` for that
  repository and HEAD and the push guard returns 0 for `git push origin feature`; a failing
  or unrunnable check leaves the push refused. Extend `tests/test_build.py` `setup` with a
  vcs fake (`commit_context`, `head`, `status`) so the Codex loop still records.
- [X] T011 Implement `check` in `cli/wuwei/commands/build.py` through
  `fast_checks.record`, reading per-command results from the recorded rows. Run green.

- [X] T011a Add failing tests: `tests/test_vcs_guard.py` reads the repository with `git var`
  exiting 128 (`repo_context` exit 0, `commit_context` exit 2); `tests/test_fast_checks.py`
  runs `build check` with `commit_context` failing (exit 0, push guard exit 2);
  `tests/fakes/day.py` answers `git var` with 128 so the scripted day runs as on a CI
  runner with no identity. Then add the identity-free `repo_context` port operation in
  `adapters/vcs/git.py`, `cli/wuwei/registry.py` and `tests/fakes/vcs.py`, build
  `commit_context` on it, and use it in `commit_push.context(identity=False)` (fast checks,
  build), the configured-repository match, `merge.py`, `shepherd.py` and `workspace.py`.
  `context(identity=False)` refuses settings or env overrides. Paths that commit or push
  (the guards, the git hook and the PR conflict rebase push) keep the identity read;
  `tests/test_pr_actions.py` checks that push through the real `push_check`.

## Docs and messages

- [X] T012 Update the `gate_ready` hint in `cli/wuwei/brief.py`; update
  `skills/wuwei-plan/SKILL.md`, `docs/site/reference.md`, `docs/site/concepts.md` and the
  prompt in `scripts/headless_e2e.py` (brief `--body`, no `state transition A gate`).

## Verification

- [X] T013 Run the full suite; scan changed files for em-dashes, emojis and absolute local
  paths.
