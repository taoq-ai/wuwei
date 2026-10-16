Verdict: PASS
Gate: security
Item: free-lines-3
PR: taoq-ai/wuwei#1104
Head: 3782d17b9b882db4caf1f6bb6c9f635fcbc0728a
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:132 blocks: no. Existing limit, same on main: when git cannot run or cwd is not a repository, current_branch answers '' and a bare `git push` reads as pass (a door that depends on the branch fails open there). The push itself would fail with git missing or no repository, so no harm is reachable; recorded for a later item.
- [low] cli/wuwei/hook.py:124 blocks: no. The `or ''` fallback was dropped from the confidence regex; safe because last_text always returns a str (transcript() defaults to '' and only takes str text), noted in case last_text changes.

## Probes
- Suites: main e34586d 931 passed 2 skipped; head 3782d17 937 passed 2 skipped; routes.json unchanged, `pytest tests/test_guards.py -k route` 218 passed at head.
- Differential door probe (scratch test, real git, fake gh): every routes.json command plus 12 extra push/create/merge/ready/api probes, across 7 cwds (feature branch with github origin, default branch with ssh origin, gitlab origin, no origin, empty dir, a plain file, missing path) and with PATH emptied so git cannot run: 1834 results, byte-identical between main and head (decision, door and first 300 chars of reason).
- _git failure: origin and current_branch answer '' on non-repo, file, missing path and no-git in both trees; the doors that read them gave the same decision as main.
- Mutant: removing the except in _git fails test_origin_and_branch_answer_blank_when_git_cannot_run. Mutant: dropping `.lower()` in the confidence capture fails test_a_seat_records_its_confidence_or_null.
- Paths: ws.PLUGIN, hook.VENDORED, guards.PR_STANDARD, the session-start CLI path, the charters read and ws.version() resolve to the same files as main for cli/, the vendored .claude/wuwei/cli (VENDORED True) and a symlinked vendored copy (resolve() lands on the real tree as before). The vendored copy is byte-identical to cli/ for all six changed modules.
- No new subprocess arguments, no new input parsing, no outward call, no secret path touched; argv list form kept, timeout 5 kept.
- Confidence high: behaviour measured identical across the route corpus and failure cwds; would drop if a caller outside guards relied on the removed hook.PLUGIN/setup.PLUGIN/__main__.PLUGIN names (grep found none in cli/ or tests/).

## Residual risk
A pure move of path and subprocess code with no measured behaviour change; the existing fail-open of branch-dependent doors when git is unavailable remains as on main.
