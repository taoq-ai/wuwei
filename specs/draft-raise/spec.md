# Feature Specification: a draft PR opens before its gates, and the flip to ready waits for them

**Feature branch**: `claude/draft-raise`
**Item**: draft-raise, tier full, goal G-2
**Input**: bug #1074. The create door refuses `gh pr create --draft` before the gates pass. On a
repository whose CI runs only on `pull_request`, CI then never runs before the gates, which
contradicts the owner's ruling in #1050 (restated in #1074): open as draft, gate at the draft head
after CI, then flip to ready with reviewers.

## The promise in my words

The raise has three steps, and the doors follow them:

1. Open as draft. A draft create passes before any gate: `gh pr create` or `gh pr new` with
   `--draft` or `-d`, `gh api POST repos/<r>/pulls` whose body carries `"draft": true` (from
   `-F draft=true`, or from the `--input` JSON), and the GitHub MCP `create_pull_request` with
   `draft` true. A create that is not a draft is held as today, and its refusal tells the seat to
   open a draft instead.
2. Gate at the draft head. Nothing changes here: the gates read the pushed head as before.
3. Flip to ready. `gh pr ready` (not `--undo`), `gh api POST repos/<r>/pulls/<n>/ccr/ready_for_review`
   and MCP `update_pull_request` with `draft` false are held until the gates the diff needs pass
   at the PR head. A reviewer request on a draft PR is held the same way: `gh pr edit
   --add-reviewer`, `gh api POST repos/<r>/pulls/<n>/requested_reviewers` and MCP
   `update_pull_request` with `reviewers`. On a PR that is not a draft these pass.

The ready door reads the PR once (`gh.pr`) and runs `create_door` on its head, base and body, so
no gate logic is new. The GraphQL mutation `markPullRequestReadyForReview` joins the refused
mutations, with a pointer to `gh pr ready` or the CCR route. `update_pull_request` joins
`guards.DOORS`, so a guard error on it fails closed. Review pings need no code: `review_duty`
already skips drafts. The charters and docs state the order.

The acceptance scenarios, restated:

1. On a pushed branch with no gates, `gh pr create --draft -t t -F body.md` passes with the PR
   standard note once; without `--draft` it is refused and the reason names `gh pr create --draft`.
2. `gh api -X POST repos/o/r/pulls -f head=b -f base=main -F draft=true` passes; without the draft
   field it is refused as today.
3. MCP `create_pull_request` with `draft` true passes; with `draft` false or absent it is refused.
4. For draft PR 7 with gates missing, `gh pr ready 7`, the CCR ready route and MCP
   `update_pull_request` with `pullNumber` 7 and `draft` false are refused naming the missing
   gates; `gh pr ready 7 --undo` passes.
5. For draft PR 7 with every needed gate passed, `gh pr ready 7` passes.
6. For draft PR 7 with gates missing, `gh pr edit 7 --add-reviewer bob` and the REST
   `requested_reviewers` POST are refused; on a PR that is not a draft they pass.
7. A GraphQL `markPullRequestReadyForReview` mutation is refused with the pointer to `gh pr ready`.
8. The runtime stays at 3,000 lines or fewer, the agents match the charters and the vendored copy
   matches the tree.

## How this fails

1. A non-draft create read as a draft, so a PR opens ready for review before its gates. Ways in:
   `--draft` eaten as the value of a preceding flag (`-t --draft`), a later `--draft=false`, a
   bool value pflag refuses (`--draft=`, `--draft=yes`), `-f draft=true` (gh sends the string
   "true"), `-F draft=True` (also a string), `draft` nested inside the `--input` JSON, or a field
   that gh moves to the query string because `--input` is present. The reader follows pflag and gh
   2.89.0, checked with pflag v1.0.6 and a logging server; every one of these stays held.
2. A ready route missed, so the flip happens before the gates: a full URL or upper-case host, the
   `{owner}/{repo}` placeholder, `--undo=false`, a GraphQL mutation, the MCP tool. The REST route
   rides the existing route table (any host, any case); the GraphQL and MCP routes are listed.
3. A false hold on routine follow-up: `gh pr edit` without reviewers, `gh pr ready --undo`, a
   reviewer request or `gh pr ready` on a ready PR, or a PR read that fails in a cloud session.
   The main-versus-head comparison holds every corpus route, and the new routes are added with
   their sources.

## Clarifications

### Session 2026-10-16

- Q: Does a draft create that also names reviewers (`gh pr create --draft -r bob`, MCP
  `create_pull_request` with `draft` true and `reviewers`) pass? A: No. A reviewer request is what
  the gates must precede (#1050), so such a create meets the create door as a non-draft does.
- Q: Which values make `--draft` true? A: pflag's: `--draft`, `-d`, and `=1`, `=t`, `=T`, `=true`,
  `=TRUE`, `=True`; the last occurrence wins. Any value pflag refuses makes gh exit before it
  creates anything, so it is read as not a draft. Short clusters are unpacked as pflag does (`-fd`
  and `-dt x` are drafts; `-drbob` and `-dr=bob` name a reviewer and are held). Against pflag
  v1.0.6 over 96 argument lists the reader agrees on every one (fix round below).
- Q: What does the reader do with an `--input` body that is not a JSON object? A: Only a body that
  starts with `{` is parsed; a list, plain text or stdin (`--input -`) counts as no draft, and a
  route with no door still passes. A malformed body that starts with `{` raises, so the hook fails
  closed on that call; GitHub would refuse such a body anyway.
- Q: Which REST draft spellings count? A: Only a JSON `true` in the body: `-F draft=true` in any
  flag spelling (gh types exactly `true`), or a top-level `"draft": true` in the `--input` JSON.
  With `--input`, gh moves the fields to the query string, so only the JSON counts. `-f draft=true`
  sends the string "true" and stays held; the reason tells the seat to use `-F`.
- Q: Is a ready or reviewer request on a PR that is not a draft held? A: No. The promise holds the
  flip and the reviewer request on a draft. A PR already ready has nothing to flip, and reviewer
  requests on a ready PR are outside.
- Q: What if the PR cannot be read, or no number is named? A: The door stays shut, as the merge
  door does: it names what it could not read and asks for a number or URL.
- Q: Is `request_copilot_review` a reviewer tool? A: Yes. The item's assumption says a separate
  reviewer tool joins the same check, so it is held on a draft with gates missing, as
  `update_pull_request` with reviewers is.
- Q: Is the GraphQL `requestReviews` mutation refused? A: Yes, beside
  `markPullRequestReadyForReview`: otherwise it requests reviewers on a draft around the door. It
  points to `gh pr edit --add-reviewer`. GraphQL is already refused in cloud sessions.

### Fix round at 8774129

- Q: Which PR and repository does a `gh pr` door read? A: The ones gh reads: one pflag reader
  (`_flags`) skips every value flag's value, so the PR is the first positional word
  (`gh pr edit -t 5 7 --add-reviewer bob` changes PR 7), and the repository is the last `-R`,
  `-Rx/y`, `--repo x/y` or `--repo=x/y`, or the URL's. `gh pr merge` reads `-m` and `-r` as bools.
  The security gate saw real gh 2.89.0 change PR 7 and repository x/y where the old helper read PR
  5 and the origin. `_draft` and `gh api` now use the same reader.
- Q: When does an `--input` file make a draft? A: Only when the gh call is the command's only
  segment. gh reads the file in its own working directory when it runs; after `cd sub &&` or
  `cp f d.json &&` the hook's copy may differ, so such a create meets the create door.
- Q: How is an endpoint matched? A: After the scheme, host and query are removed, percent-escapes
  are decoded and repeated slashes collapse, so `pulls/7//requested_reviewers`, `repos/o//r/...`,
  `requested%5Freviewers` and `pulls/5//merge` meet their doors. The security gate measured that
  GitHub routes those spellings (read-only GETs).
- Q: Which draft values in the `--input` JSON count? A: Only the JSON `true`: `"false"` and `1`
  stay held, and a test pins it.

## Assumptions

- The owner's ruling stands (#1050, restated in #1074 on 2026-10-16). Overturned if the owner
  prefers gates before the PR.
- GitHub MCP server v1.14.0 is the schema: `update_pull_request` takes `pullNumber`, `draft`
  (boolean) and `reviewers` (string array); `create_pull_request` takes `draft` and `reviewers`;
  `request_copilot_review` takes `pullNumber`. Overturned by a server release that renames them.
- The REST ready route is the CCR proxy's `pulls/<n>/ccr/ready_for_review`, as the promise names
  it; GitHub's own REST API has no ready endpoint. Overturned if the proxy names another route.
- Refusing GraphQL `requestReviews` on a PR that is not a draft costs nothing: no charter or skill
  uses it, and `gh pr edit --add-reviewer` does the same. Overturned if a seat needs it.

## Breaking

This changes the Bash and MCP doors, an outward contract, so it is declared breaking (as
doors-by-rest was): commands that passed on main now meet a door. The commit and PR title take a
`!` and a `BREAKING CHANGE:` line.

- Newly held until the gates pass at the PR head, on a draft PR only: `gh pr ready` (not
  `--undo`), a REST POST on `pulls/<n>/ccr/ready_for_review`, MCP `update_pull_request` with
  `draft` other than true, and a reviewer request (`gh pr edit --add-reviewer`, a REST POST on
  `pulls/<n>/requested_reviewers`, MCP `reviewers`, `request_copilot_review`).
- Newly refused on any PR: the GraphQL mutations `markPullRequestReadyForReview` and
  `requestReviews`.
- Newly passing: a draft create before its gates.
- Migration: open the PR as a draft right after the push, run the gates at the draft head once CI
  has run, then `gh pr ready <n>` and request reviewers. Use `gh pr edit --add-reviewer` or the
  REST route instead of GraphQL `requestReviews`. No config or data changes.

## Rollback

Revert the merge commit. The create door then refuses every create before the gates again, and
the ready routes pass unchecked; no state, config or ledger format changes.

## User scenarios

### US1: open as draft before the gates (P1)

Acceptance 1 to 3. Tests in tests/test_guards.py and tests/fixtures/routes.json.

### US2: the flip to ready and reviewers wait for the gates (P1)

Acceptance 4 to 7. Tests in tests/test_guards.py, tests/test_hook.py and tests/fixtures/routes.json.

## Requirements

- FR-001: A draft create (gh, REST, MCP) passes the create door with the PR standard note once; a
  create that names reviewers is not a draft.
- FR-002: A non-draft create is refused as today; the reason names `gh pr create --draft`.
- FR-003: `gh pr ready` (not undo), the CCR ready route and MCP `update_pull_request` with draft
  false are held on a draft PR until its gates pass at the head.
- FR-004: Reviewer requests on a draft PR (`gh pr edit --add-reviewer`, REST
  `requested_reviewers`, MCP `update_pull_request` reviewers, `request_copilot_review`) are held
  the same way.
- FR-005: GraphQL `markPullRequestReadyForReview` and `requestReviews` are refused with a pointer.
- FR-006: `update_pull_request` and `request_copilot_review` are in `guards.DOORS`.
- FR-007: charters/_way.md, builder.md, shepherd.md, docs/design.md and
  docs/site/concepts/doors.md state the order; agents rebuilt; runtime at 3,000 lines or fewer.

## Success criteria

- SC-001: Every acceptance scenario has a test that ran red before the change and green after.
- SC-002: The full suite passes and the main-versus-head comparison moves no verdict outside the
  routes the promise changes.
