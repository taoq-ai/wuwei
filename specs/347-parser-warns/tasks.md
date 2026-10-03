# Tasks: a command the parser cannot read warns instead of falling to the publish floor, and read-only commands are never opaque

**Input**: `specs/347-parser-warns/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, see it fail for
the stated reason, then do the implementation task that follows. Run from the repository
root with the interpreter your task names. No absolute local paths, client names, emojis
or em-dashes in any file. Never edit or remove an existing test row except the four edits
in spec A6 (T013, T019). Fixture names stay neutral.

The five shapes, used by several tasks (spec A7):

- S1 `cd .wuwei/ziran && for r in a b c; do cat $r/report.json; done`
- S2 `ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml`
- S3 `W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check`
- S4 `python3 -P -c 'import subprocess;r=subprocess.run(["git","log","-1"]);print(open("config.toml").read())'`
- S5 `mkdir -p ../scratch && cd ../scratch && ls`

## Phase 1: acceptance through the hook (red)

- [X] T001 [US1] [US2] Test, new `tests/test_parser_warns.py`: a `workspace` fixture (seeded
  integrity as in `tests/test_seat_command_forms.py`, no `WUWEI_WORKSPACE`, no `CDPATH`),
  a `hook(cwd, command, ...)` helper running `wuwei.commands.hook.run` in process, and an
  `events(root, kind)` reader. `test_five_shapes`, parametrized over S1..S5 and
  `observe`, `guarded`, `strict` (written as `[security]\nposture = "<name>"\n`), asserting
  the spec US1 table: S2 exit 0 and no event; S1 and S5 exit 0 and one
  `guard.would_refuse` whose `reason` starts with `workspace guard`; S3 and S4 exit 0 and
  one `guard.would_refuse` whose `reason` starts with `unparsed` under observe and guarded,
  and exit 2 with `permissionDecisionReason == shell.UNPARSED` and no event under strict.
  `test_publish_forms_still_refuse` over the three postures and
  `for r in a b; do git -C $r push origin main; done`, `x=$(git push origin main)`,
  `G=git; $G push origin main`: exit 2 and `deploy` in the reason.
  `test_state_writes_still_refuse` over the three postures and the six forms of spec
  US2-2 (state path `.wuwei/days/2026-10-03/state.json`): exit 2. Run
  `python -m pytest -q tests/test_parser_warns.py`: the shapes fail (import of `UNPARSED`
  fails first; with a temporary constant they fail on exit 2 and floor lines); the
  still-refuse tests pass and pin behaviour the fix must keep.

## Phase 2: the shared classification (FR-001, FR-002)

- [X] T002 [US3] Test, `tests/test_shell.py`: `test_classify_table`, parametrized over the
  forms listed in plan.md Tests with expected `(readonly, publishes, inline,
  written_names_state)`; include S1..S5 (S1 and S2 readonly; S3 and S5 neither readonly
  nor publishing; S4 inline and not publishing), the US2 forms (publishing, or writing
  text that names `.wuwei`), and the edge rows (`echo "unterminated` publishes;
  `git show HEAD:d.py | python3` publishes; `grep -n "git push" notes.md` readonly;
  `echo "gh pr merge 17"` publishes; `cat cmds.txt | xargs git` publishes). Add
  `test_unread_table`: S2 gives `(0, '')`, S3 and S4 give `(2, UNPARSED)`, the push loop and
  `python3 -m pytest -q && git status` give `None`. Run
  `python -m pytest -q tests/test_shell.py -k "classify or unread"`: fails, no `classify`.
- [X] T003 [US3] Implement plan change 1 in `cli/wuwei/shell.py` (`_SNIPPET` shared with
  `is_opaque`, `WORKSPACE_ROOT`, `UNPARSED`, `READ_ONLY`, `PUBLISHERS`, `Shape`, `_cut`,
  `_simple`, `_git_publishes`, `_names_publisher`, `classify`, `_classify`, `unread`, the
  `ponytail:` comment). Rerun T002; passes. Run `python -m pytest -q tests/test_shell.py`;
  every existing row green.

## Phase 3: the publish guards consult it (FR-003)

- [X] T004 [P] [US3] Test, `tests/test_commit_push.py`: rows asserting `check` returns
  `(0, '')` for S2 and `(2, UNPARSED)` for S3 and S4 with the workspace as cwd, and keeps
  its refusal for `for r in a b; do git -C $r push origin main; done`. Run
  `python -m pytest -q tests/test_commit_push.py`: the S2 row fails ("opaque interpreter
  command: ls"), S3 and S4 fail on the reason.
- [X] T005 [US3] Implement plan change 3 in `cli/wuwei/guards/commit_push.py`. Rerun T004;
  passes, existing rows green.
- [X] T006 [P] [US3] Test, `tests/test_deploy.py`: rows in the `test_decisions` table (or a
  new small table using its helper): S3 and S4 give exit 2 with `unparsed` in the reason;
  `for r in a b; do cat $r/x; done; git -C repo log -1` gives exit 2 with `unparsed` (a git
  read is not a read-only word); `for r in a b; do cat $r/x; done | grep kubectl` (relevant
  through the data word, every command read-only) gives 0; the push loop keeps
  `control flow`; `G=git; $G push origin main` keeps exit 2. Run
  `python -m pytest -q tests/test_deploy.py`: the S3, S4 and read-only rows fail.
- [X] T007 [US3] Implement plan change 4 in `cli/wuwei/guards/deploy.py`. Rerun T006;
  passes, including the existing `git status | python3` and `python3 < d.py && git status`
  rows (exit 2, `python3`).
- [X] T008 [P] [US3] Test, `tests/test_pr_guards.py`: rows in
  `test_bypasses_and_relevance`: S3 gives 2 with `unparsed`; `x=$(cat f); gh pr merge $x`
  keeps 2 with its parse reason; `for r in a b; do gh -R $r issue list; done` keeps 0. Run
  `python -m pytest -q tests/test_pr_guards.py`: the S3 row fails on the reason.
- [X] T009 [US3] Implement plan change 5 in `cli/wuwei/guards/pr.py`. Rerun T008; passes.

## Phase 4: the records guards and the cd rule (FR-004, FR-005, FR-006)

- [X] T010 [P] [US1] [US2] Test, `tests/test_protect_state.py`: rows for `check_bash` with
  the workspace as cwd: `for r in a b; do cat .wuwei/$r/report.json; done` gives `(0, '')`;
  S3 gives `(2, UNPARSED)`; S1 and S5 give their current codes with reason
  `WORKSPACE_ROOT`; `cd ..` gives `(1, WORKSPACE_ROOT)`; `pushd` (directory stack) gives
  `(2, WORKSPACE_ROOT)`; every state-write form of spec US2-2 gives a nonzero code with a
  reason other than `UNPARSED`; `W=$(cat .wuwei/executable); $W drafts approve x` keeps 2.
  Run `python -m pytest -q tests/test_protect_state.py tests/test_owner_actions.py`: the
  new rows fail.
- [X] T011 [US1] [US2] Implement plan change 6 in `cli/wuwei/guards/protect_state.py`.
  Rerun T010; passes, with `tests/test_owner_actions.py` and
  `tests/test_records_after_dryrun4.py` green.
- [X] T012 [P] [US1] Test, `tests/test_decision.py`: `check_write` for a Bash call, inside a
  workspace, of S4 with `days/x/decisions/D-1.md` read in the snippet returns
  `(2, UNPARSED)`; `for f in days/x/decisions/D-*.md; do cat $f; done` returns `(0, '')`;
  `for f in a; do echo x > days/x/decisions/D-1.md; done` keeps
  `could not inspect decision record`; a parsed `python3 -c '<code naming D-1.md>'`
  result includes `UNPARSED` and still lints the day's records. Run
  `python -m pytest -q tests/test_decision.py`: the new rows fail.
- [X] T013 [US1] Implement plan change 7 in `cli/wuwei/guards/decision.py`. Rerun T012;
  passes.

## Phase 5: the hook decides the two reasons (FR-007)

- [X] T014 [US1] [US2] Test, `tests/test_hooks.py` (stub guards as its posture tests do):
  under observe and guarded a stub returning `(2, UNPARSED)` is recorded once as
  `guard.would_refuse` (two stubs returning it still give one event) and the hook exits 0;
  under strict it exits 2 and the deny reason is exactly `UNPARSED` (no posture line); a
  stub under `protect_state` returning `(1, WORKSPACE_ROOT)` is recorded and exits 0 under
  all three postures; a stub under `protect_state` returning `(1, 'kept')` still blocks
  with the records floor line. Run `python -m pytest -q tests/test_hooks.py -k posture`:
  the new tests fail.
- [X] T015 [US1] Implement plan change 2 in `cli/wuwei/commands/hook.py`. Rerun T014;
  passes.
- [X] T016 [US1] [US2] Rerun T001: `python -m pytest -q tests/test_parser_warns.py`; all
  pass.
- [X] T017 [US1] Update the two hook-level rows the cd rule changes (spec A6):
  `tests/test_protect_state.py::test_discovered_guards_through_hook` row `cd ..` from 2 to
  0, and `tests/test_seat_command_forms.py::test_seat_command_forms` row
  `cd $(git rev-parse --show-toplevel) && ls` from `2, ('workspace guard',)` to `0, ()`.
  Run both files; green.

## Phase 6: the heartbeat probe and doctor row (FR-008)

- [X] T018 [US1] Test, `tests/test_parser_warns.py`: `test_heartbeat_read_loop_exits_zero`,
  parametrized over the three postures: a PreToolUse payload with session
  `wuwei.commands.hook.HEARTBEAT_SESSION`, cwd `<workspace>/.wuwei`, command
  `wuwei.heartbeat.READ_LOOP` exits 0 with no output. Run it: fails (no `READ_LOOP`; with
  the literal command it exits 2 on main's records floor).
- [X] T019 [US1] Test, `tests/test_heartbeat.py` and `tests/test_doctor.py`: `OK` gains a
  fifth result `(0, '', 50)`; the calls assertion expects four hook calls and the fifth
  payload's command equals `READ_LOOP`; the adapter-failure test lists `read_loop` among
  the unmeasured names; a launcher-outcome row `(4, (2, 'refused', 50), 'read_loop',
  ('failed', 'exit 2: refused'))`; the doctor guards names include `read_loop` after
  `state_write`. Run both files: fail.
- [X] T020 [US1] Implement plan change 8 in `cli/wuwei/heartbeat.py` and
  `cli/wuwei/commands/doctor.py`. Rerun T018 and T019; pass.

## Phase 7: docs and regression

- [X] T021 Test, `tests/test_docs.py`: the heartbeat test already requires every probe in
  `docs/site/reference.md`; add an assertion that `docs/site/security.md` mentions
  `unparsed` and the subshell form. Run: fails.
- [X] T022 Implement plan change 9 in `docs/site/reference.md` and
  `docs/site/security.md`. Rerun T021; passes.
- [X] T023 Run `python -m pytest -q tests/test_shell.py tests/test_deploy.py
  tests/test_commit_push.py tests/test_pr_guards.py tests/test_protect_state.py
  tests/test_owner_actions.py tests/test_decision.py tests/test_seat_command_forms.py
  tests/test_guard_mutation.py tests/test_scope_first.py tests/test_profiles.py
  tests/test_hooks.py tests/test_posture.py tests/test_shadow.py`; all pass, and `git diff`
  on existing test files shows additions only apart from the edits in T017 and T019.
- [X] T024 Run the full suite, `python -m pytest -q`; everything passes, including the
  hook budget tests. Check every changed file for em-dashes, emojis and absolute local
  paths and remove any.
