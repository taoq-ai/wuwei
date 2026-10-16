Verdict: PASS
Gate: security
Item: X-1
PR: taoq-ai/wuwei
Head: 201859ce8cef15d069e4a1e7afe469533b8a2eda
Confidence: medium

## Findings
- [low] cli/wuwei/evidence.py:121 blocks: no. Some content still reads as a release, and all of it is inert. CHANGELOG.md at the root takes any text: it is docs and scripts/build-release.py does not ship it. The manifest takes any path key with a strict semver value, and only release-please reads it. plugin.json takes extra or duplicate "version" lines, tab indents, and a patch with no +/- lines. The plugin.json version is read only for display and records (__main__.py:189, guards.py:173, setup.py:110). An attacker commit could set an odd semver such as 99.0.0, which could confuse client update ordering until the next release PR rewrites it. That is an availability note, not code execution.
- [low] cli/wuwei/evidence.py:105 blocks: no. The extra-files list is read from the PR's baseRefName. A writer who retargets the PR to an unprotected branch with a wider config gets only "version" lines through, and the merge lands on that branch, not main. String entries in extra-files are honoured, which matches release-please syntax.
- [low] cli/wuwei/evidence.py:121 blocks: no. Mutant `bool(files) and` dropped survives. It is equivalent in effect: a bot PR with no files has no code and ships nothing. The missing test is a note only.
- [low] cli/wuwei/gh.py:53 blocks: no. Pre-existing and outside this diff: the PR head and its files are read in separate calls, so a push between them pairs the old head with the new files. Every gap shares this race; the stale head then fails the gate checks.

## Probes
- The delta e2fb0e1..201859c is tests only (git diff --stat: tests/test_evidence.py, 4+/1-). It adds deletion-smuggle cases (a hooks line deleted beside a version bump, in plugin.json and in the manifest), and both keep every gap.
- Ran the suite in a scratch copy at 201859c (git archive): 317 passed. Runtime size is 3000 lines (wc -l cli/wuwei/*.py), at the limit.
- Wrote my own release() probe script (scratch probe/p.py, gh.file faked). Every acceptance shape holds: the real 1.2.1 shape is True. A human, the login 'github-actions', a branch that does not start with release-please--, and a PR adding guards.py are all False. With the config unreadable, plugin.json is False and manifest plus CHANGELOG is True.
- These smuggles keep every gap: bare CR, U+2028, NEL, a Cyrillic letter in the key, a fullwidth digit, a deleted hooks line, a None patch, an empty patch, a renamed CHANGELOG.md, docs/CHANGELOG.md, and no files at all. These read as a release, all inert: a tab-indented version line, a duplicate version line, a context-only patch, and "\ No newline" markers.
- Config probes: '../hooks/x.json' under package 'cli' normalises to hooks/x.json, and '/hooks/hooks.json' to hooks/hooks.json. Both come from base-branch config, and only version lines pass in either. 100000 nested '[' (RecursionError), [] and {'packages': []} all fall back to the manifest only (fail closed).
- Ten mutants on the new code, run against tests/test_evidence.py. Nine are killed: author check, branch check, renamed check, fail-open except, config read from the head ref, CHANGELOG widened to any .md, loose semver, '-' lines skipped, and the code list emptied for every PR. One survives (no-files), which is equivalent; see the findings.
- No scanner run: no agent tooling, workflow or dependency changed. Unmeasured live: how GitHub's files API sends partial patches and bare CR. The code fails closed on None and on CR.
- Confidence is medium, not high, because GitHub's live patch behaviour is unmeasured and the exemption still relies on CI and owner merge on the head.

## Residual risk
Anyone who can push to the bot's release-please-- branch can get only version values, manifest keys and CHANGELOG text through without a test or a gate. None of these is executed or shipped as code. CI, threads, owner review and the other safety gaps still apply.
