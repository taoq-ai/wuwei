Verdict: PASS
Gate: security
Item: X-1
PR: taoq-ai/wuwei
Head: e2fb0e1d96fccb45a5adb8a8a11853971a946d7c
Confidence: medium

## Findings
- [low] cli/wuwei/evidence.py:120 blocks: no. Closed: the bare-CR smuggle (my 12f8054 high). The patch is now split on '\n' and each line must fullmatch with re.A. Bare CR, U+2028, form feed, vertical tab and NUL smuggles all keep both gaps (probed). Mutant K4 (splitlines) is killed by 3 tests, K3 (match instead of fullmatch) by 4 and K5 (no re.A) by 1.
- [low] cli/wuwei/evidence.py:47 blocks: no. Closed: a path key with a versioned file name (my 12f8054 medium). Outside the manifest the key must be "version", and the value must be strict semver. `"hooks": "1.0.0.md"` and `"name": "9.9.9"` keep both gaps (probed). Mutant K1 (key check dropped) is killed.
- [low] cli/wuwei/evidence.py:121 blocks: no. Still read as a release, all of it inert: an extra "version" line anywhere in plugin.json; new path-like keys with version values in .release-please-manifest.json, which only release-please reads; any text in CHANGELOG.md, which is docs and not in build-release.py's SHIPPED set. A patch with no +/- lines also passes, but GitHub sends None for mode-only changes. The hunk-header context text comes from git, not from the head.
- [low] cli/wuwei/evidence.py:121 blocks: no. Moving the trailing comma between version lines can leave plugin.json malformed: an availability fault, not code. test_setup.py:90 and test_guards.py:129 json.loads plugin.json, so CI fails when Tests runs. A PR that runs no checks at all reads as no CI gap (ci_gaps, pre-existing). A bot-opened release PR without RELEASE_PAT triggers no Tests (release.yml comment). An agent's added commit, though, triggers pull_request under the agent's token.
- [low] cli/wuwei/gh.py:59 blocks: no. Unmeasured: whether GitHub ever sends a partial `patch` rather than omitting it. If omitted, every gap stays (patch None probed).

## Probes
- Suite at e2fb0e1 in a scratch copy: 316 passed. Runtime: 3000 lines (wc -l cli/wuwei/*.py), at the limit.
- 22 patch variants against plugin.json and the manifest. These keep both gaps: bare CR, U+2028, \f, \x0b, \x00, NBSP indent, Arabic-Indic digit, hooks path, versioned name, trailing space, CRLF, empty patch, delete-all, '++' prefix, manifest object value. These read as a release, all inert: an extra version line, a comma drop (CI parses plugin.json), context-only, a hunk-header comment, a manifest new key, a manifest '../../x' key, an arbitrary CHANGELOG.md.
- Mutants on the new guard: key check (killed, 1), empty patch (killed, 1), fullmatch->match (killed, 4), split->splitlines (killed, 3), re.A dropped (killed, 1), CHANGELOG.md->any .md (killed, 1), manifest key exemption widened to all files (killed, 1).
- Earlier closures still hold (I re-read the diff 12f8054..e2fb0e1; release()'s gate lines and gh.pr are unchanged): opener/branch spoofs, path tricks, renames, base-branch config read, deep config caught, create_door still denies a release-please-- branch.
- scripts/build-release.py ships .claude-plugin, cli, bin, hooks, charters, skills, agents, keys, README, LICENSE, NOTICE and SECURITY.md. CHANGELOG.md and the manifest are not shipped.
- Not run: no scanner (no agent tooling changed). Unmeasured: GitHub's handling of a bare CR and of partial patches. Both now fail closed in the code.
- Confidence medium, not high: GitHub's patch behaviour is unmeasured live, and the exemption still depends on CI running on the head.

## Residual risk
A release PR's plugin.json can now change only version values. CHANGELOG.md and manifest keys stay unreviewed but are not executed or shipped. An agent can still push to the bot's branch; only version content gets through ungated.
