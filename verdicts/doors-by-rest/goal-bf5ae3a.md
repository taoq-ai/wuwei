Verdict: PASS
Gate: goal
Item: doors-by-rest
PR: taoq-ai/wuwei
Head: bf5ae3ae539aba6ed554025733039257a0e6a821
Confidence: high

## Findings
- [low] cli/wuwei/guards.py:34 blocks: no. MUTATIONS also refuses mergeBranch and enqueuePullRequest, which the promise does not list. This is a claim beyond the requirement, but it is deliberate and recorded in spec.md Clarifications. Both are merge routes, and no seat or transcript uses either.
- [low] cli/wuwei/guards.py:30 blocks: no. POST repos/<r>/git/refs (creating a ref, no trailing path) still passes. The promise names only "git/refs/". Creating refs/heads/main where main already exists fails at GitHub, so I could not turn this into a harmful input.
- [low] cli/wuwei/guards.py:170 blocks: no. Field files (-F body=@f, --input f) are read relative to the payload cwd. A "cd elsewhere && gh api ... -F body=@pr.md" reads the wrong file or none, so the item comes from the branch. gh pr create --body-file had the same limit on main. A graphql query sent in an --input JSON is not searched, which falls under the promise's Outside clause (graphql queries read from a file).
- [low] blocks: no. docs/site/concepts/doors.md does not list the new REST, graphql and MCP push routes. SECURITY.md does. The promise's Touches list leaves docs out, so this is a follow-up, not drift.

## Probes
- Suite at head in a git-archive copy: /root/.local/bin/pytest -q gave 645 passed, 2 skipped. The runtime size test passes. find cli/wuwei -name '*.py' | xargs cat | wc -l gives 2,996 (cap 3,000).
- Replayed every unique Bash command from all 74 transcripts under /root/.claude/projects/-home-user-wuwei (1,302 commands) through guards.pre_tool on origin/main 40a966b and on the head. Doors were stubbed to sentinels and origin was taoq-ai/wuwei. Changed decisions: 0 (1,223 pass and 79 deny on both). The 1,210 Bash targets in .wuwei/traces.jsonl also gave 0 changes. Replaying the 67 MCP calls from the transcripts (23 create_pull_request, 18 merge_pull_request, the rest reads) gave identical output on both trees. No route a seat uses today is newly refused.
- Real hook entry point: <tree>/bin/wuwei hook PreToolUse with a JSON payload on stdin. The scratch workspace was a git repo on branch x with origin https://github.com/taoq-ai/wuwei.git and a .wuwei plan holding doors-by-rest (light) and other (full). A stub gh on PATH logged every call and answered compare, default branch and pulls/5.
- A1: -X POST, no -X, and 'repos/{owner}/{repo}/pulls' with -f head=x -f base=main all give the same refusal as gh pr create --head x --base main ("taoq-ai/wuwei x opens as a PR once its gates pass ... gates missing at head aaaaaaa: quality").
- A2: -F body=@pr.md (doors-by-rest, light) asks for quality only. -F body=@other.md (other, full) asks for arch, quality, security, goal. --input JSON naming other does the same. So the item comes from the body file.
- A3: gh pr new -t t -b b reaches the create door (compare main...HEAD on an unborn branch).
- A4: -XPUT, --method=PUT, -X=PUT, a ?x=1 query, a trailing / and 'repos/{owner}/{repo}/pulls/5/merge' each call merge_door. The stub log shows api repos/taoq-ai/wuwei/pulls/5 read every time. ccr/auto_merge reaches the same door.
- A5: graphql mergePullRequest, enablePullRequestAutoMerge and createPullRequest are denied, and each reason names gh pr merge or gh pr create. resolveReviewThread, addPullRequestReviewThreadReply and a viewer query pass.
- A6: PATCH git/refs/heads/main, PUT contents/a.md, POST merges and DELETE repos/o/r are all denied.
- A7: MCP push_files with branch main, with no branch, and create_or_update_file with refs/heads/main are all denied as a push to the default branch. Branch x passes. A push_files payload whose tool_input is a list makes the guard raise, and the hook denies it with "names a door and the hook failed".
- A8: gh api repos/o/r/pulls, pulls/5/ccr/review_threads, POST ccr/comments/1/resolve, comment replies, requested_reviewers, PATCH pulls/5, POST issues and the review ping all pass. The route corpus test passes in the suite.
- Shepherd cloud route as charters/shepherd.md:10 writes it (gh api -X POST repos/taoq-ai/wuwei/pulls -f head=x -f base=main -f title='...' -F body=@pr.md), with quality attested at head aaaa... in the scratch ledger: the first call returns the PR-standard note (context, not a deny) and the second passes. The same workspace through main's hook passes every create route with or without gates, which is the escape this item closes.
- The vendored guards.py, shepherd charter and built agent are byte-identical to their sources (cmp). The explain-back in spec.md matches the promise and all nine acceptance scenarios.
- Confidence is high because every acceptance scenario was run through the real hook, and the replay of 2,500+ real commands shows zero moved decisions. A real gh against GitHub (not stubbed) would be the remaining check.

## Residual risk
- A GH_REPO override, --hostname, gh aliases, stdin bodies (-F body=@-, --input -) and graphql queries inside --input JSON are not read. SECURITY.md documents most of these.
