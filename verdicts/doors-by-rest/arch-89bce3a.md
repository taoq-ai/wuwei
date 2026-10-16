Verdict: PASS
Gate: arch
Item: doors-by-rest
PR: taoq-ai/wuwei
Head: 89bce3a98208859ba6cdeea27a52eaaf56340890
Confidence: high
Breaking: yes: commands that passed on main now meet a door or a refusal in every existing session. Newly refused: (1) gh api POST/PUT/PATCH/DELETE on repos/<o>/<r>/contents/<path>, repos/<o>/<r>/git/refs/<ref> and repos/<o>/<r>/merges, on any branch, including deleting a feature branch with gh api -X DELETE .../git/refs/heads/<b>, which git push origin --delete <b> still allows; (2) gh api -X DELETE repos/<o>/<r>; (3) gh api graphql whose query names mergePullRequest, enablePullRequestAutoMerge, createPullRequest, updateRef(s), deleteRef, createCommitOnBranch, mergeBranch, enqueuePullRequest or any BranchProtectionRule or RepositoryRuleset name, refused even when the PR has no gaps or is gated, and even in a read query that uses one as a fragment type; (4) GitHub MCP push_files, create_or_update_file and delete_file on the default branch or with no branch. Newly checked: (5) REST pull request creates (POST repos/<o>/<r>/pulls) and gh pr new meet the create door and are refused until the gates pass at the head; (6) REST merge and auto-merge spellings meet the merge door: -XPUT, --method=PUT, an empty attached flag value before the method, a leading slash, a query string, a full URL with any scheme, host or case, and {owner}/{repo}. Migration: push branches with git, open PRs with gh pr create or gh api -X POST repos/<owner>/<repo>/pulls once the gates pass, merge with gh pr merge or the REST merge route

## Findings
- [low] blocks: no. Closed: my bf5ae3a blocking finding (docs/design.md section 7 and docs/site/concepts/doors.md kept the old closed list). At 89bce3a both list every route this item adds: REST creates, gh pr new, the REST merge spellings, REST writes to merges, git/refs and contents on any branch, REST repo delete, the GraphQL mutations and the MCP file tools. specs/doors-by-rest/spec.md:104-119 records the break and its migration, and the commit is fix(guards)! with a BREAKING CHANGE footer.
- [low] cli/wuwei/guards.py:34 blocks: no. An empty attached short value (-X=) is read as the value "=" where gh reads "". It still does not consume the next argument, and a later -X still wins, so no route moves. gh sends an empty method as GET.
- [low] blocks: no. Carried notes from bf5ae3a, unchanged by the delta: gh api graphql --input <file>, repositories/<id>/pulls/<n>/merge and a doubled-slash endpoint are not read (branch protection is still the wall there); a branch rename and a default_branch change by REST sit outside every door; the runtime is at 2,996 of 3,000, so draft-raise at an estimated +15 must free at least 11 lines first.

## Probes
- Delta bf5ae3a..89bce3a: guards.py changes API_FLAG so only an empty attached short value is ignored, _api's value consumption, a host strip that removes any scheme://host[:port] in any case, re.I in route matching, and .lower() on the auto_merge test. The rest is docs, spec, tests and 11 corpus routes. The vendored guards.py is byte-identical (cmp).
- Runtime: cat cli/wuwei/*.py | wc -l gives 2996 at the head.
- Suite at the head in a git archive copy: 682 passed, 2 skipped.
- probe2.py through _api: -X= -X PUT, -X=PUT, -XPUT and -iX PUT read PUT; a trailing -X and --method= consume nothing; HTTPS://API.GITHUB.COM:443/Repos/O/R/Pulls/5/MERGE reaches the merge route under re.I; a GET on contents/README.md and -q .x still read as GET.
- probe.py, rerun at the head: the shepherd's cloud create route still reaches create_door with repo o/r, head br, base main and the item read from the body file. The CCR resolve POST, an issue comment and update-branch still pass.
- Mutant: restoring the old =? in API_FLAG and dropping re.I together failed 13 tests in test_guards, including the -q= create and -X= graphql corpus routes.
- re.I applies only on the refusing side: every API row is a door or a refusal, so case-insensitivity can only send more calls to a door.

Confidence is high: the delta is small, probes and mutants back it, and the docs and spec now match the code.

## Residual risk
The breaking refusals depend on no seat needing a REST branch write where git push is unavailable. The PR still needs its Announcement link and the owner's breaking: confirmation, which are safety gaps for the merge door rather than for this gate.
