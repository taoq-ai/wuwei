Verdict: PASS
Gate: arch
Item: vendored-drift
PR: taoq-ai/wuwei
Head: 8b188da0299289caf82c973235508077c7cdeeb0
Confidence: high
Breaking: no

## Findings
- [low] tests/test_setup.py:142 blocks: no. Merge order for the open PRs is not written down. Branch protection on main has strict=false (read with `gh api repos/taoq-ai/wuwei/branches/main/protection`), so a PR does not have to be up to date with main before it merges. #1075 (ws.py, setup.py), #1076 (evidence.py, gh.py) and #1077 (guards.py, hook.py) all change cli/ and none carries a re-vendored copy. If this item merges first, any of them that merges on CI that went green before this item landed turns main red. Probe: #1075's cli/tests diff applied on top of this head fails with `.claude/ lags the tree in ['wuwei/cli/wuwei/setup.py', 'wuwei/cli/wuwei/ws.py']`. Two safe orders: merge this item last (rebase, re-vendor once, re-gate the delta), or rebase each of the three onto main after this item lands, re-vendor, and get fresh CI. Record the chosen order in the PR's review notes.
- [low] tests/test_setup.py:137 blocks: no. Excluding project-owned agents and skills is correct, because vendor() never deletes them, and it is recorded under spec.md Assumptions. One side effect: an agent or skill that is removed upstream stays behind in .claude/agents/ or .claude/skills/, and the test does not flag it. vendor() leaves it too, so this matches vendor and is out of scope ("changing vendor() itself").
- [low] tests/test_setup.py:132 blocks: no. .claude/settings.json is written by setup's settings function, not by vendor(), so it is not compared. If the hook commands in setup.py change, the committed settings can drift without a test failing. This is within the promise (vendor output only). It is a follow-up candidate.
- [low] docs/adr/0001-cut-1.2.1-before-1068.md:15 blocks: no. 2a306da is the merge commit of #1072 itself, which is the release commit, not the main commit the release was cut from (the base was 5d7157b). Suggested wording: "Release PR #1072 merged as 2a306da and cut 1.2.1." The rest of the ADR matches the record: the owner's answer is quoted, and docs/adr/ is the folder that hook.py:286 and docs/site/concepts/decisions.md name.

## Probes
- Full suite on a copy of the tree at 8b188da in the scratch directory: 292 passed. Runtime: `wc -l cli/wuwei/*.py` = 3000 (budget held, no runtime lines added).
- Contract consumers: setup.vendor() (setup.py:56) is the single producer. Its output is bin, cli, charters and .claude-plugin under .claude/wuwei/, plus .gitignore, skills/<name>, and agents/*.md. The test computes "want" by calling vendor() into a tempdir, so it never restates the file list. Hooks run "$CLAUDE_PROJECT_DIR"/.claude/wuwei/bin/wuwei (setup.py:42), so the copy is what enforces the doors here, and keeping it in step with the tree is the item's purpose.
- Mutant: drift detection reversed (extra = set()) -> test_the_drift_check_names_a_changed_vendored_file fails. Mutant: the copy's extra-files entry removed from release-please-config.json -> test_release_please_bumps_the_vendored_plugin_version_with_the_root fails. Mutant: one byte appended to .claude/wuwei/cli/wuwei/gh.py -> the real-repository drift test fails.
- Simulated release bump: "1.2.1" -> "1.2.2" applied the same way to both plugin.json files -> test_setup.py 19 passed. The two files are byte-identical before the bump, and release-please's json updater is deterministic, so they stay identical after it.
- Interplay with #1076 (head 201859c, its evidence.py diff read): release() reads extra-files from the base branch's release-please-config.json for every package and every entry, and it accepts a patch whose only changed lines are `"version": <semver>`. Once this item is on main, a release PR that bumps .claude/wuwei/.claude-plugin/plugin.json is still read as a release. Before this item merges, release-please does not touch the copy, and #1076's check is unaffected. The two are compatible in either order.
- If the 1.2.2 release PR merges before this item, the copy still says 1.2.1 while the root says 1.2.2. This branch's drift test fails on rebase until it is re-vendored, which copies 1.2.2. It is self-correcting and not silent.
- Published contracts: no CLI command, flag, exit code, config key, event or file format changes. The release-please config gains an extra file and nothing else reads it. The promise names the new rule (every PR touching cli/, charters/, agents/ or skills/ re-vendors), and the test enforces it with an assertion message that names the paths and the fix.
- Confidence is high: the suite and all mutants were run, and the #1075 merge was simulated. The only open questions are process ones (merge order), and they do not change the design.

## Residual risk
With strict=false branch protection, stale green CI on #1075, #1076 or #1077 can merge drift onto main after this item lands. The fix is a rebase plus re-vendor, and the failure message names it.
