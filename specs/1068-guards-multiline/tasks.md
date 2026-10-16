# Tasks: 1068 guards multi-line

- [x] T001 Write failing tests in tests/test_guards.py for each acceptance scenario and edge case; run red.
- [x] T002 Write a failing-guard test in tests/test_hook.py: an unreadable command after it ran records no hook error.
- [x] T003 Add `_lines()` and the heredoc handling in `segments()` and `_unwrap()`.
- [x] T004 Refuse an unreadable command naming a door in `bash()`; update the module docstring.
- [x] T005 Read `gh pr create` in the PostToolUse hook from the raw command.
- [x] T006 Free lines in guards.py and hook.py until the runtime is at 3,000 lines.
- [x] T008 Fix round 1: read heredoc bodies in order, no heredoc inside `((`, tests for the four guards the gates reversed, refusal names `git commit -F`.
- [x] T009 Fix round 2: track the `((` depth in the `_lines` loop; tests for quoted and commented `))`, a `<<-` body kept as data, and a nested `$(...)`.
- [x] T010 Redesign: merge origin/main 5d7157b; replace the depth counter with a one-way flag at `((`, `${` or a joined `[`; refusing tests for the seven gate inputs and the pinned cost; passing tests for quoted `((`, a `case` pattern, `[ -f x ]` and the python edit script that quotes the hook command.
- [x] T011 Redesign fix round 1: openers `=(` and extglob read across continuations, separator tokens of `();|&` and backticks, unquoted bodies with a backslash-newline kept, comments only before an opener, `RecursionError` refused, linear scan after a missing body, `<<<` test, refusal names its own Bash call.
- [x] T007 Run `python3 -m pytest -q` and `bin/wuwei agents check` from the worktree root.
