# Builder evidence

Source baseline: 3feedf5ca60ad78ac602cb1a44c165e2aade0263. Tested source head: 1976a022. The later evidence commit changes only prose and task completion.

## Tests

Red command:

```sh
uv run --no-project --with pytest python -m pytest -q tests/test_guards.py tests/test_evidence.py -k 'pending_review_allows or review_wait_does_not_waive or unreadable_review_classifier or oddly_shaped_actions or review_triggered_status_is_review' --tb=line
```

Result: 14 failed, 12 passed, 2425 deselected. The six pending-review auto cases refused, and unreadable classifier cases returned ordinary CI or failed to raise.

Green: same selection, 26 passed, 2425 deselected. Full focused modules: 2447 passed, 4 skipped. Runtime and vendor checks in tests/test_setup.py: 4 passed. Runtime remains 3745 physical lines, net zero against baseline.

## Route comparison

The runner reuses specs/gates-at-push/route_diff.py and adds recognized pending, running, failed and unreadable review hosts. Both trees use the same tests. Main is a git archive; head is the archive plus the exact runtime patch in 1976a022. All generated case roots live under .wuwei/scratch/builder-1255/.

Quality and security PASS fixture attestations name o/r#5 and o/r#7 at their own head. They are test evidence, never real review attestations. No exception is needed beyond the existing excepted host's approved CI-failure fixture.

Commands (prefix each Python invocation with `uv run --no-project --with pytest`):

```sh
python -I specs/1255-review-status/route_diff.py .wuwei/scratch/builder-1255/main tests .wuwei/scratch/builder-1255/cases-main
python -I specs/1255-review-status/route_diff.py .wuwei/scratch/builder-1255/head tests .wuwei/scratch/builder-1255/cases-head
python -I specs/1255-review-status/route_diff.py compare .wuwei/scratch/builder-1255/main-routes.json .wuwei/scratch/builder-1255/head-routes.json
```

Every movement follows:

```text
corpus sha256 de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (main) de377966b71fcb42f20fd057b033b43377891f3be8fd7d39130a81f750ed71c1 (head); 288 routes; 2304 cases; 45 moved
green: 288 cases, 0 moved
running: 288 cases, 0 moved
red: 288 cases, 0 moved
excepted: 288 cases, 0 moved
review-pending: 288 cases, 2 moved
review-running: 288 cases, 2 moved
review-failed: 288 cases, 0 moved
review-unreadable: 288 cases, 41 moved
- review-pending gh api -X PUT repos/o/r/pulls/5/ccr/auto_merge: main merge (waiting on review: Review Gate), head pass (no gap)
- review-pending gh pr merge 5 --auto: main merge (waiting on review: Review Gate), head pass (no gap)
- review-running gh api -X PUT repos/o/r/pulls/5/ccr/auto_merge: main merge (waiting on review: Review Gate), head pass (no gap)
- review-running gh pr merge 5 --auto: main merge (waiting on review: Review Gate), head pass (no gap)
- review-unreadable gh api --jq= -X PUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api --method= -X PUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api --method=PUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -H 'Accept: x' -X PUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o//r/pulls/7/requested_reviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/./pulls/7/ccr/ready_for_review: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7%D9%A3/requested_reviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7.0/ccr/ready_for_review: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7/./requested_reviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7//requested_reviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7/ccr/ready_for_review: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7/requested%5Freviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7/requested_reviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7/requested_reviewers/. -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X POST repos/o/r/pulls/7abc/requested_reviewers -f reviewers[]=bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT 'repos/o/r/pulls/5/merge?x=1': main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT 'repos/{owner}/{repo}/pulls/5/merge': main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT HTTPS://API.GITHUB.COM/repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT http://api.github.com/repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT repos/o/r/pulls/5/./merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT repos/o/r/pulls/5//merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT repos/o/r/pulls/5/ccr/auto_merge: main pass (no gap), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT repos/o/r/pulls/5/merge -f merge_method=squash: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X PUT repos/o/r/pulls/5x/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -X= -X PUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -XPUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh api -t= -X PUT repos/o/r/pulls/5/merge: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr edit --add-reviewer 5 7: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr edit --milestone 5 7 --add-reviewer bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr edit -t 5 7 --add-reviewer bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr edit 7 --add-reviewer bob: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr merge --repo=o/r 5: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr merge -R a/b -R o/r 5: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr merge 5 --auto: main pass (no gap), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr merge 5 --auto=false: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr merge 5 --squash: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr merge 5 -t --auto: main merge (CI running), head merge (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr ready --repo=o/r 7: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr ready -R a/b -R o/r 7: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr ready -Ro/r 7: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
- review-unreadable gh pr ready 7: main ready (CI running), head ready (evidence unreadable: review status classification unreadable)
```

## Class sweep

- AUTH PASS: route_diff.py above, 288 routes and 2304 cases per tree. CLI, REST and MCP auto-merge consumers also pass the regression selection.
- VAL N.A.: no command parser or normalization change. The focused tests cover pending, failed, missing and malformed classifier evidence.
- TEST PASS: pytest focused modules above, assertions exercise pre_tool, ready_door through guards.bash, and evidence.gaps.
- ERR PASS: classifier failure becomes explicit unreadable evidence; both merge modes refuse in the regression selection.
- STATE N.A.: no new writer or persisted state transition. Existing workflow cache remains unchanged.
- CON PASS: the documented 1067-probe producer fixture passes through evidence, ready and merge consumers in focused tests.
- INF N.A.: no secret, environment key or entry point changes.

CI: unread. Full suite and independent gate reviews remain for the planner. Residual risk: no new live sanitized failure sample was accessible, so classification remains limited to the supported observed shape.
