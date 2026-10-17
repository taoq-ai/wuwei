Verdict: PASS
Gate: arch
Item: free-lines-5
PR: taoq-ai/wuwei#1123
Head: a287d4458e68ee0cafb94c0e70246718a8892ed0
Confidence: high
Breaking: no

## Findings
- [low] blocks: no. upgrade.items now counts imports as len(known) - before instead of a counter. This is equivalent only because each _add is guarded by "lower-cased id not in known" followed by known.add of that same id. A future edit that adds to known without importing would make the count wrong silently. The comment on `before` records the invariant.
- [low] blocks: no. The probes cover board.compute and board.rows by reading the code, not by running them: rows now calls evidence._cached, which is the same two-line cache_get/cache_put body, and `mine` is the same filtered list in the same order that the except branch and the loop rebuilt before.

## Probes
- git diff d1c3d79..a287d44 --stat: 10 runtime files in cli/wuwei and the vendored copy plus specs only. guards.py, tests, design.md and the constitution are untouched. diff -r shows the vendored copy is identical to cli/wuwei.
- Constitution: stdlib only, and no import was added (report.py only moves `import hashlib` into the stdlib block). Walrus in conditions and in comprehension filters needs Python 3.8, well under the 3.11 floor. No config key, door or contract changed.
- Contract check: every message, f-string, exit path and return value is byte-identical in the diff. Breaking: no.
- wc -l on cli/wuwei/*.py: base 2996, head 2975 (-21), git-globals 783522a 2997 (+1).
- git merge-tree --write-tree a287d44 783522a: clean (tree b434556), and the two branches touch disjoint files. The merged tree has 2976 runtime lines and its suite gives 1600 passed, 2 skipped. The head suite alone gives 1500 passed, 2 skipped.
- Headroom: 3000 - 2976 = 24. The queued scratch-remotes (+2), push-refspecs (+4) and gh-args (+3) total +9, which lands at 2985 with 15 spare.
- Differential probe (scratchpad probe.py, run under python3 -I on both trees), identical outputs on both:
  - verdict.parse over 201 real verdict files, strict and non-strict, plus 5 edge texts (407 results);
  - hook._verdict_problem and hook.handle with an unknown event;
  - agents.stale, clean and with one file tampered and one removed;
  - upgrade.items with 1000 imports, a case duplicate, done/parked/non-dict rows and lead candidates with duplicates, then a second run (imports 0);
  - report.learning exception lines over 2000 ruling rows.
- Timing, 4 alternating runs per tree, head vs base medians: verdict.parse 125 KB 7.5 vs 7.2 ms; verdict.parse 500 KB 32 vs 31 ms; _verdict_problem at 500 KB 3.3 vs 3.2 ms; upgrade.items at 1000 imports 6.6 vs 6.2 s (I/O-bound; base itself ranged 5.9 to 7.7 s); report.learning at 2000 rows 0.42 vs 0.44 s. Spread was the same on both trees, nothing moved beyond noise, and no rewrite changes the order of growth.
- Confidence reason: every rewrite is a local mechanical substitution with the same evaluation order and short-circuit behavior, and the differential and merge probes ran on real trees.

## Residual risk
The differential probe did not run board.compute against a live code host. It is equivalent by reading the code only. Timing at 500 KB is noisy at the 20 percent level, so repeated runs were needed to separate noise from change.
