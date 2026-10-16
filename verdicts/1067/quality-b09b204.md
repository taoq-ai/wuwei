Verdict: PASS
Gate: quality
Item: 1067
PR: taoq-ai/wuwei#1071
Head: b09b20469703ab3995713a84b5d95c259d03df04
Confidence: medium
Breaking: no

## Findings
- [low] cli/wuwei/evidence.py:350 blocks: no. Each unsettled run-linked status still pays one uncached per-run read. A token without Actions read pays one failed review-workflow read per evidence read (fail-closed to CI, tested). Caching by run id would remove the cost. A limit, unchanged from 3fb3f40.
- [low] cli/wuwei/evidence.py:350 blocks: no. Design limits, unchanged: a CI workflow that also listens on pull_request_review reads as review (the merge is still refused), and a review workflow outside the last 100 runs or newer than the day-old cache reads as CI.
- [low] cli/wuwei/evidence.py:246 blocks: no. A gap that was there before: the `imported` branch of verdicts() has no test that reaches it, and deleting it also passes the suite on origin/main. The builder's merge of the two appends is equivalent by reading.

## Probes
- Suite in a scratch copy of b09b204: 286 passed (280 at 3fb3f40, plus the 3 new tests, one of them 4 cases). The runtime is exactly 3000 lines, the cap, with no margin.
- Delta 3fb3f40 to b09b204 touches evidence.py (3 lines), tests and the spec tasks only; gh.py and the guards are untouched.
- Mutants on the delta, all KILLED:
  - the duty check reverted to startswith('CI failing'): test_a_failing_review_gate_still_names_an_approval_at_an_older_commit
  - TypeError dropped from the except: test_an_oddly_shaped_actions_reply_leaves_the_status_ci[workflow_runs None]
  - AttributeError dropped: the 'not json' case of the same test
  - KeyError dropped: the {'id': 7} case
  - `runs and` guard removed: test_a_head_without_commit_statuses_makes_no_actions_read
  - `paths and` guard removed (my previous surviving mutant): test_a_repo_without_review_workflows_reads_no_run
- My two earlier surviving mutants (the `paths and` guard, the narrowed except) are now killed. Both findings are closed.
- Regex moved inside the try: not run as a mutant, because my scripted edit broke the syntax. By reading, url=7 makes re.search raise TypeError, which the new case sends in, so only the in-try placement passes it.
- The duty change is correct by reading. A "change request outstanding" gap now also names an approval at an older commit, as "CI failing" already did, and the new test asserts both texts in order.
- Confidence is medium because ai-stacks still returns 403 here, so the real run `path` shape is unmeasured.
- Simplicity: none. The except tuple is now covered case by case, and no trust-boundary or fail-closed code is deletable.

## Residual risk
The tie from status to workflow rests on 1067-probe's reading of ai-stacks, which this session could not re-check. The widened except fails closed to CI, never to a pass.
