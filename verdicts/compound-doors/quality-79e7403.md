Verdict: PASS
Gate: quality
Item: compound-doors
PR: taoq-ai/wuwei
Head: 79e74037f913350161a85dc3b857ef231821d453
Confidence: medium
Breaking: no

## Findings
- [low] tests/test_guards.py:451 blocks: no. Note: the mutants that still survive have no concrete harm. They are `>|` dropped from the redirect operators, `argv[1:body]` widened to `argv[1:]` (`bash deploy.sh -c x` is misread as a -c body, which only hides a non-door shell call), the -c regex widened to any dash word (`bash -x deploy.sh` is misparsed in the same way), the `sed` READ entry, and `gh` and the NETWORK entries (equivalent, because `gh` is in NETWORK too). Optional tests only.
- [low] cli/wuwei/guards.py:90 blocks: no. Note: `bash -o pipefail -c '<door>'` is still not unwrapped, because the body is the first non-dash word. Main missed it too and the promise does not cover it. Record it as residual under SECURITY.md.
- [low] cli/wuwei/guards.py:87 blocks: no. Note: `tokens[i + redirect]` adds a bool to an int, which hides intent. A plain `if` would read more clearly at the same line count.

## Probes
- Ran the suite on a `git archive` copy of 79e7403 in the scratch directory: 443 passed.
- Re-ran 35 mutants against tests/test_guards.py, each in its own copy. The three earlier blocking survivors are now killed: `while` by the `while git push` case, `elif` by the `elif false; then; elif git push` case, and the SHELLS guard by `git -c a=b push --force origin x`.
- Both halves of the new first-program skip are killed. Dropping the `-` half (the `a.startswith('-')` test) fails `env -C/src/git git push --force origin x`. Dropping the `=` half fails `env GIT_SSH=/usr/bin/ssh git push --force origin x`. Removing both fails the same case. The READ entries `wuwei` and infra are now killed by the `env X=/bin/tee wuwei hook pre` and `env TOOL=/usr/bin/rm terraform apply` cases.
- The walrus in the nested-body return keeps the UNREAD behaviour. Dropping UNREAD there still fails test_an_unreadable_sh_c_body_naming_a_door_is_refused.
- Runtime lines: `cat cli/wuwei/*.py | wc -l` gives 3000, equal to origin/main (net 0), and the size test passes.
- The vendored copy matches: `diff -r -x __pycache__ cli .claude/wuwei/cli` is empty.
- Simplicity: none to delete. The walrus saves a line but is acceptable, and the `-`/`=` skip is needed for the pinned cases.

## Residual risk
- Probes cover the pinned shapes only. Shapes the promise leaves outside (eval, `| sh`, `bash -o opt -c`, `case` bodies) are still read by shape.
