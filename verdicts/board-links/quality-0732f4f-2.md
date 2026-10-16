Verdict: FIX
Gate: quality
Item: board-links
PR: taoq-ai/wuwei
Head: 0732f4f301643058ff65fc0a92afc4d371998c18
Confidence: medium

## Findings
- [medium] cli/wuwei/board.py:55 blocks: yes. Failure: the fallback in names (item_for through the plan's prs list or the branch name when the body names no item) is reversed to `or set()` and the whole suite still passes except the vendor-drift test. A PR on branch `A-fix` with no WUWEI footer then shows item A as "no pull request yet" and never closes it once merged, and nothing catches it. Add one board test for a footer-less PR linked by branch name (and by the plan's prs list).
- [low] cli/wuwei/board.py:70 blocks: no. The `unlinked` line is not needed. Any open item without an open PR (approved but not started, awaiting approval, a run item) makes it true, which is the normal state of a plan, so the 300 s branch almost never serves. Cheaper and shorter: drop `unlinked` and the cache and read `merged = gh.merged_prs(repo, since) if mine else []`. The board is cached 60 s and the open list 60 s, so this is at most one call per repo per minute, the bound the spec already accepts. It deletes 1 runtime line, the extra `names` scan per compute and the magic `-1`. Fresh only when a branch exists on the remote is not available: the branch is not recorded (out of scope in the promise). A shorter TTL (60) also passes scenario 2 but fails a 50 s-old cache, so it does not close "just merged" reliably.
- [low] blocks: no. tests/test_watch.py: The 300 s branch (all items linked, cache serves) has no test; `-1 if unlinked else 300` reversed to a constant -1 survives. If the simplification above is taken this disappears.
- [low] blocks: no. `.lower()` on both sides makes case handling untestable as a mutant; a case-mixed footer test is missing but the behavior is equivalent to plan.find.

## Probes
- Copy of the tree from git archive at the head: full suite 473 passed, 2 skipped; runtime `cat cli/wuwei/*.py | wc -l` = 2949 (cap 3000, met).
- Mutants (each also trips the vendor-drift test, which I ignore): items_named limited to first match: fails test_a_pr_naming_two_items_links_both_and_closes_both_once_merged. Fresh-read condition replaced by 300: fails the two-items test and test_an_item_whose_pr_just_merged_closes_despite_a_stale_merged_cache. Uncounted line removed: fails test_an_item_with_no_pr_names_its_uncounted_verdicts. done and linked reverted to item_for: each fails the two-items test. names fallback removed: SURVIVES (finding 1). Fresh constant -1: survives (note).
- Acceptance: scenarios 1, 2, 3 each have a test that reaches board.compute; 4 holds at 2949.
- Tests are real: each new test fails under its matching mutant.
- Simplicity: delete the `unlinked` line and the cached `_list` call for merged, replace with a direct `gh.merged_prs(repo, since)` read (-1 line, no `-1` magic ttl). Nothing else; names and items_named carry the promise.
- Vendored copies under .claude/wuwei match cli/wuwei in the diff (identical hunks).

## Residual risk
The merged list is read once per repo per compute in practice; large plans on tight rate limits could feel it. A stale open-PR cache (60 s) still delays closing by up to a minute, as before.
