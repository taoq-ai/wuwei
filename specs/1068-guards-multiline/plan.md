# Implementation plan: 1068 guards multi-line

## Technical context

Python 3.11+ stdlib, `cli/wuwei/guards.py` and one line of `cli/wuwei/hook.py`. Tests in
`tests/test_guards.py` and `tests/test_hook.py` through `guards.pre_tool` and `hook.handle`.

## Constitution check

- I. Stdlib only: `re` and `shlex`. PASS.
- III. A door that cannot read its evidence stays shut: an unreadable command naming a door is refused. PASS.
- V. Test first: the new tests ran red on main 7f8a0d7 (10 failed), then green. PASS.
- VI. Budget: runtime at 3,000 lines; freed in guards.py (`_git` helper, one ledger check, shorter
  `_default`, `once`, `leak`, walrus returns in `bash()`) and hook.py (one blank line, an inlined variable, a rewrapped record). PASS.

## Design

1. `_lines(command)` scans once, tracking single and double quotes. Outside quotes it drops a
   backslash-newline, skips a comment, turns a newline into ` ; `, and replaces each heredoc with
   `<< '<body>'` once its delimiter line is found. An unterminated heredoc, or an unquoted one whose
   body holds `$(` or a backtick, is left to be read as commands.
   Bodies on one line are read in order; the first that cannot be dropped stops the dropping for
   that line. A `<<` with an open `((` before it is not a heredoc.
2. `segments()` lexes `_lines(command)` and lets `ValueError` propagate. `_unwrap()` collects `<<`
   bodies and reads them as commands when the program is a shell.
3. `bash()` catches `ValueError` and refuses when `DOORS` matches the raw text.

## Rollback

Revert the merge commit. No state, config or schema changes.
