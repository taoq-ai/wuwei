Verdict: FIX
Gate: security
Item: 1068
PR: taoq-ai/wuwei
Head: fb20e00639d09f3a2b3c7d69b21861cdde2442f9
Confidence: medium

## Findings
- [high] cli/wuwei/guards.py:68 blocks: yes. Failure: this is what remains of my 1647e2e finding 1 on the line this delta changed. The comment rule decides whether a word starts from the last emitted character. When the backslash branch (line 64) emits an escaped separator, that character is quoted text inside a word, so bash reads the following `#` as literal and runs the rest of the line. Each of these passes at fb20e00, and main 5d7157b refuses each: `echo \(#; git push --force origin x`, `echo a\ #; git push --force origin x` (escaped space), `echo \;#; gh pr merge 5 --admin`, `echo \|#; wuwei hook Stop`, `echo \&#; git push --force origin x`, and an escaped tab before `#`. The same flaw was in 4be5260 and 1647e2e, and I missed it in both rounds. Fix: in the backslash branch, emit the escaped pair as one element of out, and test the whole element (out[-1] in (' ', '\t', ';', '&', '|', '(')). An escaped character then never opens a comment. OPENER keeps out[-1][-1], which can only set the flag more often and so fails closed.
- [low] cli/wuwei/guards.py:95 blocks: no. Carried, a gap main shares: a separator stuck to a redirect or a process substitution still hides the command (`true;>/dev/null git push --force origin x`, `cat <(git push --force origin x)`). The same goes for ANSI-C `$'\''` throwing off the quote tracking. Both belong to compound-doors or a follow-up.
- [low] cli/wuwei/guards.py:243 blocks: no. Closed from 1647e2e: every RecursionError is now refused. At 600 levels, `g''it push` and `"g"it push` are refused, and so is a harmless `echo hi`, which is an acceptable fail-closed cost. The four `)#` inputs (`$(true)#`, `x=$(date)#`, `$(true)#x`, `<(true)#`) are refused. `$(# c` on its own line is still a comment, and the next line is still read.

## Probes
Suite: 377 passed at fb20e00 in a scratch copy (git archive). Runtime: 2999 lines (cat cli/wuwei/*.py | wc -l).
Parser probes: 16 inputs through guards.bash in fb20e00 and main 5d7157b copies (d3.py). That covered the `)#` set, escaped separators before `#`, ordinary comments with an apostrophe (`echo hi # it's fine`, still passes), and the 600-level nests with three innermost lines.
Mutants: two, each in a scratch copy with tests/test_guards.py run. Adding `)` back to the comment set is killed by the `$(true)#` test. Dropping the RecursionError clause is killed by the 600-level `g''it` test.
Real-shell comparison: not run. Earlier in this session a safety classifier stopped a harness that ran candidate commands in shells, so I stayed parser-only. The finding rests on the POSIX rule that `#` opens a comment only at the start of a token, where a backslash-quoted character is part of the word, and on main refusing every one of these inputs.
Why medium: the blocking finding is a direct scanner fact against main, but I did not observe bash's handling in a run.

## Residual risk
The comment rule still infers word starts from a single emitted character. Any other way of emitting a separator character inside a word would reopen this class.
