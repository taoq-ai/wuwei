Verdict: PASS
Gate: goal
Item: gh-doors
PR: taoq-ai/wuwei#1108
Head: fd32bc2b11a23d71f5007e14e67b707f17bd5eaa
Confidence: high

## Findings
- [low] tests/fixtures/routes.json:125 blocks: no. The acceptance 1 row refuses because q.json is missing in /repo (the "cannot read" reason), not by naming markPullRequestReadyForReview; the naming half of acceptance 1 rests on test_a_graphql_input_file_has_its_query_read_for_door_mutations, which passes.
- [low] tests/fixtures/routes.json:132 blocks: no. The merge rows (-t --auto, --auto=false) record only "merge" reached, the same on main and head; the CI-running outcome of acceptance 4 is held by test_merge_reads_auto_the_way_pflag_does, not by the corpus.
- [low] cli/wuwei/guards.py:198 blocks: no. gh pr merge 5 -t --admin moved from refusal to the merge door. That matches pflag (admin=false, --admin is -t's subject) and promise (1), and the merge door still runs; it is a loosening worth naming in review notes.
- [low] blocks: no. Two choices go beyond the promise text and are declared in the spec's Clarifications and Assumptions: the plain-call rule also covers -F query=@file, and an empty --input file counts as unreadable. Only -F query= counts, not every -F @ field, also declared (variables carry no mutation).
- [low] blocks: no. The builder's pflag mirror is v1.0.6; gh 2.89.0 links pflag v1.0.10 (go version -m). Bool parsing (strconv.ParseBool) and value-flag consumption are the same in both, so the readings hold.

## Probes
Plan: wuwei plan.json item gh-doors read with python3; goal G-2 from .wuwei/goals.md; diff 23625f3..fd32bc2 touches guards.py (both copies, identical hunks), docs/design.md, docs/site/concepts/doors.md, routes.json, test_guards.py, specs/gh-doors only.
Real gh 2.89.0, my own copy of the builder's server.py on my own socket (scratchpad/goal-gh-doors/gh), one call each: --input q.json logged POST /graphql with the markPullRequestReadyForReview body; echo mergePullRequest | --input - logged POST /graphql with the raw mutation; -F query=@- logged POST /graphql {"query":"mutation { mergePullRequest ..."}; -X POST repositories/123/pulls/5/requested_reviewers -f reviewers[]=a logged POST /repositories/123/pulls/5/requested_reviewers {"reviewers":["a"]}; gh api repositories/123 logged GET /repositories/123.
Suite at head in a git archive copy: pytest -q gives 1009 passed, 2 skipped. Runtime lines: 3000 (base 2992), within the budget.
Corpus: builder's probe_test.py run fresh on base and head copies (base given head's routes.json, as the builder did); compare.py shows 132 routes, 8 moved, all among the 11 new rows (6 pass to refusal, 2 merge to refusal), 0 of 121 pre-existing rows moved, no foreign refusal. Probes: 13 moved, each a declared shape; ok.json, -F query=@ok.graphql, -f query=@threads.graphql -F number=5 and gh api repositories/123 still pass.
pflag v1.0.6 harness I wrote with merge's flags: -t --auto auto=false; --auto true; --auto=false false; --admin=true and --admin=1 admin=true; -t --admin admin=false; --admin=yes is a parse error. guards.TRUE matches strconv.ParseBool's true set.
Spec specs/gh-doors/spec.md: promise in its own words matches (1) to (4) and the Outside list; acceptance 1 to 6 restated faithfully; Breaking section and PR body (REST read, head fd32bc2, draft) agree with the diff.
Assumption check: grep of .wuwei/traces.jsonl (3466 rows) for graphql with --input or -F query=@, gh api repositories/, and merge with --admin or -t finds only gate probe commands, no seat route.
Confidence high: every acceptance line has a real run or a passing test at this head, and the corpus moved only on the new rows.

## Residual risk
A future gh merge flag that WUWEI's VALUED set does not know could shift how --admin or --auto is read (named in the spec's How this fails 2). ?draft=false on a POST stays unmeasured, as the item declares.
