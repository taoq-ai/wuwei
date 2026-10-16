Verdict: PASS
Gate: goal
Item: compound-doors
PR: taoq-ai/wuwei
Head: 6c9b74cb5e2bb7e241182bf53362e771bc063f27
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:88 blocks: no. The first-program rule stops at an option argument that itself names a read program: 'sudo -u git git push --force origin x' and 'env -u git gh pr merge 5' still pass on the head (they passed on main too, so nothing regresses). This follows the promise's rule word for word, but SECURITY.md's residual list does not name it. Add one line there, or skip the argument of known option flags (-u, -n).
- [low] cli/wuwei/guards.py:88 blocks: no. Reading too far, as the spec's own assumption predicts: 'time echo gh pr merge 5', 'xargs printf git push origin main' and 'nohup echo git push --force origin x' are now refused. The real-use replay found 0 such commands in 488 calls, so the assumption holds for now.
- [low] cli/wuwei/guards.py:86 blocks: no. Shapes outside the reserved-word list still hide a door: 'coproc git push --force', 'builtin command git push --force', and a function body (the function body is already listed as residual). 'case' and 'select' bodies happen to be read. Note these for SECURITY.md.
- [low] SECURITY.md:36 blocks: no. Also corrects the stale runtime cap (2,500 to 3,000 lines), matching AGENTS.md and the size test. No requirement asked for this. It is a harmless factual fix.

## Probes
- Traced goal G-2 (fix bugs found in real use before features), then the promise, the spec FRs 001-006, and the diff to cli/wuwei/guards.py. Each promise clause maps to a line: the reserved words at guards.py:86, the wrapper first-program rule at :88 with READ at :21, the combined -c flags at :89-90, and timeout and stdbuf added to WRAPPERS.
- The builder's explain-back (spec.md "The promise in my words") matches the item. It goes past the promise in two places, both recorded under Clarifications: READ also covers the network tools, file writers, sed and python, to keep main's ledger and leak reads after a wrapper; and the UNREAD marker. Neither is drift against the goal.
- Ran a scratch copy of the head with /root/.local/bin/pytest -q: 431 passed. Main: 397 passed. wc -l cli/wuwei/*.py gives 3000 on both, so the size acceptance holds and the net-zero line promise holds (guards.py +23/-23).
- Copied the head's tests/test_guards.py onto main's code: 24 failures, covering every acceptance case for loops, ifs, braces, '!', 'bash -lc', 'sh -ec' and the wrappers. So the new tests do detect the gap that main has.
- probes.py ran every acceptance command through guards.pre_tool on both trees. Main passed all of the door commands. The head refuses each one with the matching door's reason (merge without a PR number, force push, PR not ready). 'for f in *.md; do wc -l $f; done' and 'if [ -f x ]; then echo ok; fi' pass on both.
- Real-use replay: extract.py pulled 488 Bash commands (478 unique) from all 27 transcripts under /root/.claude/projects/. replay.py ran each through guards.pre_tool on origin/main (2aa89fb) and on the head, with gh stubbed offline. compare.py: 0 changed decisions and 57 denies on each side, all from the existing multi-line rule. Among the 372 one-line commands, the head reads 19 loops or ifs, 3 shell -c calls and 6 wrapped commands, with 0 refusals. So the replay shows no new false refusals.
- Residual list: SECURITY.md:23-34 records everything the promise's Outside clause names (eval, pipes or here-strings into a shell, a variable as the program, $(...) inside double quotes), plus more.
- Confidence high: the acceptance scenarios pass on the head and fail on main, and the replay shows zero changed decisions. A larger or different transcript population that prints commands through a wrapper would lower it.

## Residual risk
The guards remain a deny-list over shlex tokens, and wrappers or keywords outside the lists (setsid, coproc, builtin, bash -o) still hide a door. The code host's protected refs stay the hard boundary.
