Verdict: PASS
Gate: security
Item: compound-doors
PR: taoq-ai/wuwei
Head: 79e74037f913350161a85dc3b857ef231821d453
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:89 blocks: no. The skip test `'=' in a` is broader than an assignment. When the program path itself contains '=', it is skipped: `env /opt/a=b/git push --force origin x` passes, while main refused it. Nobody plausibly writes a git binary under a directory with '=' in its name, and the listed residuals (eval, | sh) are easier routes, so this does not block. Matching only `re.fullmatch(r'[A-Za-z_]\w*=.*', a)`, the same rule as line 86, would close it.
- [low] SECURITY.md:35 blocks: no. Wrapper option values that name a read program (`env -C /src/git git push`, `sudo -g /x/git git push`) still pass, as on main. They are now recorded as residual.

## Probes
- `git diff 6c9b74c..79e7403`: the guards change is the line 89 skip (no '-' words, no '=' words) plus an equivalent walrus rewrite of the UNREAD return. The .claude copy is identical (diff printed SAME). SECURITY.md lists the residuals from the previous verdict.
- Full suite at a git-archive copy of 79e7403 (`/root/.local/bin/pytest -q`): 443 passed.
- s-cd/cmp2.py over the original s-cd/cmds.txt, main 2aa89fb against the head: 0 regressions out of 130. All 14 earlier regressions now refuse or ask as on main.
- s-cd/cmp2.py over the new s-cd/cmds2.txt (57 fresh wrapper and assignment shapes: `--`, `-`, `--user=`, `--kill-after=`, `-k 5 60`, `stdbuf -o L`, `xargs -a`, quoted and empty assignments, chained wrappers with assignments, PATH/HOME/VIRTUAL_ENV pointing at read programs, ledger, canary, hook and infra doors, the same shapes inside loops, ifs, braces, `!` and `bash -lc`, plus harmless controls): 1 regression, the contrived `=`-in-path case above. 16 shapes are newly caught and the harmless controls still pass.
- Reversed the new guard in fresh copies (s-cd/mut2.py). Dropping the dash skip, the '=' skip, or both was each caught by test_guards.py (1, 7 and 9 failures).
- Confidence is high: 187 commands were compared deterministically through bash(), and the one remaining difference needs a program path containing '='.

## Residual risk
The shell shapes listed in SECURITY.md stay unread by design, and so does a program path containing '='. The guards remain a deny-list for cooperating agents.
