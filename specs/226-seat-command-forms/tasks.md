# Tasks: Ordinary seat command forms pass the commit, deploy and PR guards

Test first: run each test task, see it fail for the stated reason, then do the
implementation task that follows it. Run tests with `python -m pytest -q <file>` from the
repository root using the interpreter the task names.

## An assignment is not a command name (US3)

- [X] T001 In `tests/test_shell.py`, replace `test_command_mentions_still_counts_substitutions` (the #205 pin) with a failing table test `test_command_mentions_skips_assignment_words` over `mentions(text, {'git', 'gh'})` (command text, default `script=False`). Not relevant (False): `x=$(pwd)`, `x=$(pwd); echo $x`, `x="$(pwd)"; echo "$x"`, `x=$y`, `X=$(pwd) make test`. Relevant (True): `x=$(pwd); $x push`, `x=$(pwd) $cmd`, `a=gi; x=$(pwd) ${a}t push`, `x=$(git rev-parse HEAD)`, `x=$(pwd) && git push`, `$DEST push`. Also assert `mentions('x=$(pwd); echo $x', {'push', 'commit'}) is False`. Fails today on every False row.
- [X] T002 In `cli/wuwei/shell.py` `mentions`, change the final command-word scan (lines 113 to 114) to skip leading `NAME=value` words at each command position and drop assignment-only words with `_ASSIGNMENT`, as in plan.md. Add the one-line comment. No other branch of `mentions` changes.

## Opaque only when the list feeds standard input (US2)

- [X] T003 Add a failing test `test_is_opaque_stdin` in `tests/test_shell.py`: `is_opaque(['python3', '-m', 'pytest', '-q'])` and `is_opaque(['python3'])` stay True; with `stdin=False` both are False; with `stdin=False`, `is_opaque(['python3', '-c', 'import os; os.system("git push")'], stdin=False)`, `is_opaque(['xargs', 'git', 'push'], stdin=False)` and `is_opaque(['node', '-e', 'run("gh pr merge 1")'], stdin=False)` stay True. Fails today with a TypeError on the unknown keyword.
- [X] T004 In `cli/wuwei/shell.py`, add `stdin=True` to `is_opaque` (line 536), extend its docstring by one sentence, and return `stdin and not has_snippet and (...)` on the last line.
- [X] T005 Add failing rows to `tests/test_deploy.py::test_decisions`: `('python3 -m pytest -q && git status', 0, '')`, `('python3 -m pytest -q; git status', 0, '')`, `('git status | python3', 2, 'python3')`, `('git show HEAD:d.py | python3', 2, 'python3')`, `('python3 < d.py && git status', 2, 'python3')`. The first two fail today with "opaque deployment command"; the refused rows fail on the missing `python3` in the message.
- [X] T006 In `cli/wuwei/guards/deploy.py` `check` (lines 273 to 278), enumerate the commands, compute `fed = bool(command.reads) or index > 0 and commands[index - 1].separator == '|'`, call `is_opaque(argv, fed)`, keep the `mentions(raw, ('git', 'gh'))` conjunct, and name the command in the message (`opaque deployment command: <argv joined by spaces>; use a plain command`).
- [X] T007 Add failing rows to `tests/test_pr_guards.py::test_bypasses_and_relevance`: `('python3 -m pytest -q && gh pr view 1', 0)` and `('gh pr view 1 | python3', 2)`, plus a separate test asserting the refusal message for `gh pr view 1 | python3` contains `PR guard` and `python3`. The first row fails today with "opaque command".
- [X] T008 In `cli/wuwei/guards/pr.py` `check` (lines 372 to 377), apply the same `enumerate` and `fed` computation, call `shell.is_opaque(command.argv, fed)`, and name the command (`opaque command: <argv>; run gh as a plain command`).
- [X] T009 Add a failing test in `tests/test_commit_push.py`: `python3 -m pytest -q && git commit -m x` returns 2 and the reason contains `python3 -m pytest -q` and still contains `git push origin HEAD:refs/heads/<branch>`. Fails today on the missing command text.
- [X] T010 In `cli/wuwei/guards/commit_push.py` `check` line 367, put the joined argv into the message as in plan.md. The condition on lines 363 to 366 does not change.

## Combined short commit options (US1)

- [X] T011 Add failing rows in `tests/test_commit_push.py`: to `test_ordinary_commit_options` add `git commit -qm "wip"`, `git commit -sm wip`, `git commit -qam wip`, `git commit -vqm wip`, `git commit -qmmsg` and `git add -A && git commit -qm wip` (all 0); to `test_bash_table` add `('git commit -qn -m x', 1)`, `('git commit -nm x', 1)`, `('git commit -qC HEAD', 2)`, `('git commit -qZ', 2)`. The ordinary rows fail today with "unsupported commit option", and the `-qn` and `-nm` rows fail today with exit 2 instead of 1; the `-qC` and `-qZ` rows already pass and pin the fail-closed paths.
- [X] T012 In `cli/wuwei/guards/commit_push.py` `commit_options` (lines 205 to 207), replace the `-a` special case with the general split for bundles whose second character is in `aenqsv`, as in plan.md.

## Substitution rows in every guard table (US3)

- [X] T013 Add rows (they fail today only where marked): `tests/test_commit_push.py::test_bash_table` gets `('x=$(pwd); echo $x', 0)` (fails today), `('cd $(git rev-parse --show-toplevel) && ls', 0)`, `('git push $(cat remote) main', 2)`, `('echo $(git push origin main)', 2)`, `('x=$(pwd); $x push', 2)`; `tests/test_deploy.py::test_decisions` gets `('x=$(pwd); echo $x', 0, '')` (fails today), `('cd $(git rev-parse --show-toplevel) && ls', 0, '')`, `('git push $(cat remote) main', 2, 'substitution')`, `('echo $(git push origin main)', 2, 'substitution')`; `tests/test_pr_guards.py::test_bypasses_and_relevance` gets `('x=$(pwd); echo $x', 0)` (fails today), `('cd $(git rev-parse --show-toplevel) && ls', 0)`, `('gh pr create $(echo x)', 2)`. With T002 in place they all pass; if any row still fails, fix it in the shared `mentions`, never in a guard.

## Not a git repository (US4)

- [X] T014 Add a failing test `test_not_a_repository_is_named` in `tests/test_vcs.py`: `install_replay(monkeypatch, 'git', [{'exit': 128, 'stderr': 'fatal: not a git repository (or any of the parent directories): .git'}])`, then `adapter().head('/repo')` returns exit 2 with `'not a git repository'` in the reason and `'git exited'` not in it. Keep `test_git_exit_is_explained` unchanged. Fails today with "git exited 128".
- [X] T015 In `adapters/vcs/git.py` `_run` (lines 176 to 177), raise `ValueError('not a git repository')` when `b'not a git repository'` is in `result.stderr`, else keep `git exited <code>`.

## The cd containment refusal names itself (US5)

- [X] T016 Add a failing test in `tests/test_protect_state.py`: from the workspace root, `check_bash` for `cd $(git rev-parse --show-toplevel) && ls` returns 2 with `workspace guard` and `cd` in the reason and without `git or gh`. Fails today on the message.
- [X] T017 In `cli/wuwei/guards/protect_state.py` `check_bash` ParseError branch (lines 301 to 310), move the `contain_cwd and cd/pushd/popd` clause into its own `if` after the others and return the message from plan.md. Decisions do not change.

## Acceptance through PreToolUse (US5)

- [X] T018 Add `tests/test_seat_command_forms.py`, in process through `wuwei.commands.hook.run` with the workspace fixture and `hook` helper pattern of `tests/test_launcher_relevance.py` (workspace with `.wuwei`, `worktrees/ITEM-1`, `fakes.integrity.seed`, empty config, `WUWEI_WORKSPACE` and `CDPATH` removed), parametrized over cwd in (workspace root, `worktrees/ITEM-1`). Exit 0: `x=$(pwd); echo $x`, `python3 -m pytest -q && git status`. Exit 2 with deny JSON: `git push $(cat remote) main` (reason contains `commit/push guard` and `deploy`), `git status | python3` (reason contains `deploy` and `python3`), `cd $(git rev-parse --show-toplevel) && ls` (reason contains `workspace guard`). One more test at the workspace root: `install_replay(monkeypatch, 'git', [<exit 128, not-a-repository stderr>] * 8)`, then `git commit -m wip` exits 2 with `commit/push guard` and `not a git repository` in the reason. Run it after T002 to T017 are in; it must pass without further code changes (if it fails, the fix belongs in the task that owns that behaviour).

## Verification

- [X] T019 Run `python -m pytest -q` from the repository root with the interpreter the task names; every test passes, including the unchanged spec 4.5 bypass rows and `tests/test_guard_mutation.py`.
- [X] T020 Scan every file changed in this feature for em-dashes, emojis and absolute local paths, and remove any.
