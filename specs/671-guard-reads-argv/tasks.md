# Tasks: the git and gh guard reads the executed command, not prose

Test first: each test task runs and fails for the expected reason before its implementation
task. Use the existing fixtures: `tests/test_commit_push.py` (`workspace_case`, `payload`),
`tests/test_pr_guards.py` (`case`, `payload`), `tests/test_parser_warns.py` (`workspace`,
`configure`, `hook`, `events`). Neutral names and paths; no test reaches git or the network.
Write a line continuation in a test as `'gi\\\nt push'`. Run the touched files, then the full
suite with `python -m pytest -q`.

## Phase 1: a line continuation cannot hide the program name (FR-001; US2.3)

- [X] T001 Test in `tests/test_shell.py`: `mentions('gi\\\nt push', {'git'})`,
  `mentions('g\\\nh pr merge 5', {'gh'})` and `mentions('sh -c "g\\\nit push"', {'git'})`
  are true; `mentions('echo hi', {'git'})` stays false. Fails today (false).
- [X] T002 Implement in `cli/wuwei/shell.py` `mentions` (line 99): remove `\\\n` with the
  quotes and backslashes before matching.

## Phase 2: a reader's text is data in an all-reader call (FR-002, FR-007; US1)

- [X] T003 Tests in `tests/test_shell.py`, new `test_reader_text_is_data`, parametrized,
  each `normalize(script)` returning the listed argv:
  `"cat > brief.md <<'EOF'\nThe shepherd falls back to gh.\nRaise the PR with gh pr create; then git push.\nEOF"`
  (`[['cat']]`, writes `('brief.md',)`), `"echo 'falls back to gh' > notes.md"`,
  `'grep -rn "gh pr" docs | head -20'`, `'echo "git push"'`,
  `"git status; cat <<'EOF'\ngit push\nEOF"`, `"cat <<'EOF' | git status\ngit push\nEOF"`,
  `"cat <<'EOF'\n$(git push -f)\nEOF\ngit status"`. Fails today (`ParseError`).
- [X] T004 Tests in `tests/test_shell.py`, new `test_reader_text_that_can_run_fails_closed`,
  each raising `ParseError` (passes today; it pins the per-call rule):
  `"echo 'git push' | sh"`, `"echo 'import os; os.system(\"git push\")' | python3"`,
  `'echo "gh pr merge 5" | xargs -I@ sh -c @'`, `"cat <<'EOF' | python3\ngit push\nEOF"`,
  `"cat <<'EOF' | tee out\ngit push\nEOF"`, `"mkdir -p d && echo 'git push' > d/x"`,
  `"printf 'git push' > x"`.
- [X] T005 Update `tests/test_shell.py` cases this issue flips on purpose (run them first to
  see each fail against T006's code, then move them):
  - `test_unaccounted_guarded_mentions_fail_closed`: drop `'git status; echo "git push"'`,
    `"cat <<'EOF'\n$(git push -f)\nEOF\ngit status"`,
    `'cat <<"EOF"\ngit push -f\nEOF\ngit status'` and `'echo "git push"'` (now in T003);
    remove the "Intentional false positive" comment.
  - `test_opaque_interpreter`: the `echo 'python -c git push'` case is data now; expect it
    to parse to `[['echo', 'python -c git push']]` (keep `is_opaque` false for it).
  - `test_other_commands_cannot_borrow_guarded_heredoc_exemption`: replace `cat` with
    `python3` in each case so the owner rule is still pinned with a non-reader.
  - `tests/test_hooks.py::test_unaccounted_shell_mention_blocks_hook`: use
    `awk 'BEGIN {system("git push")}'` instead of `echo "git push"`.
- [X] T006 Implement in `cli/wuwei/shell.py`: thread `texts` through `normalize`, `_parse`
  and `_unwrap` (every internal call site); append reader argv and non-git here-doc bodies
  to it; reject them at the end of `normalize` when the call runs a command that is neither
  a reader (`reads(argv)`) nor in `protected` (plan, "Reader text is deferred").

## Phase 3: a quote-split name in eval or sh -c is resolved (FR-003; US2.1, US2.2, US2.4)

- [X] T007 Tests in `tests/test_shell.py`, new `test_constructed_names_resolve`,
  `normalize(script)` returning `[['git', 'push']]` for `'g""it push'`,
  `'sh -c "gi""t push"'`, `"eval 'gi''t push'"`, `'gi\\\nt push'`,
  `'sh -c "gi\'t\' push"'`, `'bash -c "g\'\\\nit\' push"'` and `"sh -c 'g\"\"it push'"`.
  Fails today for the `eval` and `sh -c` forms.
- [X] T008 Update `tests/test_shell.py`: drop `'''sh -c "gi't' push"'''` from
  `test_obfuscated_launcher_mentions_fail_closed` and
  `test_nested_script_continuation_cannot_hide_obfuscated_mention` (both now in T007);
  in `test_unwrap_cannot_discard_mentions` move `"eval 'echo git'hub"` and
  `"sh -c 'echo git'hub"` to a case asserting `[['echo', 'github']]`.
  `test_source_mentions_cannot_be_replaced_by_decoded_mentions` stays as it is (its cases
  still raise, at line 337 or on the continuation part at lines 332-334).
- [X] T009 Tests in `tests/test_commit_push.py`, new
  `test_constructed_command_is_judged_as_plain`, parametrized pairs, each asserting
  `check(payload(root, built)) == check(payload(root, plain))`:
  (`'sh -c "gi""t push"'`, `'git push'`), (`'g""it push'`, `'git push'`),
  (`"eval 'gi''t commit --no-verify -m x'"`, `'git commit --no-verify -m x'`),
  (`'sh -c "gi""t commit --no-verify -m x"'`, `'git commit --no-verify -m x'`),
  (`'sh -c "gi""t push origin HEAD:refs/heads/feature"'`,
  `'git push origin HEAD:refs/heads/feature'`) and
  (`'gi\\\nt commit --no-verify -m x'`, `'git commit --no-verify -m x'`). Fails today for
  the `eval`, `sh -c` and continuation forms (exit 2, or 0 for the continuation, where the
  plain form gets 1).
- [X] T010 Test in `tests/test_pr_guards.py`: `check(payload(root, 'g\\\nh pr merge 9
  --admin'))` returns `(1, ...admin...)` as `gh pr merge 9 --admin` does. Fails today
  (`(0, '')`); T002 alone makes it pass, keep it as the guard-level pin.
- [X] T011 Implement in `cli/wuwei/shell.py` `_unwrap`: delete the `eval` split-quote loop
  (lines 452-454) and the `sh -c` split-quote check and obfuscation raise (lines 482-485).

## Phase 4: a constructed command is named and not lowered (FR-004, FR-005, FR-006; US2.5)

- [X] T012 Tests in `tests/test_shell.py`, new `test_constructed_names_the_command`:
  `constructed(script)` is `'git push'` for `'g""it push'`, `'sh -c "gi""t push"'`,
  `'x=git; $x push'` and `'x=gi; ${x}t push'`; `'gh pr merge'` for
  `'g\\\nh pr merge 5 --admin'`; `''` for `'git push'`, `'/usr/bin/git push'`,
  `'echo "git push"'`, `'$(printf git) push'` and `'ls'`. And `unreadable('x=git; $x push')
  == ''` while `unreadable('$(printf git) push') != ''`. Fails today (no `constructed`).
- [X] T013 Implement `constructed` in `cli/wuwei/shell.py` above `unreadable`, and its first
  line in `unreadable` (plan, "constructed(command)").
- [X] T014 Tests in `tests/test_parser_warns.py`, new `test_prose_heredoc_passes` and
  `test_constructed_refusal_names_the_command`, parametrized over `POSTURES` with the `hook`
  helper:
  - `"cat > brief.md <<'EOF'\nThe shepherd falls back to gh.\nRaise the PR with gh pr create; then git push.\nEOF"`:
    exit 0 and no `guard.would_refuse` event in every posture (US1.1, US1.2; fails today
    under strict and records a warning under observe and guarded).
  - `'sh -c "gi""t push"'` and `'x=git; $x push'`: in each posture the exit equals the
    hook's exit for plain `git push` in that posture, a refusal's
    `permissionDecisionReason` ends with `resolved: git push`, and no `guard.would_refuse`
    reason starts with `opaque:`.
  - `'g\\\nh pr merge 5 --admin'`: exit 2 in every posture, reason contains `admin merge is
    refused` and ends with `resolved: gh pr merge`.
  Fails today (no `resolved:` line; the variable form is lowered to `opaque:` below strict;
  the continuation form passes).
- [X] T015 Implement in `cli/wuwei/commands/hook.py` before the PreToolUse `if reasons:`
  return (line 132): append `\nresolved: <constructed>` to `reasons[0]` for a Bash refusal.

## Phase 5: invariant, docs, suite (FR-008, FR-009)

- [X] T016 Test in `tests/test_invariants.py`: add `i41(case, rules)` (READS `()`, memoised
  with `rules.memo` like `i35`) checking at the shared spot: `normalize` returns argv for the
  T003 reader cases and raises for the T004 cases; `normalize` returns a `git` or `gh` argv
  for the T007 forms; `constructed` names the T012 variable forms and `unreadable` returns
  `''` for them. Register `'I41': i41` in `INVARIANTS` and `'I41': ()` in `READS`.
  `test_table_matches_the_checks` fails until T017.
- [X] T017 Add row I41 after I37 in `docs/specs/2026-09-24-wuwei-design.md` 9.2:
  `| I41 | A Bash call is judged by what it runs: git or gh words in the text of a call whose every command is a reader or a guarded program never refuse it; a git or gh name built by quotes, a line continuation, eval or sh -c is judged as the plain command; one built from a variable is refused naming it | normalize, constructed and unreadable on the reader, runnable-text, split-name and variable tables | #671; the guard and hook cases stay in tests/test_commit_push.py, tests/test_pr_guards.py and tests/test_parser_warns.py |`
- [X] T018 `docs/site/security.md`, after the `unparsed` paragraph's read-only sentence:
  "A git or gh word in the text a reader prints or writes to a file (`cat > brief.md
  <<'EOF'`) is text when every command of the call is a reader or git or gh; a git or gh
  name built from quotes, a line continuation, `eval` or `sh -c` is judged as the command it
  runs, and one built from a variable is refused with `resolved: <command>`."
- [X] T019 Run `python -m pytest -q` from the repository root; everything passes. Check
  every changed file for em-dashes and emojis.

## Phase 6: review fixes

- [X] T020 Review F1: `constructed` enumerates each variable once (one value per run) and
  skips the enumeration above 64 combinations, so the refusal stands and the hook stays
  inside the #346 budget. Tests in `tests/test_shell.py`: `x=gi; x=t; $x$x push` names
  nothing, and 30 `$c` positions return in under a second.
- [X] T021 Review F2: a reader's text is data only when no redirect of the call writes
  under `.git/`; `echo ... >> .git/config` and `cat > .git/hooks/pre-commit <<'EOF'` with
  git or gh text stay unparsed.
