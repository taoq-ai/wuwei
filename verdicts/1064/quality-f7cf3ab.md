Verdict: PASS
Gate: quality
Item: 1064
PR: taoq-ai/wuwei
Head: f7cf3ab6f8946b492a7f940371eaa63d7a18e245
Confidence: medium
Breaking: no

## Findings
- [low] .claude/wuwei/ blocks: no. The vendored copy (cli, charters) is a second 5k-line copy of cli/ and charters/. Nothing tests that it matches the source, so it goes stale on the next cli change until `wuwei init --cloud` is rerun. Missing test: a drift check like the one for agents/.
- [low] .claude/settings.json blocks: no. Cloud sessions run the vendored cli, not the repo's working cli/, so a change to cli/ is not exercised by the repo's own hooks until re-vendored. If the plugin is also installed locally, hooks fire twice.
- [low] AGENTS.md blocks: no. The 3-line rule is already present at df6ea05 in the branch history; the diff against origin/main is only that rule. Fine.

## Probes
- diff -rq cli/wuwei .claude/wuwei/cli/wuwei (excluding __pycache__), charters vs .claude/wuwei/charters, agents/ vs .claude/agents, skills/ vs .claude/skills: no differences, so the output is a faithful copy at this head.
- Compared hooks/hooks.json with .claude/settings.json hooks: the same events; only the command path differs (CLAUDE_PLUGIN_ROOT vs CLAUDE_PROJECT_DIR/.claude/wuwei), as setup.py writes it.
- No __pycache__ is tracked (git ls-files); the vendored .gitignore covers it.
- python3 -m pytest -q at head (pytest installed first): 264 passed. The 3000-line runtime budget test still passes, since the copy is outside cli/wuwei/. testpaths is tests only, so the copy is not collected.
- settings.json deny rules keep the ledger and force push blocked; the allow list is broad (Bash(git:*), Bash(gh:*)) but is the generated default, not hand-written.
- Mutants: no guard or validation changed in runtime code, so not run. No new behavior in the diff, so no new test is needed; the `init --cloud` path is covered by tests/test_setup.py.

Simplicity: none to delete; the committed .claude/ is the required output of init --cloud. Do not hand-trim it, since a later init would rewrite it.

## Residual risk
Staleness of the vendored copy is the only real risk and no test guards it. No standards lines existed to check.
