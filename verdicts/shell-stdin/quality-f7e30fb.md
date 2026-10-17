Verdict: PASS
Gate: quality
Item: shell-stdin
PR: taoq-ai/wuwei#1115
Head: f7e30fbfd02531e999589f7cf383310cabb8579d
Confidence: medium
Breaking: no

## Findings
- [low] blocks: no. The first-character rule of the named-fd pattern is untested at its edges. Reversing `[A-Za-z_]` to `\w+` (a name that starts with a digit, `{1a}>x`) or to `[^}]*` (`{a-b}>x`) leaves the suite green. Bash does not read either spelling as a redirect, so the reversed guard would only over-read and refuse a command bash cannot run. I found no input that lets a hole through. Missing test: a negative row such as `{1a}>x git push origin main` and `{a-b}>x ...`, asserting the guard leaves the word in place. I did not run a differential probe, so I call these untested, not equivalent.

## Probes
- Suite at the head, run from a git archive copy: 1237 passed, 2 skipped (`pytest -q`).
- Red on main: the head tests/test_guards.py run against the 86135fa tree gives 18 failed, 830 passed. The failures are the new named-fd, stdin-shell and leak/infra tests.
- Named-fd mutants (run in fresh copies, `pytest -x tests/test_guards.py`):
  - dropping the `{name}` alternative: killed by test_a_push_after_a_named_fd_redirect_meets_the_push_door[{fd}>x ...].
  - first-char `in '{0123456789'` changed to `.isdigit()`: killed by the same test.
  - first-char changed to `in '{'`: killed by test_a_push_after_any_redirect_meets_the_push_door[2>&1 ...].
  - unclosed `{name`: killed.
  - `\w+` name: SURVIVED (see the finding).
  - `[^}]*` name: SURVIVED (see the finding).
- SHELLS UNREAD marker mutants (all killed):
  - dropping the `argv and` check: killed by test_a_pr_reference_does_not_hide_the_rest_of_the_command.
  - marker added for every argv: killed by test_ordinary_work_passes.
  - marker removed: killed by the stdin-shell refusal test.
  - `Path(...).name` changed to `argv[0]`: killed by the `/bin/bash < x` row.
  - SHELLS is `{'sh','bash','zsh','dash'}`. The `-c` exception is the unchanged earlier return. The `bash -o pipefail -c "git push origin main"` row covers a body behind flags.
- Real execution test (stub git on PATH under real bash) covers 2 named-fd and 4 stdin shapes. It ran, and it is not skipped here because bash is present.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` gives 2976 at the head and 2976 at main, so +0 within the budget of +2. This matches the 2,976 in the spec and tasks.
- Vendored copy: `cmp cli/wuwei/guards.py .claude/wuwei/cli/wuwei/guards.py` is identical.
- Readability of the two changed lines: dense but in the file's existing one-line regex style. The inline comments name the intent (the `{fd}` of `{fd}>x`; commands come from stdin or a file).
- docs/design.md names the new unreadable shape and `{fd}>x`. docs/site/concepts/doors.md has no list of unreadable shapes, so it needs no change. No routes.json change, and the spec states why.
- Emojis and em dashes: none in the added lines (grep over `git diff 86135fa f7e30fb`).
- Spec completeness: spec, plan, tasks, analysis and checklist are present. spec.md has "How this fails", Requirements, Breaking and Assumptions. I did not rerun the builder's generated probe; its 0 holes is the builder's claim in tasks.md T014 (unmeasured by me).
- Simplicity: none. Both changes are minimal (one regex alternative and one conditional on the existing return). The unread marker is fail-closed handling and not deletable.

## Residual risk
`bash script.sh && git push ...` is now refused by design, which is a false refusal; the spec records it. Script-file contents stay outside the guard.
