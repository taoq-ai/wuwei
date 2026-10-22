Verdict: PASS
Gate: quality
Item: door-words-text
PR: taoq-ai/wuwei#1245
Head: 01587bfd60a8e9455737387e8df0c3cc949c9d8d
Confidence: medium

## Findings
- [low] cli/wuwei/guards.py:366 blocks: no. The found list is not length-bounded for the `.wuwei` group: its pattern `\.wuwei[/.]*(...)` has an unbounded run, so a command holding `.wuwei` + 1,000,000 slashes + `ledger` (or 1,000,000 dots) makes a 1,000,305-byte refusal reason (main: 252 bytes). The other groups stay under 340 bytes (whitespace is collapsed, and each group is listed at most once). The reason only echoes back text the caller already sent, so this is a note; capping each word, for example `[:40]`, would bound it.
- [low] tests/test_guards.py:502 blocks: no. Mutant "list only found[0]" (`{found[0]}` for `", ".join(found)`) survives: no test has a command matching two door-word groups, so the joined list is untested. Add one case such as `git push` plus `gh pr` expecting `found: git push, gh pr`.

## Probes
- Fail-open or closed: the walrus list is built inside the `if` and only after the multi-line or unreadable test is true. `found` is non-empty exactly when `any(all(...))` was true, so the condition is unchanged. Inside the list, `re.search(w, command)[0]` runs only for groups where every word matched, so it cannot be None and cannot raise. `re.sub` on a str cannot raise. The decision cannot change.
- Route corpus differential at main 470ab635 against head 01587bfd, 288 routes (`tests/fixtures/routes.json`, sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 at both): 0 verdict moves, 3 reason moves, all the multi-line or unreadable refusal text gaining `found: git push`: `git push origin $'main'`, `git push origin $"main"`, `>&>x git push origin main`. This confirms the builder's count. No route names a different PR or repository in its reason.
- tests/test_guards.py at both trees via a dump test that imports it: main 1952 passed, head 1959 passed (+7 new). The existing HINT tests (`its own one-line Bash call`, `--body-file`) hold.
- Length probe (1 MB commands, under `python3 -I`): `.wuwei`+slashes and `.wuwei`+dots give a 1,000,305-byte reason; 1 MB whitespace inside `wuwei hook` gives 303 bytes; 30,000 lines naming all four groups give 335 bytes. Time is about 24 s for the slash and dot shapes at both main and head (an existing cost, not added).
- Text per shape: heredoc body gives "found: gh pr"; quoted prose plus `git status` gives "found: git push" (the words are not adjacent, but both are in the text, so it is right); backslash-newline `wuwei \ hook` gives "wuwei hook"; the unreadable `echo it's && gh pr merge 5` gives "gh pr". The text says a heredoc body or quoted prose counts, and says to use the Write tool. The three one-line shapes from the issue are not refused by the multi-line rule (test passes on main as well, a regression guard).
- Mutants, one at a time, applied to both `cli/wuwei/guards.py` and `.claude/wuwei/cli/wuwei/guards.py`, run with pytest on tests/test_guards.py (door, refusal and multi-line subset): `all` to `any` in the comprehension killed by test_ordinary_multi_line_work_passes[cd /repo\nmake test\nls -la]; whitespace normalise removed killed by the `wuwei \\\n hook Stop` case; multi-line test removed killed by test_a_multi_line_command_naming_a_door_is_refused_with_the_hint; UNREAD test removed killed by test_dollar_quoting_in_a_command_naming_a_door_is_unreadable; heredoc-prose sentence removed killed by the new test; "the Write tool" changed to "Write" killed by the new test; first-found-only SURVIVED (finding above). A `''.join` mutant did not apply (pattern text differs), so it is not run.
- Runtime lines: guards.py 456 against 455 at main (+1, budget 1); runtime total 3551 of 3600. Docs and the vendored copy match (the vendored-copy test is part of the 1959 passed).
Simplicity: the walrus plus nested comprehension on one line is dense; a small helper that returns the found words would read better, but it would add lines against a 3600 budget, so nothing is deletable now.

## Residual risk
Message text only; the decision path is unchanged and the corpus shows 0 verdict moves. The unbounded `.wuwei` echo is the one open limit.
