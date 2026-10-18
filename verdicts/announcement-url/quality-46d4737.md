Verdict: PASS
Gate: quality
Item: announcement-url
PR: taoq-ai/wuwei#1148
Head: 46d4737fdeea7a23a2d47b39f73664db409cc302
Confidence: high

## Findings
- [low] blocks: no. Docs drift: docs/site/concepts/evidence.md:77, docs/site/reference.md:71 and docs/design.md:111 still say `Announcement: <link>` and list a release note without "already published" or "the URL alone on its line". The gap text names the new shape, so nobody is stuck, but the user docs now describe the old contract.
- [low] blocks: no. Limit, by design of the promise: the guard checks the URL's shape, not that the URL resolves or was published. An `Announcement: https://example.com` line, or one inside an HTML comment or a fenced block, still clears the gap. This existed before the change too.
- [low] blocks: no. The charters/_common.md Done list (and every agents/*.md built from it) still says `Announcement: <link>`. The shepherd charter is precise now and the evidence text names the shape, so this is only wording.

## Probes
- Suite at the head (git archive copy): `/root/.local/bin/pytest -q` gives 1810 passed and 2 skipped. Both skips are tests/test_release.py, because ssh-keygen is absent, and neither touches this item. The focused test collects 32 rows and all 32 pass.
- Test-first: the head's tests run against main's runtime (b28a3dc, with head tests and charters) give 39 failed. That covers all 26 ANNOUNCE rows, test_breaking's announcement test, and the 12 older breaking tests that share the ANNOUNCE message constant. The 6 CONFIRM rows pass on main as they should, because main also counted them. rows.py agrees: 32 rows, 6 count at the head, 19 counted on main and refused at the head, 7 refused on both.
- Reaching the consumer: each row asserts the full `texts(evidence.gaps(root, 'acme/app', 42))` list with arch, quality and security attested. evidence.gaps calls breaking_gaps (evidence.py:398). The CONFIRM rows show that only the owner's breaking: confirmation is left, which matches acceptance 2. The placeholder row `Announcement: CHANGELOG.md (placeholder)` gives the gap naming the http(s) URL shape, which matches acceptance 1.
- Builder probe (specs/announcement-url/probe.py) in a fresh copy against main: part 1 ran 12960 bodies with 0 holes against the urlsplit oracle; 4760 verdicts moved from main, and 0 of those moved to counted, so the change only tightens. Part 2: all 8 builder mutants killed, 0 survived.
- My own mutants on evidence.py:341, each run against the focused test plus tests/test_breaking.py: `https?`->`https` killed (1 row, http). Dropping `[ \t]*` killed (7 rows). `[^\s/?#]+`->`\S+` killed (https:///n). `[ \t\r]*$`->`\s*$` killed (the NBSP-suffix row). Adding re.I killed (2 rows, HTTPS and lowercase key). Dropping re.M killed (8 rows). Inverting `if not` killed (35 tests). The lazy `\S*`->`[^\s]*?` survived. A differential probe over the same 12960 bodies shows 0 differences between it and the head regex, so it is an equivalent mutant.
- Charter fitness test (test_the_shepherd_asks_for_an_announcement_url_that_exists_at_the_head): it fails on main's shepherd charter. In a copy I made 5 negations ("need not exist at the head", "later counts.", "holds a link or a path.", "`Announcement: <link>`", "does count") and the test killed all 5.
- Old-contract tests: test_breaking.py changed only the expected message and replaced `Announcement: CHANGELOG.md` with a URL in the moved-head test, which keeps that test's intent (the confirmation binds to a head). No assertion was removed or loosened. The ANNOUNCE constant was updated in place.
- Budget: the cli/wuwei/*.py total is 2992 lines at both main and the head, so 0 runtime lines were added (budget 2). The vendored .claude/wuwei/cli/wuwei/evidence.py and .claude/wuwei/charters/shepherd.md match their sources byte for byte (diff). The agents drift test passes inside the suite.
- CI at the head, read once via REST check-runs: test 3.11/3.12/3.13, CodeQL, both Analyze jobs, ZIRAN and ziran-audit all completed successfully.
- Test quality: the tests use the fake gh and a tmp root. They use no wall clock, network or shared file, and they assert on the gap decision list.
- Confidence high because every guard mutant, including my own, is killed, the oracle probe has 0 holes, and the tests fail on main. A real PR body shape the corpus lacks (for example Unicode line separators) would lower it.
- Simplicity: none. The diff changes one regex and one message with 0 net runtime lines. `[^\s/?#]+\S*` could be written `[^\s/?#]\S*`, but that is cosmetic and not worth a change.

## Residual risk
Only the URL's shape is checked, not whether it resolves or was published; the shepherd charter and the owner's breaking: question carry that. The user docs still describe `<link>` until someone updates them.
