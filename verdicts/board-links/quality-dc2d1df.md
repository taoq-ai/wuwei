Verdict: PASS
Gate: quality
Item: board-links
PR: taoq-ai/wuwei
Head: dc2d1dfa3a4ddc87c8f523555577459b1dac523a
Confidence: high

## Findings
- [low] blocks: no. The earlier finding on the names fallback is closed: test_a_footerless_pr_links_by_branch_name_and_closes_the_item_once_merged and test_a_footerless_pr_links_through_the_plan_prs_list both fail under the `or set()` mutant.
- [low] tests/test_watch.py:93 blocks: no. test_an_item_whose_pr_just_merged_closes_despite_a_stale_merged_cache no longer exercises a cache the code reads (merged has none now); it still guards the behavior but its cache setup is vestigial and could be dropped.

## Probes
- git archive of dc2d1df into a scratch directory: full suite 476 passed, 2 skipped; runtime `cat cli/wuwei/*.py | wc -l` = 2947 (cap 3000, met).
- Vendored copy under .claude/wuwei/cli/wuwei is identical to cli/wuwei (diff -r shows only __pycache__).
- Mutants patched in both the tree and the vendored copy, so the drift test does not mask: items_named first match only fails the two-items test; names fallback removed fails the branch-name and prs-list tests; merged read through a 60 s cache fails the two-items and branch-name tests; uncounted line removed fails the uncounted test; done reverted to item_for fails the two-items test; linked reverted to item_for fails the two-items test.
- Acceptance: scenarios 1 to 3 each have a test through board.compute; scenario 4 holds at 2947.
- Simplicity: none. The unlinked line, the -1 cache trick and _list's ttl parameter are gone; names and items_named carry the promise. The cost is one merged-list call per repo per board compute, at most one a minute behind the 60 s board cache, as the spec assumes.

## Residual risk
Large plans on tight GitHub rate limits pay one merged-list call per repo per minute. A stale 60 s open-PR cache still delays closing by up to a minute, as before.
