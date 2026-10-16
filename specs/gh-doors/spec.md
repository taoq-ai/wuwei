# Feature Specification: gh api graphql queries WUWEI cannot read, repositories/<id> writes, and merge flags read the way gh reads them meet the doors

**Feature branch**: `claude/gh-doors`
**Item**: gh-doors, tier full, goal G-2
**Input**: on main fe5bc0b `guards.bash` passed `gh api graphql --input q.json` carrying
`markPullRequestReadyForReview`, `gh api graphql --input -`, and `gh api -X POST
repositories/123/pulls/5/requested_reviewers`, `-X PUT repositories/123/pulls/5/merge` and
contents writes. Real gh 2.89.0 sends each of them. `gh pr merge` read `--auto` and `--admin` from
raw argv.

## The promise in my words

Allow the plain shapes WUWEI can read; never chase spellings.

1. `gh pr merge` reads `--admin` and `--auto` the way pflag does, through `guards._flags` with
   merge's value flags. `--admin`, and `--admin=` with any value pflag reads as true, is refused.
   `--auto` counts only where pflag reads it as the flag: in `gh pr merge 5 -t --auto` it is the
   subject, so the CI-running exemption does not apply. The last `--auto` wins; `--auto=false` is
   off.
2. A `gh api graphql` call is refused when its query could carry a write WUWEI cannot read:
   `--input -`, `-F query=@-`, an `--input` or `-F query=@` file that is missing, or such a file in
   a command that is not one plain `gh` call. An `--input` file WUWEI reads has its query checked
   for door mutations, like `-f query=`.
3. Any write method to an endpoint starting `repositories/` is refused with a hint to spell
   `repos/<owner>/<repo>/...`. Reads pass.
4. The redundant `len(segments(command) or ()) == 1` clause goes.

Out of scope: shell parsing (shell-doors), `ready_door` comparing the branch by name for fork PRs,
repository settings that auto-request reviewers, `?draft=false` on a POST.

The acceptance scenarios, restated:

1. `q.json` holds a `markPullRequestReadyForReview` mutation. Real gh sends it as POST /graphql;
   `guards.bash` refuses `gh api graphql --input q.json` naming the mutation.
2. Real gh sends stdin as POST /graphql for `--input -`. `guards.bash` refuses `--input -` and
   `-F query=@-` as a query WUWEI cannot read; `gh api graphql -f query=@threads.graphql -F
   number=5` still passes (gh sends `@threads.graphql` as the literal query).
3. Real gh sends `POST /repositories/123/pulls/5/requested_reviewers`. `guards.bash` refuses it,
   `-X PUT repositories/123/pulls/5/merge` and `-X PUT repositories/123/contents/x`, each naming
   `repos/<owner>/<repo>`; `gh api repositories/123` passes.
4. PR 5 with only `CI running`: `gh pr merge 5 -t --auto` is refused, `gh pr merge 5 --auto`
   passes, `gh pr merge 5 --auto=false` is refused.
5. `gh pr merge 5 --admin=true` and `--admin=1` are refused as `--admin`.
6. Every pre-existing row in `tests/fixtures/routes.json` keeps its verdict; new rows hold the
   shapes above.

## Clarifications

### Session 2026-10-16

- Q: Does `-f query=@file` read a file? A: No. Real gh 2.89.0 sent `{"query":"@threads.graphql"}`
  and `{"query":"@-"}`: only `-F` reads `@`. So `-f query=@-` passes.
- Q: Which `-F` fields count? A: Only `query`. Other `-F` fields are GraphQL variables; a variable
  cannot carry a mutation.
- Q: Does the plain-call rule cover `-F query=@file` too? A: Yes. `cd sub && gh api graphql -F
  query=@q.graphql` makes gh read `sub/q.graphql` while WUWEI reads `./q.graphql`. The promise
  names the rule for `--input`; the same cwd gap holds for `-F query=@`, at no extra line.
- Q: How is the `--input` file's query read? A: The whole file, with JSON `\u` escapes decoded,
  is checked for door mutations. gh sends the file as is and GitHub decodes the escapes, so
  `markPullRequestReadyForReview` is the same mutation. A batch array is covered too.
- Q: Does the head, base and body read of an `--input` file change? A: No. It stays as on main,
  read in any command; only the query check needs the plain one-call rule.
- Q: Is a file named `-` read? A: No. gh reads `-` as stdin, so `_read` answers blank for it.

## How this fails

1. A seat pipes a read-only GraphQL query from a file (`gh api graphql --input q.json | jq`) and
   is refused. The refusal says to pass `-f query=...`; no seat route in the corpus or the traces
   uses `--input` on graphql, so the cost is one rewrite.
2. A future gh adds a merge value flag `_flags` does not know. pflag would then read `--admin`
   after it as its value while WUWEI reads it as the flag, which refuses more, never less; the
   reverse (a new bool flag WUWEI reads as valued) would let `--admin` through. The pflag mirror
   check and the merge flag list in `VALUED | PR_VALUED` are where to look.
3. A seat names a repository by id for a write it needs (`repositories/<id>/issues/5/comments`)
   and is refused. The hint names the `repos/<owner>/<repo>` spelling, which reaches the same
   endpoint.

## User scenarios

### US1: a GraphQL write WUWEI cannot read never passes (P1)

Acceptance 1, 2. Tests in `tests/test_guards.py`:
`test_a_graphql_input_file_has_its_query_read_for_door_mutations`,
`test_a_graphql_query_wuwei_cannot_read_is_refused`,
`test_a_graphql_query_wuwei_reads_with_no_door_mutation_passes`.

### US2: a write by repository id meets the doors (P1)

Acceptance 3. Tests: `test_a_write_to_a_repositories_id_endpoint_is_refused_naming_the_repos_spelling`,
`test_a_read_of_a_repositories_id_endpoint_passes`.

### US3: merge flags read as gh reads them (P1)

Acceptance 4, 5. Tests: `test_merge_reads_auto_the_way_pflag_does`,
`test_merge_refuses_admin_in_every_spelling_gh_reads_as_true`,
`test_merge_reads_a_false_or_swallowed_admin_as_off`.

### US4: the route corpus holds (P1)

Acceptance 6. `test_every_route_reads_as_recorded` with 11 new rows.

## Requirements

- FR-001: `gh pr merge` reads `--admin` and `--auto` through `_flags` with merge's value flags;
  the last occurrence wins; true values are pflag's.
- FR-002: `gh api graphql` with `--input -`, `-F query=@-`, a missing or empty file, or a file in a
  command that is not one plain `gh` call is refused as unreadable.
- FR-003: a readable `--input` file on graphql has its whole text, `\u` escapes decoded, checked
  for door mutations.
- FR-004: any write method on an endpoint under `repositories/` is refused naming
  `repos/<owner>/<repo>`; reads pass.
- FR-005: the `len(segments(command) or ()) == 1` clause is removed.
- FR-006: routes.json gains a row per new shape naming its source; docs and `.claude/` follow.

## Breaking

Commands that passed on main and are now refused:

- `gh api graphql --input -`, `-F query=@-`, `--input <missing file>`.
- `gh api graphql --input <file>` or `-F query=@<file>` inside a pipeline, a compound command, a
  wrapper or with quoted or non-plain words.
- Any POST, PUT, PATCH or DELETE on `repositories/<id>/...`.
- `gh pr merge --admin=true` (and `1`, `t`, `T`, `TRUE`, `True`) reached the merge door on main and
  is now refused outright.
- `gh pr merge <n> -t --auto` (and other spellings where `--auto` is a value) lose the CI-running
  exemption.

Migration: pass a GraphQL query by `-f query='...'`, or by `--input <file>` or `-F
query=@<file>` in its own one-line `gh api graphql` call with plain words. Spell REST endpoints
`repos/<owner>/<repo>/...`. Put `--auto` where pflag reads it as the flag. No seat route in
`tests/fixtures/routes.json` changes its verdict.

## Assumptions

- No seat route uses `gh api graphql --input` or `-F query=@` outside a plain call (none in
  `.wuwei/traces.jsonl` or routes.json, per the item). Overturned if a seat trace shows one.
- An empty `--input` file counts as unreadable. gh sends an empty body, which carries no write;
  refusing it costs nothing a seat needs. Overturned if a seat route posts an empty graphql body.
- The change is breaking by the rule "routes that passed on main now refused", though every moved
  shape is a door bypass. Overturned if the owner reads the guard's refusals as outside the
  outward contract.

Rollback: revert the commit; no data, config or schema changes.
