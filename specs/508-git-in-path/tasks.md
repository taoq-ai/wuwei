# Tasks: 508-git-in-path

- [X] T001 Test: hook probes (launcher `state get`, `pytest`, `ls`) from a temporary path containing `git` and `gh` exit 0 under every posture, and `git push origin main` there is refused (tests/test_parser_warns.py)
- [X] T002 Implement: a whole-word `_GUARDED` pattern in cli/wuwei/shell.py that ignores a name used as a directory component; `mentions()` keeps its original pattern (review F1)
- [X] T003 Run the focused files and the full suite from this worktree (its path contains `git`)
- [X] T004 Review F1: limit the directory-component lookahead to path-segment characters so a redirect glued to `git` or `gh` (`git</dev/null push`, `gh</dev/null pr merge --admin`) is still a mention; pin it in tests/test_shell.py and tests/test_parser_warns.py
