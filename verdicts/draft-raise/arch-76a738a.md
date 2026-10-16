Verdict: FIX
Gate: arch
Item: draft-raise
PR: taoq-ai/wuwei
Head: 76a738ad735a284b76c5246cd77f834826d887fb
Confidence: medium
Breaking: yes: on a draft PR, gh pr ready, POST pulls/<n>/ccr/ready_for_review, MCP update_pull_request with draft false or reviewers, request_copilot_review, gh pr edit --add-reviewer and POST pulls/<n>/requested_reviewers now wait for the gates; GraphQL markPullRequestReadyForReview and requestReviews are refused on any PR; and gh api endpoints spelled with repeated slashes or percent-escapes (for example PUT pulls/5//merge) now meet the merge, push, rules and delete doors they passed on main

## Findings
- [high] cli/wuwei/guards.py:188 blocks: yes. Failure: the endpoint normalisation collapses repeated slashes and decodes percent-escapes but leaves dot segments, so "gh api -X POST repos/o/r/pulls/7/./requested_reviewers -f reviewers[]=bob" on draft PR 7 with no gates matches no API row and passes, which is a reviewer request around the new ready door; "gh api -X PUT repos/o/r/pulls/5/./merge" passes the merge door the same way (also open on main, but this delta claims the endpoint is now read as gh reads it). Measured: gh api repos/taoq-ai/wuwei/pulls/./1096 returns PR 1096, so GitHub routes the dot spelling. posixpath.normpath on the decoded path would cover //, /./ and /../ in one call.
- [high] cli/wuwei/guards.py:208 blocks: yes. Failure: the alone rule counts segments after wrappers are unwrapped, and segments() drops a wrapper's options, so "env -C sub gh api -X POST repos/o/r/pulls --input d.json" reads as one segment: the hook parses ./d.json ({"draft": true}) while gh reads sub/d.json (no draft) and opens a ready PR with no gates. sudo -D does the same. This is the cd sub && case the fix round closed, reached by another spelling; treat an --input draft as alone only when the command's argv[0] is gh itself (no wrapper), or when the wrapper has no cwd option.
- [low] specs/draft-raise/spec.md:133 blocks: no. The Breaking section and the commit's BREAKING CHANGE text list only the ready-door routes and the two mutations; the fix round also makes endpoints with repeated slashes or percent-escapes meet the merge, push, rules and delete doors (pulls/5//merge passed on main) and changes which PR and repository gh pr merge reads (first positional after value flags, --repo= and -Rx/y). Add one Newly held line; the migration needs nothing beyond "spell the endpoint plainly".
- [low] specs/draft-raise/spec.md:139 blocks: no. Short-cluster drafts (-fd, -dt x) now pass; "Newly passing: a draft create before its gates" covers them and the clarification at spec.md line 74 states it, so no extra line is needed.
- [low] cli/wuwei/guards.py:153 blocks: no. One shared _flags reader for _repo_number, _draft and gh api is the right shape (it removed API_FLAG and the hand-rolled loops at no line cost); each caller passes its own valued set, and gh pr merge subtracts -m and -r. _draft reads -drbob as d, r (unknown), b=ob rather than pflag's r=bob, but the outcome (held) is the same because r is outside the create reader's sets.
- [low] cli/wuwei/guards.py:1 blocks: no. Runtime still 2,999 of 3,000 (cat cli/wuwei/*.py | wc -l); the normpath fix fits in the line it replaces plus an import, which reaches the cap exactly. A free-lines item should precede the next runtime change.

## Probes
- git diff 8774129 76a738a for guards.py, spec, SECURITY.md, docs, shepherd charter and routes.json; earlier arch notes are resolved (evidence.md row, shepherd cloud reviewer route).
- pytest -q in an archive copy at 76a738a: 853 passed, 2 skipped; cli/wuwei matches .claude/wuwei/cli/wuwei (diff -r).
- probe.py in my scratch folder: segments("env -C sub gh api ... --input d.json") returns one segment with env and -C gone; _api on repos/o/r/pulls/7/./requested_reviewers returns that endpoint unchanged, so no API row matches; _repo_number(['-m','7']) with merge's set returns PR 7; _draft(['-fd']) is True, _draft(['-dr=bob']) is False.
- One read-only GET, gh api repos/taoq-ai/wuwei/pulls/./1096, returned 1096: GitHub routes the dot segment.
- merge_door still refuses when no number is read, so a misread value flag fails closed rather than merging the wrong PR.
- Confidence medium: the two blockers are concrete and measured on GET; I did not run a write to confirm the POST and PUT routes behave the same as the GET.

## Residual risk
Other cwd-changing spellings (subshells, pushd) depend on segments() counting more than one segment; I checked cd, env -C and sudo -D only. The one-line runtime headroom remains.
