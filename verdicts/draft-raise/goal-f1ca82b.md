Verdict: PASS
Gate: goal
Item: draft-raise
PR: taoq-ai/wuwei
Head: f1ca82b2a9570af2f02f8f4a2a38d6f161a3a73d
Confidence: high

## Findings
- [low] specs/draft-raise/tasks.md:39 blocks: no. T023 says 52 refusals changed text only. I count 54 refusals with changed text: 50 are wording only (48 create-door, 2 GraphQL mergePullRequest), and 4 are merge-door refusals that now name the PR or repository gh reads (gh pr merge --repo=x/y 5, -Rx/y 5, -t 3 5, and URL with -R o/r). Those 4 are the named repository-reading fix and still refuse, but T023 neither counts nor itemises them. All the other T023 counts match: 248 commands, 25 drafts, 36 ready, 3 merge spellings, 4 newly refused.
- [low] blocks: no. The runtime is now exactly 3,000 of 3,000 lines (+38 over main 7f31a51, which is 2,962). It is within the cap, and plan.md and the checklist record it, but the next runtime change has no headroom.
- [low] blocks: no. The scope notes from earlier rounds still stand (request_copilot_review, GraphQL requestReviews, extra docs, merge-door reader). Each makes a door stricter and none lets more through.

## Probes
- Acceptance 1 to 7: test_a_draft_opens_before_its_gates_with_the_pr_standard_once, test_a_create_that_is_not_a_draft_waits_for_its_gates_and_names_the_draft_route, test_an_mcp_draft_create_passes_and_any_other_create_waits, test_a_draft_leaves_draft_or_asks_reviewers_only_once_its_gates_pass, test_undo_reads_and_a_pr_already_ready_pass, test_the_ready_door_stays_shut_without_a_number_or_a_readable_pr, test_the_mcp_update_and_copilot_review_meet_the_ready_door, test_a_graphql_ready_or_reviewer_mutation_is_refused_with_the_route_to_use and test_every_route_reads_as_recorded (every acceptance string is in routes.json): 236 passed at f1ca82b.
- Acceptance 8: in a git archive of f1ca82b, pytest -q gave 901 passed, 2 skipped; cat cli/wuwei/*.py | wc -l gave 3000 (the test asserts <= 3000); bin/wuwei agents build printed "agents match the charters" with a clean status; diff -r against .claude/wuwei/cli/wuwei shows only __pycache__.
- Merge: f1ca82b merges 25479bf3 with 7f31a51 and the merge commit adds no change of its own (git show --cc is empty). Main touched hook.py and plan.py, not guards.py.
- Corpus: sha256 of routes.json at f1ca82b and at 25479bf3 is 70bf0867..., which matches compare/corpus.sha256.
- Compare: I ran the builder's harness on git archives of 7f31a51, 76a738a and f1ca82b. The outputs are byte-identical to compare/main.txt, prev2.txt and head.txt.
- 76a738a to f1ca82b moves (9, all named fixes): dot segments (repos/o/r/./pulls/7/ccr/ready_for_review, pulls/7/./requested_reviewers and requested_reviewers/. now go to the ready door; pulls/5/./merge now goes to the merge door; ./contents/a.md is refused as a push); a write through .. is refused (pulls/5/../5/merge); and the stricter --input rule (env -C sub, env --chdir=sub and sudo -D sub before gh api --input d.json now meet the create door). Nothing else moved.
- 7f31a51 (main) to f1ca82b moves: refused to pass: 25, all draft creates. Pass to ready-door hold: 36, all ready or reviewer routes on draft PR 7. Pass to merge door: 3 (//, %6D, . spellings). Pass to refused: 4 (2 GraphQL mutations, the . spelling of a contents write, the .. write). Refused to refused: 54 (50 with wording only, 4 merge-door repository and PR readings as gh reads them). No other verdict moved.
- Code against spec Phase 4: the endpoint drops empty and . segments after unquote; the dots route (r'(.*/)?\.\.(/.*)?', WRITE) refuses writes and lets reads pass; an --input draft needs one segment, gh as the first word and no ~ $ * ? [ character. These match T027 to T029, spec Clarifications, Breaking, SECURITY.md and analysis S4, S5 and Q2, with no open HIGH. The new corpus routes are cited to the gates.
- Confidence is high because all three differentials reproduced exactly and every move falls into the promise or a named fix. It would drop if GitHub routed dot or .. spellings differently from the read-only GETs the security gate recorded.

## Residual risk
The behaviour of gh, pflag and GitHub's path handling is as the builder and the security gate recorded it; I did not run a live gh or GitHub call here. The runtime has no headroom left under the 3,000-line cap.
