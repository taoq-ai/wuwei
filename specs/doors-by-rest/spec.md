# Feature Specification: every code-host route to a door meets that door

**Feature branch**: `claude/doors-by-rest`
**Item**: doors-by-rest, tier full, goal G-2
**Input**: `guards.gh_command`'s api branch read only `-X PUT` and `--method PUT` and a bare
`repos/<o>/<r>/...` endpoint, so `-XPUT`, `--method=PUT`, a leading `/`, a query string or gh's
`{owner}/{repo}` placeholder walked past the merge door, and a REST or GraphQL pull request
create, branch write or merge reached no door at all.

## The promise in my words

The Bash door reads a `gh api` call the way gh's own flag parser does: the method from `-X PUT`,
`-XPUT`, `-X=PUT`, `--method PUT` or `--method=PUT` (upper-cased; POST when a field or `--input`
is given and no method is), the endpoint with a leading `/`, a trailing `/` and a query removed,
and `{owner}`/`{repo}` filled from the origin remote. The fields come from `-f`, `-F`,
`--raw-field` and `--field` in every spelling, with `-F key=@file` read from the file, and from
the JSON object in the `--input` file.

One route table then decides:

- POST `repos/<r>/pulls` goes to the create door, with head and base from the fields and the body
  from the fields (so `-f body=`, `-F body=@file` and `--input` all count), as `gh pr create` does.
- PUT `repos/<r>/pulls/<n>/merge` and `.../ccr/auto_merge` go to the merge door.
- A write method on `repos/<r>/merges`, `repos/<r>/git/refs/...` or `repos/<r>/contents/...` is
  refused like a push to the default branch; DELETE `repos/<r>` is refused like `gh repo delete`.
- The protection, ruleset, status, collaborator, hook, key, secret and environment writes stay
  refused as before.

`gh api graphql` whose query names a merge, auto-merge, create-PR, ref, commit-on-branch, branch
protection or ruleset mutation is refused and points at `gh pr merge` or `gh pr create` (or the
REST create route). `gh pr new` is read as `gh pr create`. The GitHub MCP tools `push_files`,
`create_or_update_file` and `delete_file` join `guards.DOORS` under `push`: on the default branch,
or with no branch, they are refused like a push to it, and a guard error on them fails closed.
The shepherd charter names the cloud create route; SECURITY.md says what the api reader covers.

The acceptance scenarios, restated:

1. A REST PR create with `-X POST`, without `-X`, and through `repos/{owner}/{repo}/pulls`, at a
   head with gates missing, is refused exactly as `gh pr create` for that head and base is.
2. A REST create with `-F body=@pr.md` reads the item from pr.md.
3. `gh pr new -t t -b b` reaches the create door.
4. `-XPUT`, `--method=PUT`, a query string and `{owner}/{repo}` on `pulls/5/merge` all reach the
   merge door for PR 5.
5. GraphQL `mergePullRequest`, `enablePullRequestAutoMerge` and `createPullRequest` mutations are
   refused and the reason names `gh pr merge` or `gh pr create`.
6. PATCH on `git/refs/heads/main`, PUT on `contents/a.md`, POST on `merges` and DELETE on the
   repository are refused.
7. MCP `push_files` with branch main is refused like a push to the default branch, and is refused
   when the guard raises on it.
8. `gh api repos/o/r/pulls`, the CCR review-thread read and the CCR resolve POST pass, and every
   other route in tests/fixtures/routes.json reads as recorded.
9. The runtime stays at 3,000 lines or fewer.

## How this fails

1. A false refusal of a route the shepherd needs in a cloud session (the CCR review-thread read,
   the CCR comment resolve POST, a reply POST, a graphql `resolveReviewThread`), which would stop
   every PR follow-up. The route table matches whole endpoints (`fullmatch`), the mutation list is
   searched only in the graphql `query` field, and the corpus plus a main-versus-head comparison
   over 153 commands hold these routes.
2. A misread flag cluster: `-iXPUT`, `-fhead=x` or `--field=head=x` read as a positional, so the
   endpoint becomes a flag value or the method stays GET and a merge passes. The reader follows
   gh's parser (pflag), and each spelling was checked against gh 2.89.0 sending to a logging proxy.
3. The create door reads the wrong body or branch: `-f body=@pr.md` is literal in gh (only `-F`
   reads a file), and the JSON in `--input` holds head, base and body. Reading these differently
   from gh would let a PR open with an item the gates never saw, or refuse a ready one.

## Clarifications

### Session 2026-10-16

- Q: Is a write on `contents/` or `git/refs/` refused only on the default branch, as the MCP tools
  are? A: Every write method on those routes and on `merges` is refused, as the promise lists them
  without a branch condition. Seats push with git, which the push door already reads per branch;
  no charter or skill writes a branch through REST. The reason says "like a push to the default
  branch" and points to a branch and a PR.
- Q: How is the method read when it is given twice? A: The last one wins, as in pflag.
- Q: Which graphql mutations are refused? A: The promise's list (mergePullRequest,
  enablePullRequestAutoMerge, createPullRequest, updateRef and updateRefs, deleteRef,
  createCommitOnBranch, the create, update and delete BranchProtectionRule and RepositoryRuleset
  mutations), plus mergeBranch and enqueuePullRequest, which merge a branch or a PR by the same
  route and have no seat use. resolveReviewThread and addPullRequestReviewThreadReply pass.
- Q: Is `-F query=@file` read? A: The promise puts it outside. The field reader reads every
  `-F key=@file` the way gh does, so a query in a file is searched too; nothing more is promised
  and no route depends on it.
- Q: Does the REST create route get the once-per-session PR standard note? A: Yes. It shares the
  `gh pr create` path after the door, so a ready REST create gets the same note.
- Q: What head does a REST create without `head=` use? A: The current branch, as `gh pr create`
  does; GitHub would refuse the call anyway.
- Q: Does a full URL (`https://api.github.com/repos/...`) count? A: Yes, gh accepts it and the
  reader strips that prefix.

## Assumptions

- Refusing every REST write on `contents/`, `git/refs/` and `merges` costs no seat a route (no
  charter, skill or workspace command uses one). Overturned if a seat needs a REST branch write
  where git push is unavailable.
- gh's flag spellings are read as gh 2.89.0 reads them (checked with a logging proxy). Overturned
  by a gh release that changes pflag's short-flag or `--input` handling.
- A body or head given on stdin (`--input -`, `-F body=@-`) is not read: the create door then
  checks the current branch with no named item, so it refuses rather than passes when gates are
  missing. Overturned if a seat needs stdin bodies; it can write the file with Write instead.

## User scenarios

### US1: a REST or GraphQL route to a door meets that door (P1)

Acceptance 1 to 6 and 8. Tests in tests/test_guards.py and tests/fixtures/routes.json.

### US2: the MCP file tools meet the push door (P1)

Acceptance 7. Tests in tests/test_guards.py and tests/test_hook.py.

## Requirements

- FR-001: `gh api` method, endpoint and fields are read as gh reads them.
- FR-002: One route table sends REST create to create_door, merge and auto-merge to merge_door,
  branch writes and repository delete to a refusal, and keeps the protection writes refused.
- FR-003: graphql mutations on merges, PR creation, refs, commits and protection are refused.
- FR-004: `gh pr new` reads as `gh pr create`.
- FR-005: MCP push_files, create_or_update_file and delete_file are in `guards.DOORS` and refused on
  the default branch or with no branch.
- FR-006: charters/shepherd.md names the REST create route; agents/ rebuilt; SECURITY.md updated.
- FR-007: Runtime at 3,000 lines or fewer; every corpus route reads as recorded.

## Success criteria

- SC-001: Every acceptance scenario has a test that ran red before the change and green after.
- SC-002: The full suite passes and the main-versus-head comparison shows no moved verdict outside
  the routes the promise changes.
