Verdict: PASS
Gate: arch
Item: 1068
PR: taoq-ai/wuwei
Head: 1647e2e1718603eb9a2762da855bdf3d452701e8
Confidence: high
Breaking: no

## Findings
- [low] cli/wuwei/guards.py:68 blocks: no. Closed: my arch-4be5260 finding. `OPENER` now covers `=(`, `+=(` and the extglob groups, and it reads across a backslash-newline. At this head, real bash and `pre_tool` agree on all four inputs: `a=( [1<<EOF ]=x )`, `a+=( ... )`, `declare -A m=( [k<<EOF ]=v )` and `@(a<<EOF )` are all refused. The cost (`a=(1 2)` and `[[` stop later body dropping) is recorded under the spec's Assumptions.
- [low] cli/wuwei/guards.py:68 blocks: no. New fail-closed cost, recorded in the spec ("After an opener no comment is skipped") but not as a refusal case. A comment that holds an apostrophe after an opener makes the command unreadable, so `echo $((1)) # don't\ngit push origin feature` is now refused, while main and 4be5260 let it through. This matches design.md section 7 ("a door that cannot read its evidence stays shut"), the refusal names the way out, and a narrower rule that skips `#` only outside `${...}` would need the pairing the item rejects. A note for the PR review notes.
- [low] cli/wuwei/guards.py:95 blocks: no. Existing gaps, the same on main 5d7157b and not regressions: a separator glued to a redirect (`echo a;>out git push --force origin x`, `true&&>o ...`, `true|>o ...`) and process substitution (`cat <(git push --force origin x)`, `echo >(...)`) hide a push that bash runs. So does `$'\''`, as in my previous verdict. These belong with compound-doors or a follow-up item.
- [low] cli/wuwei/guards.py:119 blocks: no. The `_default` refactor behaves the same: both callers pass a string (`origin(cwd)` and `_repo_number(...)[0]`), and the conditional is evaluated before any gh call.

## Probes
- Suite in a scratch copy at 1647e2e (`git archive | tar`): 366 passed. Runtime `cat cli/wuwei/*.py | wc -l` = 2999.
- Contracts since arch-4be5260. `git diff --stat 4be5260 1647e2e` touches only guards.py, specs and tests/test_guards.py. hook.py, the hook JSON and the ledger kinds are unchanged. `deny()` keeps its shape, and the force-push, ledger and merge texts are byte-identical. The only text change is the unreadable-command reason, which now adds "or give a heredoc that follows an expansion, an array or (( its own Bash call". That text exists only on this branch, so no published contract changes. CONTROL was a module constant that `git grep CONTROL` at the head shows nothing else imported.
- Design fit. The flag stays one way (set at an opener, on a missing body or on an expanding body), and no branch clears it, so every addition this round can only read more lines as commands. Separating more tokens only yields more segments to check. This is still the simplest honest shape, versus a stack.
- Real bash 5.2.21 with logging stand-ins (probes/probe.py, probe2.py, pt.py), 29 inputs at head and at main. These are refused at head and run the push in bash: the four from my finding, `a\` newline `[1<<EOF ]=x`, `${#x}` before a push, and `(true);git push --force`. The last two get through on main. The only inputs that run the push and are not refused at head are the existing gaps listed above.
- Mutants in scratch copies, tests/test_guards.py. Old CONTROL set: 5 fail. Comments skipped after an opener: 2 fail. No flag on a missing body: 1 fails. No `\\\n` in the expanding-body check: 2 fail. RecursionError uncaught: 1 fails. Opener without `=(` and extglob: 5 fail. Opener matched on raw text instead of emitted text: 5 fail. All killed.
- Confidence high: every closed finding was re-run against real bash and `pre_tool`, and every new guard has a killed mutant. It would drop if another bash context that reads `<<` as text turned up before any opener.

## Residual risk
The scanner is still a heuristic model of sh. Separator-plus-redirect tokens, process substitution and ANSI-C quoting stay unmodelled, as on main, and fit SECURITY.md's cooperative scope.
