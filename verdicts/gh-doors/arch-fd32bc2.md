Verdict: FIX
Gate: arch
Item: gh-doors
PR: taoq-ai/wuwei#1108
Head: fd32bc2b11a23d71f5007e14e67b707f17bd5eaa
Confidence: high
Breaking: yes: Bash commands that passed on main are now refused for every seat and harness: gh api graphql --input -, -F query=@- (and --field/-Fquery= spellings), an --input or -F query=@ file that is missing or empty, such a file inside a pipeline, compound command, wrapper or non-plain words; any POST/PUT/PATCH/DELETE on repositories/<id>/...; gh pr merge --admin=<pflag true> (reached the merge door on main); gh pr merge with --auto read as a value (-t --auto, -b --auto) or turned off by a later --auto=false/0 loses the CI-running exemption.

## Findings
- [medium] SECURITY.md:52 blocks: yes. Failure: SECURITY.md is the published account of what the Bash guards read and refuse, and FR-006 says docs follow; at this head it still lists only "merges, git/refs/, contents/, a repository delete, and a graphql mutation" and says nothing of the three new refusals (graphql query WUWEI cannot read, writes on repositories/<id>, --admin/--auto read through pflag). A security reviewer or client reading it for this declared breaking change sees the old contract. design.md:135 and docs/site/concepts/doors.md:10 are updated; add the same three clauses near SECURITY.md:52 (and the plain-call rule now also governs the graphql --input and -F query=@ file read, near line 56).
- [low] blocks: no. Runtime budget: cli/wuwei is exactly 3000 lines (wc -l; tests/test_setup.py:65 asserts <= 3000). shell-doors as scoped (+5) after ascii-digits (frees about 2 per its own promise, 4 per the brief) lands at 3001 to 3003, so shell-doors must free 1 to 3 lines itself or be re-scoped; this item leaves no slack. Not this item's defect; record it for shell-doors planning.
- [low] blocks: no. specs/gh-doors/spec.md Breaking list omits two moved shapes it covers elsewhere: an empty --input file on graphql (FR-002 and Assumptions name it) and --auto followed by --auto=false or --auto=0 (last-wins now turns the exemption off). Both are door-tightening; migration text already covers them.
- [low] cli/wuwei/guards.py:172 blocks: no. Mutant dropping `path != '-' and` survives every behavior test (only the .claude/ vendor-drift test fails). Not exploitable as far as I can construct: a plain one-segment call has no attacker stdin and any `<` or `|` makes alone false, so unread holds anyway. Missing test: a planted file named `-` with gh api graphql --input -.
- [low] blocks: no. Existing gaps, unchanged by this diff: a full URL with an /api/v3/ prefix (gh api -X PUT https://api.github.com/api/v3/repositories/123/pulls/5/merge passes, as does the repos/ form on main) and a GHES api/graphql endpoint are not matched; harmless against api.github.com, which 404s that prefix.
- [low] blocks: no. Fit: the change reuses guards._flags with merge's valued set (one `valued` shared with _repo_number), TRUE for pflag's spellings, and the existing alone plain-word rule; no new door, config key or dependency. The beyond-promise choice to put -F query=@file under the plain-call rule is recorded under Clarifications and in Breaking/Migration with its cwd reason (cd sub && ... reads sub/q.graphql), and it is a two-way door. Dropping the len(segments(command))==1 clause is sound: a multi-line command naming gh is refused upstream (probe below), and ; | & < > fail the plain-word regex.

## Probes
- git archive fd32bc2 and 23625f3 into scratch; full suite at head: 1009 passed, 2 skipped (pytest -q).
- Newline file-swap probe (gh auth status / cp evil.json q.json / gh api graphql --input q.json, and the -F query=@ form): refused at head and base by the multi-line rule, so FR-005 removes a redundant clause only.
- Probe at head vs base: gh api graphql --input evil.json (mergePullRequest) refused at head, passed on base; --input - via -X POST graphql, /graphql/, GraphQL, https://api.github.com/graphql all refused at head, passed on base; -XPUT ./repositories/123/..., repositories%2F123/... refused at head, passed on base; gh api graphql -f query=@q.json and REST --input - to issues comments still pass.
- Mutants (each in a fresh git archive copy, tests/test_guards.py): unread guard negated 38 fail; repositories WRITE guard negated 13 fail; on('admin') negated 62 fail; auto reverted to '--auto' in args 4 fail; path != '-' removed survives (re-run in a fresh copy, full suite: only the vendor-drift test fails).
- Routes: grep of charters/, skills/, agents/ and 3,455 rows of .wuwei/traces.jsonl finds no gh api graphql --input, -F query=@, repositories/ write, --admin, or -t --auto route; shepherd.md uses gh pr merge <n> --auto and repos/<owner>/<repo>/... only. routes.json pre-existing rows keep their verdicts (suite green).
- .claude/wuwei/cli/wuwei/guards.py is byte-identical to cli/wuwei/guards.py at head.
- Confidence high: the code fits the design and every route probe agrees; the one block is a doc omission with a known fix.

## Residual risk
The merge flag read depends on VALUED | PR_VALUED matching gh's merge value flags; a new gh bool flag listed as valued would swallow --admin (spec How this fails 2). The runtime has zero slack for shell-doors.
