# Tasks: The launcher and irrelevant scripts are never refused as opaque

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it.

## Script text is judged by literal tokens (US2)

- [X] T001 Add a failing table test `test_script_mentions_judges_literal_tokens` in `tests/test_shell.py`: with `script=True`, `x=$(pwd)\n` and the text of `ROOT / 'bin/wuwei'` are not relevant to `{'git', 'gh'}`; `git push --force origin main\n`, `g"i"t push`, `\git push`, and ``echo `git push` `` are relevant; `$'\x67it' push` is not. Add one row asserting the default (command text) call still answers True for `x=$(pwd)`. Fails today with a TypeError on the unknown `script` keyword.
- [X] T002 Add keyword-only `script=False` to `mentions` in `cli/wuwei/shell.py`: skip the `$'` check and return False after the literal pattern checks when `script` is True, with a `ponytail:` comment naming the constructed-name residual and its anchors (pre-push hook for pushes, branch protection for gh merges).

## The launcher is the CLI, not a script (US1)

- [X] T003 Add a failing test `test_script_path_treats_launcher_as_cli` in `tests/test_shell.py`: with `WUWEI_WORKSPACE` removed, a workspace with `.wuwei/` and `worktrees/ITEM-1`, `.wuwei/executable` naming a copy at `tmp_path / 'previous-plugin/bin/wuwei'`; from both the root and `worktrees/ITEM-1`, `script_path` returns None for `<ROOT>/bin/wuwei state get`, `sh <ROOT>/bin/wuwei state get` and `<recorded> build check ITEM-1`, and returns the path for an unrecorded copy at `tmp_path / 'other/bin/wuwei'`. A second case with the pointer file missing returns the path for the previous-plugin copy. Fails today because `script_path` returns every path.
- [X] T004 Add private `_launcher(path, cwd)` in `cli/wuwei/shell.py` and call it from `script_path` (plugin `bin/wuwei` via `Path(__file__).resolve().parents[2]`, pointer via `workspace.find_workspace` falling back to `workspace.worktree_workspace`, errors mean not known).

## The pointer the guards trust is protected (US3)

- [X] T005 Add failing rows in `tests/test_protect_state.py`: `check_file` with Write and Edit to `.wuwei/executable`, and `check_bash` with `echo x > .wuwei/executable` and `cp other .wuwei/executable`, all return exit 1. Fails today with exit 0.
- [X] T006 Add `('executable',)` to the protected `.wuwei` tails in `_protected_name` in `cli/wuwei/guards/protect_state.py`.

## Guards use script-mode relevance, acceptance through the hook (US1, US2, US3)

- [X] T007 Add the failing acceptance table `tests/test_launcher_relevance.py`, run in process through `wuwei.commands.hook.run` with event PreToolUse, parametrized over cwd in (workspace root, `worktrees/ITEM-1`). Exit 0 rows: `<ROOT>/bin/wuwei state get`, `<recorded> build check ITEM-1`, `wuwei state get`, `./sub.sh` (text `x=$(pwd)`). Refused rows (return 2, deny JSON): `./push.sh` (text `git push --force origin main`); `<ROOT>/bin/wuwei decision outcome D-1 A`, `<ROOT>/bin/wuwei drafts approve 1`, `<ROOT>/bin/wuwei mcp decide`, `<ROOT>/bin/wuwei integrity reconfirm`, each with `owner` in the reason. Fails today on the `./sub.sh` row with the three guard reasons from the dry run.
- [X] T008 Pass `script=True` to the script-text `mentions` calls in `cli/wuwei/guards/commit_push.py` (line 251), `cli/wuwei/guards/deploy.py` (line 263) and `cli/wuwei/guards/pr.py` (lines 339 to 340). No other change in those guards.

## Verification

- [X] T009 Run `python -m pytest -q` from the repository root with the interpreter the task names; every test passes, including the existing guard tables and `tests/test_guard_mutation.py`.
- [X] T010 Scan every file changed in this feature for em-dashes, emojis and absolute local paths, and remove any.
