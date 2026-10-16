Verdict: PASS
Gate: goal
Item: draft-raise
PR: taoq-ai/wuwei
Head: 76a738ad735a284b76c5246cd77f834826d887fb
Confidence: high

## Findings
- [low] specs/draft-raise/tasks.md:39 blocks: no. T023's counts (204 commands, 21 drafts now pass, 23 ready routes held) describe 8774129; at 76a738a the compare covers 237 lines at head, 25 drafts now pass (four short clusters added) and more ready or merge routes are held. T023 also sits after Phase 3. The spec's Fix round section states the new behaviour correctly; only this tally is stale.
- [low] cli/wuwei/guards.py:197 blocks: no. The merge door's PR and repository reading changed, which is outside the promise but is part of the security fix. My probe of 26 gh pr merge argument lists shows it now differs from main only where main misread gh: --repo=x/y and -Rx/y now read x/y (main read the origin), and --subject 6 5 now reads PR 5 (main read 6). Two REST spellings (pulls/5//merge, pulls/5/%6Derge) that passed on main now meet the merge door. Each one tightens the door; none relaxes it.
- [low] blocks: no. Scope notes from 8774129 still stand: request_copilot_review, GraphQL requestReviews and five extra docs, all recorded in spec.md. The runtime stays at 2,999 of 3,000 lines.

## Probes
- Acceptance 1 to 7: the named tests from the first round all pass at 76a738a, as do test_every_route_reads_as_recorded over routes.json (every acceptance string is in it) and the rest of the group (211 passed in the -k selection): test_a_draft_opens_before_its_gates_with_the_pr_standard_once, test_a_create_that_is_not_a_draft_waits_for_its_gates_and_names_the_draft_route, test_an_mcp_draft_create_passes_and_any_other_create_waits, test_a_draft_leaves_draft_or_asks_reviewers_only_once_its_gates_pass (missing gate named, then passes after attest), test_undo_reads_and_a_pr_already_ready_pass, test_the_mcp_update_and_copilot_review_meet_the_ready_door, test_a_graphql_ready_or_reviewer_mutation_is_refused_with_the_route_to_use.
- Acceptance 8: in a git archive of 76a738a, pytest -q gave 853 passed, 2 skipped; cat cli/wuwei/*.py | wc -l gave 2,999; bin/wuwei agents build in a fresh commit printed "agents match the charters" with a clean status; diff -r against .claude/wuwei/cli/wuwei shows only __pycache__.
- Compare: I reran the builder's harness on git archives of 15c74df, 8774129 and 76a738a. The output is byte-identical to compare/main.txt, prev.txt and head.txt.
- Main to head moves, classified: create to pass are only draft creates (gh, gh pr new, REST --input with draft true, MCP draft true), now including -fd, -df, -wd and -dt x. Pass to ready are only ready or reviewer routes on draft PR 7 (gh, REST including //, %5F and o//r, MCP), including gh pr edit with flag values before 7 and --repo=, -R<value>. Pass to refusal are only markPullRequestReadyForReview and requestReviews. Pass to merge are only pulls/5//merge and pulls/5/%6Derge. Every other change is refusal wording.
- 8774129 to 76a738a moves: the four clusters (create to pass), "cd sub && gh api ... --input d.json" (pass to create), the slash and escape routes, and the gh pr edit flag-value routes. These match the coordinator's list: pflag reader, --input only when alone, path normalisation. Nothing else moved.
- Merge reader probe: I ran _repo_number from both trees on 26 merge argument lists (python3 -I). It differs only on --repo=x/y, -Rx/y and --subject 6 5, each matching how gh reads them.
- Spec Fix round section (spec.md) matches the code: _flags is shared by _repo_number, _draft and _api; merge's -m and -r are bools (PR_VALUED minus m, r); the --input draft counts only when segments(command) has length 1; the endpoint is unquoted with slashes collapsed. Clarifications now say clusters unpack as pflag does, and NOT_DRAFTS holds -dr=bob, -drbob and -dx. analysis.md S1 to S3 and Q1 are resolved with no open HIGH; the checklist and plan are updated. SECURITY.md and the shepherd charter's cloud reviewer route are consistent with the doors.
- Confidence high because the differentials reproduced exactly and every move falls into the promise or a named fix. It would drop if real gh differs from the recorded pflag v1.0.6 behaviour.

## Residual risk
The draft and PR readers follow pflag v1.0.6 and gh 2.89.0 as recorded by the builder and the security gate, not a live gh run in this gate. One line of runtime headroom remains.
