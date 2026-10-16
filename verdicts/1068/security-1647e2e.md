Verdict: FIX
Gate: security
Item: 1068
PR: taoq-ai/wuwei
Head: 1647e2e1718603eb9a2762da855bdf3d452701e8
Confidence: medium

## Findings
- [high] cli/wuwei/guards.py:68 blocks: yes. Failure: the comment rule treats a `#` after `)` as a comment start. When that `)` closes a `$(...)`, `<(...)` or `>(...)`, bash is still inside the same word, so the `#` is literal and the rest of the line runs. Each of these passes at head, and main 5d7157b refuses each: `echo $(true)#; git push --force origin x`, `x=$(date)#; gh pr merge 5 --admin`, `echo $(true)#x; wuwei hook Stop` and `cat <(true)#; git push --force origin x`. The rule was already there at 4be5260 and I missed it last round; the last fix rewrote this line. Fix, fail closed: drop ')' from the comment-start set. A `(true) #x` comment is then read as text, which can only add refusals.
- [medium] cli/wuwei/guards.py:244 blocks: yes. Failure: my previous finding 5 is only partly closed. On RecursionError, the scanner refuses only when DOORS matches the raw text. With 600 nested "bash <<'Ek'" levels (11 KB) and an innermost line of `g''it push --force origin x` or `"g"it push --force origin x`, bash() returns None, and bash runs the force push. At 50 levels the same line is refused, because shlex reads `g''it` as git. No real command nests hundreds of shells. Fix: refuse every RecursionError, with or without a DOORS match.
- [low] cli/wuwei/guards.py:95 blocks: no. Gap that main shares: shlex still groups a separator with a redirect or process substitution into one token that is neither a separator nor a known redirect. So `true;>/dev/null git push --force origin x`, `true|>/dev/null ...`, `true&&>/dev/null ...`, `(>/dev/null ...)`, `echo $(>/dev/null ...)`, `` echo `>/dev/null ...` `` and `cat <(git push --force origin x)` all pass on main and at head. Recommended in this item or in compound-doors: split a punctuation token into its leading separator run and the rest, and treat `<(`/`>(` as separators.
- [low] cli/wuwei/guards.py:57 blocks: no. Gap that main shares, carried from the last verdict: ANSI-C `$'\''` throws off the quote tracking (`echo $'\'' ; git push --force origin x #'`).
- [low] cli/wuwei/guards.py:57 blocks: no. Closed from my previous verdict, each probed at this head (refused here; main result in brackets):
  - backtick token grouping, `` x=`date`; ... `` [main refuses]
  - `$\<newline>(` in an unquoted body [main refuses]
  - a joined `EO\<newline>F` delimiter [main passes]
  - `a=( [1<<EOF ]=x )` and its `+=(`, `declare -a`, newline and continuation forms [main refuses]
  - `${x:- #}` [main refuses]
  - the `<<<` lookbehind test [main passes]
  - quadratic scan: 256 KB now in 0.71 s; 30000 distinct heredocs (638 KB) in 2.6 s
  - RecursionError with a plain door name

## Probes
Suite: 366 passed at 1647e2e in a scratch copy (git archive). Runtime: 2999 lines (cat cli/wuwei/*.py | wc -l).
Parser probes: 25 delta inputs, each fed to guards.segments in head and main copies. Attacks on the emitted-text opener found no gap. Tried: openers split by a continuation, an opener char after a quote char, `a+=(`, `declare -a a=(`, `a=\<newline>(`. The separator rule closes every separator-only grouping. The residual groupings mix a separator with a redirect, and main shares them.
Timing and recursion: g.bash wrapped in time.time. Nested depths 50 and 600, each with a plain, a `g''it` and a `"g"it` innermost line.
Mutants (10, each in a scratch copy, tests/test_guards.py and tests/test_hook.py): all killed. They covered the separator set, the `=(`, `${` and extglob parts of OPENER, OPENER on raw text instead of emitted text, comments inside an expansion, backslash-newline in the body check, a missing body not setting the flag (the linear-time test), RecursionError not caught, and the comment check on raw text.
Real-shell comparison: not run. Earlier in this session a safety classifier stopped a harness that ran candidate commands in shells, so this review stayed parser-only. The `$(...)#` finding rests on bash word rules (a `#` starts a comment only at the start of a word) and on main refusing these inputs. dash is unmeasured.
Why medium: both blocking findings are direct scanner facts against main or against the previous fix. Not running a real shell leaves the bash semantics cited, not observed.

## Residual risk
The comment rule decides word starts from one previous character and cannot see whether a `)` closed a comsub. Token grouping of a separator with a redirect stays open, as it is on main.
