# Tasks: every read-only git subcommand is known, unknown git subcommands warn, read loops pass

**Input**: `specs/470-git-reads/` (spec.md, plan.md)

Test first: run each test task with the command given and see it fail for the expected
reason before its implementation task starts. Run from the repository root with the
interpreter your task names. No absolute local paths, emojis or em-dashes in any file.

## Phase 1: US1 and US2 core, the git tables

- [X] T001 Test, `tests/test_shell.py`: add `test_issue_470_git_kind`, parametrized over
  every member of `_GIT_READS` (expect `read`), every member of `_GIT_WRITES` that is not a
  form subcommand (expect `write`), the form cases of spec US1 scenario 4 (read and write
  forms), `[]` and `['-C', 'r']` (read), `['-c', 'alias.x=log', 'x']`,
  `['--config-env=a=B', 'log']`, `['$v', 'x']`, `['frobnicate']`, `['grep', '-Ocmd', 'x']`,
  `['grep', '--open-files-in-pager=cmd', 'x']`, `['fetch', '--upload-pack=cmd', 'o']`
  (unknown), `['-C', 'r', 'grep', '-n', 'x']`, `['branch', '-a', '-D', 'x']` (write). Also
  assert the read set and the form keys are disjoint, and that every subcommand of main's
  deploy tuple (`status diff log show rev-parse branch tag fetch checkout switch add commit
  restore reset rebase stash ls-files ls-remote remote config worktree help version
  symbolic-ref describe show-ref`, written as a literal in the test) is not `unknown`.
  Run `python -m pytest -q tests/test_shell.py -k git_kind` (fails: `git_kind` does not
  exist).
- [X] T002 Implement the tables, `UNKNOWN_GIT` and `git_kind` in `cli/wuwei/shell.py`
  (plan Design 1); delete `_git_publishes` and use `git_kind(args) != 'read'` at its one
  caller. Rerun T001 and `python -m pytest -q tests/test_shell.py`; pass.

## Phase 2: US1 and US2 in the deploy guard

- [X] T003 Test, `tests/test_deploy.py` `test_decisions` table: add
  `('git grep -n x origin/main -- a.py', 0, '')`, `('git -C repo blame -L 1,5 a.py', 0, '')`,
  `('git shortlog -sn', 0, '')`, `('git branch --list', 0, '')`,
  `('git frobnicate', 2, 'unknown git subcommand frobnicate; if it publishes')`,
  `('git grep -Ocmd x', 2, 'unknown git subcommand grep')`,
  `('git -c alias.x=log x', 2, 'unknown git command or alias')`,
  `('GIT_DIR=elsewhere git x', 2, 'unknown git command or alias')`. Keep `('git ship', 2, '')`.
  Also add the hook-level acceptance test `test_issue_470_owner_rows` to
  `tests/test_parser_warns.py`, over `POSTURES` and the five owner rows (spec US1 scenarios
  1 to 3, US3 scenarios 1 and 2; use `git -C ../widget ...` and the date of `STATE`; row 3
  parametrized over `log`, `show HEAD`, `diff`, `ls-files`, `rev-parse HEAD`,
  `fetch origin main`): every row exits 0; the loop row records exactly one
  `guard.would_refuse`, starting with `workspace guard`; the others record none. Run
  `python -m pytest -q tests/test_deploy.py -k decisions tests/test_parser_warns.py -k owner_rows`
  (fails: grep, blame, shortlog exit 2; frobnicate has the old reason; the loop row exits 2
  and stays red until T009).
- [X] T004 Implement plan Design 2 in `cli/wuwei/guards/deploy.py`. Rerun T003 and
  `python -m pytest -q tests/test_deploy.py`; pass.

## Phase 3: US2 posture, the reason levelled by its text

- [X] T005 Test, `tests/test_parser_warns.py`: add `test_issue_470_unknown_git` over
  `POSTURES` with `git -C ../widget frobnicate`: observe and guarded exit 0 with exactly one
  `guard.would_refuse` whose `payload['reason']` starts with
  `unknown git subcommand frobnicate; if it publishes` and `payload['guard'] == 'deploy'`;
  strict exits 2, `permissionDecisionReason` is that reason, no event. Run
  `python -m pytest -q tests/test_parser_warns.py -k unknown_git` (fails: exit 2 in every
  posture with the owner-only posture line).
- [X] T006 Test, `tests/test_hooks.py`: next to
  `test_posture_levels_unparsed_and_workspace_root_by_reason`, add a guarded-posture test
  where an installed `protect_state` guard returns `(2, UNKNOWN_GIT + 'x; run y')`: still
  refused with `posture: records = block (floor; no setting lowers it)`. Run it (passes
  today; it pins the deploy-only scope before T007).
- [X] T007 Implement plan Design 3 in `cli/wuwei/commands/hook.py` `posture`. Rerun T005
  and T006 and `python -m pytest -q tests/test_hooks.py tests/test_posture.py`; pass.

## Phase 4: US3 and US4, echo is a read word and piped text stays written

- [X] T008 Test, `tests/test_shell.py`: add `test_issue_470_echo_and_pipes` asserting
  through `classify`/`unread`: the owner loop
  `cd .wuwei; for f in days/d/decisions/D-*.md; do echo "### $f"; cat $f; done; cat days/d/state.json`,
  `for f in a; do echo $f; done | grep x` and
  `for f in a; do cat .wuwei/days/d/state.json | python3 -m json.tool; done` are `readonly`;
  `echo 'echo x > .wuwei/days/d/state.json' | sh`,
  `for i in 1; do echo 'echo x > .wuwei/days/d/state.json'; done | sh` and
  `echo .wuwei/config.toml | bash -s` have `.wuwei` in `written`. In
  `tests/test_parser_warns.py` add the lock rows (they pass today and must keep passing):
  to `test_publish_forms_still_refuse` add `for f in a b; do git push origin $f; done` and
  `for f in a b; do git commit -m $f; done`; to `test_state_writes_still_refuse` add
  `for i in 1; do echo 'echo x > {STATE}'; done | sh`; and add
  `test_issue_470_commit_substitution` over `POSTURES` with `x=$(git commit -m y)`: exit 2
  under guarded and strict, exit 0 with one `guard.would_refuse` from `commit_push` under
  observe. Change the `CLASSIFY` row
  `echo "gh pr merge 17"` to `(True, False, False, False)`. In `tests/test_protect_state.py`
  `test_issue_349_shared_read_predicate` add `(['python3', '-m', 'json.tool'], True)`. Run
  `python -m pytest -q tests/test_shell.py -k "echo_and_pipes or classify_table" tests/test_protect_state.py -k shared_read_predicate`
  (fails: the owner loop and the echo row are not readonly; json.tool without a file is
  not a read).
- [X] T009 Implement in `cli/wuwei/shell.py`: `'echo'` in `READ_ONLY`, the `whole` pipe rule
  in `_classify`, and `len(args) < 4` for json.tool in `reads` (plan Design 1). In
  `tests/test_decision.py` change the row `'for x in D-3; do echo x; done'` to
  `'for x in D-3; do touch x; done'`. Rerun T008, then
  `python -m pytest -q tests/test_shell.py tests/test_protect_state.py tests/test_decision.py tests/test_commit_push.py tests/test_owner_actions.py tests/test_parser_warns.py`;
  pass (`echo .wuwei/config.toml | sh` in `test_reader_mentions_are_not_writes` must still
  be 2; the T003 owner loop row now passes).

## Phase 5: US5, heartbeat and doctor

- [X] T010 Test, `tests/test_heartbeat.py`: `OK` gains a sixth result `(0, '', 50)`; the
  call-shape test expects five hook calls and `payloads[4]['tool_input']['command'] ==
  heartbeat.GIT_READ`; `test_launcher_probe_outcomes` gains
  `(5, (2, 'refused', 50), 'git_read', ('failed', 'exit 2: refused'))`; the
  unmeasured-probes test includes `git_read`. `tests/test_doctor.py` line 529 expects
  `git_read` after `read_loop`. `tests/test_parser_warns.py`
  `test_heartbeat_read_loop_exits_zero` is parametrized over `READ_LOOP` and `GIT_READ`.
  Run `python -m pytest -q tests/test_heartbeat.py tests/test_doctor.py tests/test_parser_warns.py -k "heartbeat or guards or probe"`
  (fails: no `GIT_READ`, no `git_read` probe).
- [X] T011 Implement plan Design 4 in `cli/wuwei/heartbeat.py` and
  `cli/wuwei/commands/doctor.py`. Rerun T010; pass.

## Phase 6: Docs

- [X] T012 Test, `tests/test_docs.py` `test_unparsed_commands_are_documented`: add the
  phrases `unknown git subcommand` and `` `echo` ``. The existing probe-rows test
  (`tests/test_docs.py` around line 731) covers the new `git_read` row. Run
  `python -m pytest -q tests/test_docs.py` (fails: phrases and the `git_read` row missing).
- [X] T013 Implement plan Design 5 in `docs/site/security.md` and `docs/site/reference.md`.
  Rerun T012; pass.

## Phase 7: Polish

- [X] T014 Run `python -m pytest -q tests/test_reasons.py tests/test_hooks.py tests/test_stdlib.py`
  (the new reason names a next step; the #346 import-graph tests pass unedited).
- [X] T015 Run the full suite, `python -m pytest -q`; pass. Check every changed file for
  em-dashes, emojis and absolute local paths; remove any.

## Phase 8: Review fixes

- [X] T016 Test, `tests/test_parser_warns.py` `test_issue_470_run_options_and_variable_push_refuse`:
  grep `-O`/`--open-files-in-pager`, fetch `--upload-pack`, ls-remote `-u`, and
  `git -C $R push origin main` (alone and with `gh run list`) exit 2 in every posture;
  `tests/test_deploy.py` rows for `git grep -Ocmd x` and `git ls-remote -u cmd origin`;
  `tests/test_shell.py` git_kind rows for ls-remote `-u` (fails: run options warn, `-u`
  passes).
- [X] T017 Implement FR-009 (`shell.git_runs`, used by `git_kind` and `deploy.git`). Rerun
  T016; pass.
- [X] T018 Test, `tests/test_parser_warns.py` `test_issue_470_sixth_row` (owner's row and
  the short form, every posture) and `tests/test_shell.py` `test_issue_470_variable_reads`
  (fails: nonliteral guarded arguments).
- [X] T019 Implement FR-010 (`shell._variable_read`). Rerun T018 and the full suite; pass.
