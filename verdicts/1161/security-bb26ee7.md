Verdict: FIX
Gate: security
Item: 1161
PR: taoq-ai/wuwei#1167
Head: bb26ee7277a9c9efc2e1253369954545386842dc
Confidence: medium

## Findings
- [medium] cli/wuwei/evidence.py:421 blocks: yes. Failure: the spec-gap cache key leaves out one of spec_gaps' inputs. The key is `pr-<repo>-<n>-<head>` plus engine and tier, but spec_gaps also reads the PR file list, and that list changes at the same head when the base is retargeted (a stacked PR moved onto main after its parent closes) or the merge base moves. The merge door calls gaps() without `listed`, so on main it re-read the spec on every call; now it reads this cache for up to a day. Repro (fresh copies of both trees, fake host): a full-tier PR 42 passes the merge door with a clean specs/7-rate-limits. Then the base is retargeted, the head stays the same, and the diff now also carries specs/8-stacked/spec.md with unchecked tasks, an open HIGH analysis row and an unchecked checklist. On main, guards.merge_door denies naming specs/8-stacked. At bb26ee7 it returns None and the merge proceeds, so a full-tier safety gap is hidden at the merge door (Done: "at full, the spec engine's artifacts"; CWE-524-class stale cache whose key omits an input, OWASP A04 insecure design). Fix: add the file list, or the sorted spec features taken from it, to the cached key. For example, append a digest of `files` to `key` or `kept`. Add a test that changes `files` at the same head and expects the new gap.
- [low] blocks: no. ws.cache_prune's glob `pr-<slug>-*` also matches a sibling repository whose name extends the slug (acme/app prunes `pr-acme__app-extra-3`). It only removes entries older than a day, which every reader already treats as expired, and a removed entry only causes a fresh read. That fails closed.
- [low] guards.py:62 blocks: no. The LEDGER_DENIED text lists the cache entries that feed gate inputs as ci-, review- and default-branch. cmp- (ancestry and delta) and the pr-...-<head> spec entries now feed the merge door too. The write guard already covers the whole of .wuwei/cache (probed below), so only the message is stale.
- [low] blocks: no. No secret, dependency or static-analysis scanner runs in this repository's CI (tests.yml, docs.yml, release.yml), so scanning is unmeasured, not clean. The diff adds no dependency, lockfile, install script or workflow change.

## Probes
- Corpus: tests/fixtures/routes.json sha256 9e099867c909e8400bd80bdcb7e6e4b5d8914785ac6171ed9a56e8aa3a7901b0 at main f63c804 and at the head (confirmed with sha256sum). `git diff --stat f63c804 bb26ee7` lists no guards.py or hook.py change, so no route differential is owed.
- specs/verdict-at-head/probe.py (identical file at main and head), run with PROBE_TMP in scratch over git archive copies of f63c804 and bb26ee7: 48592 cases generated, 0 whose gate result moves, 31250 named-PASS cases, 0 distinct shapes where the walk owes less. Holes were 0 ignored, 0 no-clear and 0 named at both trees. Compare calls fell from 84454 (main) to 74520 (head). No holes, so no class was added.
- Compare and ancestor cache (miscprobe.py, fake gh.run). The key holds the repo and both full shas: acme/app 'ahead' and acme/other 'diverged' for the same pair stay apart. A host 404 raises and writes nothing. A 7-char sha, an uppercase sha, '../../x'+hex, a sha+'\n' and a 41-char string are never cached (2 host calls for 2 reads each), so a verdict Head cannot steer a cache path (CWE-22 negative). A warm full-sha pair makes 0 host calls. A new head or a force push gives a new key; the answer for two full commit shas cannot change.
- Fail closed: gh.compare errors propagate out of _cached uncached, and gaps() turns GhError/KeyError/TypeError into 'evidence unreadable' (not actionable, blocking). Spec results with a ' missing: ' gap are never cached. gh.listing errors read as missing.
- Cache forgery (guards.pre_tool at head, scratch workspace): 10 write forms to .wuwei/cache/cmp-... and pr-...-<head> are all denied: Write, Edit, Write via /./ and //, printf >, cp, tee, python3 -c open, cd then >, ln -s. Known negatives: a Write to .wuwei/verdicts/... and ls are allowed. rm is allowed by design, and deletion only causes a fresh read.
- Prune: only entries older than max_age go. A fresh pr- entry, prs-, login and ci- entries stay. A planted symlink pr-acme__app-9.json -> /etc/hostname was neither followed for deletion nor touched in its target.
- Retarget scenario: tests/test_probe_retarget.py (scratch only) passes at main and fails at the head (merge_door returns None). Re-run in a fresh git archive copy of the head with the same result.
- Suite at the head copy: 2147 passed, 2 skipped (/root/.local/bin/pytest -q).
- Vendored .claude/wuwei/cli/wuwei/{board,evidence,gh,ws}.py are byte-identical to cli/wuwei at the head.
- Confidence medium: the compare cache, the guard coverage and the probe are clean and reproduced. The one blocking path needs a base retarget, which I reproduced with the fake host but not on GitHub itself.

## Residual risk
Gate verdicts are already keyed to the head and not to the base, so a retarget after review is a gap that predates this PR. Only the spec-gap cache newly hides a result that main re-read at the merge door.
