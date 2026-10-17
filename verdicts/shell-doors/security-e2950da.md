Verdict: FIX
Gate: security
Item: shell-doors
PR: taoq-ai/wuwei#1109
Head: e2950da5161b00957693c299082f50c17259480d
Confidence: high

## Findings
- [high] cli/wuwei/guards.py:81 blocks: yes. Failure: the new fd-number strip also drops the target digit of `>&1` or `<&0` when another redirect is glued after it, because the lookbehind accepts `&`. `2>&1>F` becomes `>& > F`, and _unwrap then takes `>` as the target of `>&` and puts `F` in argv. Regression: `echo x 2>&1>.wuwei/ledger/a.jsonl` and `echo x 2>&1>>.wuwei/ledger/a.jsonl` are refused on main a7fe6d5 and pass at head; bash changed the ledger file both times. The same parse passes `2>&1>x git push origin main`, `true;2>&1>x git push origin main`, `git 2>&1>x push origin main` and `2>&1<x git push origin main`, and the stub git logged `push origin main` each time (these also pass on main). Fix: keep a digit that follows `>&` or `<&` (for example add `(?<![<>]&)` to the strip), and never take an operator token as a redirect target.
- [medium] cli/wuwei/guards.py:102 blocks: yes. Failure: `<<` is still missing from the redirect tuple, though OPS emits it, so `<<x git push origin main` and `<<-x git push origin main` make `<<` the program. Bash runs `git push origin main` (heredoc ended at EOF) and the guard passes it. This is left from last round's redirect-operator finding. Fix: add `<<` (its next token is the delimiter) and a row.
- [medium] cli/wuwei/guards.py:102 blocks: yes. Failure: mutant N10 (drop `<&` from the redirect tuple) survives every behavioural test; only the vendored drift test fails, after a re-run in a fresh copy with the full suite. Under it, `<&0 git push origin main` and `git <&0 push origin main` pass, and bash ran the push. Add one of them as a row or a test case.
- [low] cli/wuwei/guards.py:81 blocks: no. Mutant N2 (drop the lookbehind, so digits glued to a word end are stripped) also survives. It turns a false pass into a real one only where the default branch ends in a digit (`git push origin release-2>x` read as `release-`); a test with `a2>x` keeping `a2` would pin it.
- [low] blocks: no. Existing gap, on main too: a named fd, `{fd}>x git push origin main`, hides the push (bash ran it).
- [low] blocks: no. Gaps listed in SECURITY.md still pass with a real push: `"$(...)"`, backticks, `<<< "$(...)"`, coproc, eval. Existing ledger gaps (also on main): a write through a symlink, `install`, and a `python3 -c` body changed the ledger. A case variant on a case-insensitive filesystem was not run, because this filesystem is case-sensitive.

## Probes
Last round's findings at this head:
- Finding 1 (leak and infra checks skipped after `$'`) is closed. All three `$'`/`$"` curl shapes are refused by the leak check, `terraform apply $'-auto-approve'` gets `ask`, and `2>x curl ... ghp_` and `2>x terraform apply` are now caught too.
- Finding 2 (redirect operators hiding the program after them) is closed for `<`, `<>`, `>&`, `<&`, `&>>` and `<<<`, for both push and ledger shapes. It is left for `<<` and for the `2>&1>x` parse above.
- Finding 3 (mutant M9) is closed: N5 is killed by the new `>|` row.
- The `//` and `/./` ledger note is closed: `.wuwei//ledger`, `/.//`, `/./`, `///`, `ledger/.`, `"./.wuwei//ledger"`, `of=.wuwei/./ledger` and cp through `.wuwei/.//ledger` are refused, and hook.door now treats them as doors.
Real bash with stub git, gh, curl and terraform on PATH logging argv, judged by guards.pre_tool from main a7fe6d5 and head trees made with git archive. Sets: cmds1-2 (push and quoting), cmds3 and cmds5 (ledger, file state checked), cmds4 (fd numbers, leak, infra), cmds6 (everyday shapes), cmds7 (remaining bypasses). Across cmds1-3, no command refused on main passes at head.
fd forms requested: `2>&1 git push origin main`, `git 2>/dev/null push origin main`, `9>x git push`, `2>>x git push`, `10>x git push`, `git 1>x push`, `true;2>x git push` and `(2>x git push)` are all refused at head and passed on main. With `"2>x" git push`, `'2'>x` and `\2>x`, bash runs no git and the guard passes, which is correct. `x=2>y`, `a2>x`, `release-2>x` and `$((2>1))` read as bash reads them. `gh pr merge 5>x` is refused as unnamed, matching bash, which runs `gh pr merge` with no number.
False refusals: none among 19 everyday shapes, including `3>&1 1>&2 2>&3`, `echo hi 1>&2`, `git log -5>x`, `git push origin feat 2>&1>x`, `x=$(gh pr view 5 --json state 2>/dev/null)` and `ls 2>/dev/null .wuwei`.
Mutants (fresh copies; full-suite re-runs for the survivors): N1 (no fd strip), N3 (`$'` makes the command None again), N4, N5, N6 to N9, N11, N12 to N15 (LEDGER and DOOR_WORDS normalisation) are each killed by a named test. N2 and N10 survive (findings above).
Suites: main 1035 passed, 2 skipped; head 1157 passed, 2 skipped. Runtime is 2,998 lines (cat cli/wuwei/*.py | wc -l).
Route corpus: routes.json sha256 is 5cdfe52932d9e1fde0afe31196b78616aa8047a60e318ef2e381518543084755 on main and 6de2b81c018a2de25040a1bcca8687506cd1b7ba81e442b3ace0f14c12cd87de at head. The 133 main rows and the 151 rows from 67b367a are unchanged, and the route tests pass (232 on main, 259 at head).
Refusals naming another PR or repo: none (113 refusals at head). The one heuristic hit, `gh pr merge https://github.com/other/x/pull/5 -R o/r`, names the URL's own repo, which gh acts on; it is the same on main.
Confidence is high because every finding comes from a real bash run with stubs and a main/head comparison.

## Residual risk
Redirect parsing still reads tokens one at a time without a grammar: an operator token can be taken as a redirect target. Named fds, heredocs and the known gaps above stay open.
