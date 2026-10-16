Verdict: PASS
Gate: arch
Item: vendored-drift
PR: taoq-ai/wuwei
Head: e1e87ccbead6ad63c9588de9ef2445cd7a1dd018
Confidence: high
Breaking: no

## Findings
- [low] tests/test_setup.py:137 blocks: no. Carried from 8b188da. When an agent or skill is removed upstream, its old copy stays in .claude/, and the test does not flag it. vendor() does not delete it either, and changing vendor() is outside this item.
- [low] tests/test_setup.py:132 blocks: no. Carried from 8b188da. .claude/settings.json is written by setup.py, not by vendor(), so the drift test does not compare it. If the hook commands in setup.py change, the committed settings can drift silently. Follow-up candidate.

## Probes
- Head: `git rev-parse origin/claude/vendored-drift` = e1e87cc, a merge commit with parents 467b46c and 478e899 (origin/main, which now holds #1075, #1076 and #1077).
- Previous findings: note 1 (merge order) is closed, because the three PRs merged first and this branch re-vendored on the merged tree. Note 4 (ADR line 15) is closed: it now reads "cut 1.2.1 from main at 5d7157b; its release commit on main is 2a306da", which matches the base and merge sha of #1072. Notes 2 and 3 are carried as notes.
- Footprint: I compared the added and removed lines outside .claude/, docs/adr and the new checklist. `git diff origin/main...8b188da` and `git diff origin/main e1e87cc` give the same lines (SAME_FOOTPRINT). The only new file outside .claude/ is specs/vendored-drift/checklists/requirements.md, a 9-line checklist. `git diff 8b188da 467b46c` shows only the ADR line and that checklist.
- Copy at e1e87cc: in a scratch copy of the tree, setup.vendor() into a tempdir, compared byte for byte with the committed .claude/ (ignoring __pycache__ and .pyc), gives differ [] and extra ['settings.json']. settings.json lies outside wuwei/ and the WUWEI skill folders, so it is out of scope. Against main, the diff has exactly the six cli files (evidence, gh, guards, hook, setup, ws) plus the copy's plugin.json at 1.2.1, which equals the root version.
- Suite on the merged tree: 375 passed. The three new tests (vendored match, drift check, release-please bump) pass. `wc -l cli/wuwei/*.py` = 2996, within the budget.
- #1076's release exemption, now on main: I called evidence.release() at e1e87cc with gh.file stubbed to return this branch's release-please-config.json. Results:
  - bot author, release-please-- branch, CHANGELOG plus manifest plus both plugin.json files with a version-only patch: True;
  - the same PR plus a code line in .claude/wuwei/cli/wuwei/gh.py: False;
  - the same release PR read against main's current config, which lacks the copy's entry: False.
  So the first release after this item merges is exempt as intended, and the exemption does not cover vendored code. Before this item merges, release-please does not bump the copy, so no such PR exists.
- Confidence is high: I ran the suite, the byte-for-byte vendor comparison and the release() calls on the exact head.

## Residual risk
Contributors to cli/, charters/, agents/ or skills/ must now re-vendor in every PR, and the drift test's failure message names the fix. Removed agents and skills, and settings.json, remain outside the drift check.
