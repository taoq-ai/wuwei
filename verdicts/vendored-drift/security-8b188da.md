Verdict: PASS
Gate: security
Item: vendored-drift
PR: taoq-ai/wuwei
Head: 8b188da0299289caf82c973235508077c7cdeeb0
Confidence: high

## Findings
- [low] tests/test_setup.py:138 blocks: no. The drift check owns wuwei/ and WUWEI's skill folders but not extra files in .claude/agents/ (by design, project agents stay), and it does not compare .claude/settings.json or file modes; a planted extra agent or a changed hook command in settings.json stays outside this test. Settings and doctor checks are outside this item's promise.
- [low] release-please-config.json:18 blocks: no. Adding .claude/wuwei/.claude-plugin/plugin.json to extra-files widens what an X-1 release PR (open #1076, reading extra-files from the base config) may touch by one file, limited there to "version": "<semver>" lines; that file has one version key and holds no executable content, so a bot release PR still cannot rewrite more than the copy's version.

## Probes
- git archive of 8b188da into a scratch tree; setup.vendor() from that tree into an empty dir; diff -r against the tree's .claude/: identical, the only extra file is .claude/settings.json, unchanged by this PR (git diff origin/main...8b188da -- .claude/settings.json empty).
- No new hooks, agents, skills or settings under .claude/; git ls-tree shows .claude/wuwei/bin/wuwei 100755 with the same blob as bin/wuwei; PR changes no cli/, so the vendored code equals already reviewed main code.
- Vendored plugin.json and root both say 1.2.1, matching origin/main and the manifest.
- Full suite in the scratch tree: 292 passed (/root/.local/bin/pytest).
- Mutant: appended a line to .claude/wuwei/cli/wuwei/gh.py: drift test fails naming wuwei/cli/wuwei/gh.py.
- Mutant: removed the new extra-files entry: test_release_please_bumps_the_vendored_plugin_version_with_the_root fails.
- Mutant: planted .claude/wuwei/hooks/h: drift test fails naming it; planted .claude/agents/evil.md: not flagged (the low note).
- Read #1076 diff via gh pr diff: release() allows extra-files paths with version-only line patches; the new path stays inside that.
- Confidence high: byte-for-byte verification and mutants were direct; it would drop if release-please's JSON updater were found to rewrite more than $.version.

## Residual risk
settings.json and extra project agents in .claude/ are not covered by any drift test; a future change there needs its own review.
