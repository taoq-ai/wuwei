# Feature Specification: why reads local state only and doctor caps its network probes

**Feature Branch**: `867-github-fanout`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #867: "fix(cli): why reads local state only and doctor caps its
network probes", with the owner's field comments of 2026-10-12.

## What happened

On 0.28.0 (three repositories, 11 to 13 seats) the owner's shared gh login emptied GitHub's
REST core quota (5000 an hour) twice before 08:00 UTC. Builder seats reported `wuwei doctor`
and `wuwei why <item>` taking 100 to 120 s. The refusal text read "GitHub rate limit until
07:51:41 UTC (4989 of 5000 graphql calls left)" while GitHub's headers said
`X-RateLimit-Resource: core`, remaining 0, reset 07:55:41; the owner retried at the printed
time and was refused again. A contributor found that plan propose lists every open PR of
every configured repository (195 PRs) to find the owner's 2.

## Root causes

1. `adapters/_http.py` `gh_limit` (line 75): after a gh call fails with "rate limit", it reads
   `gh api rate_limit` and reports whichever of `core` and `graphql` has fewer calls left,
   not the resource the failed call used. A REST call under a secondary limit prints the
   graphql counter, and a GraphQL call prints core's reset when core is the emptier bucket.
   A counter above zero means a secondary limit, but the text does not say so.
2. `adapters/_http.py` `retry` (line 93) and `cap` (line 66): every gh call waits up to
   `host.rate_limit_wait_seconds` (120 s) for a reset, then retries once. Doctor runs about a
   dozen GitHub calls, so a limit that resets within two minutes holds doctor for up to two
   minutes: the 100 to 120 s builders saw.
3. `cli/wuwei/commands/config.py` `run` (line 104) and `_protection` (line 433): `config
   check`, which doctor's "config check" row runs, reads branch protection for every
   configured repository on every run: three calls per repository (classic protection, the
   rulesets page, the repository record), nine for three repositories. Every seat that runs
   doctor pays them again, although protection does not change during a day.
4. `cli/wuwei/commands/doctor.py` `_gates` (line 392): a rate-limited protection read makes
   the config check row `unmeasured`, not `waiting`, so the owner reads a broken check.
5. `adapters/code_host/github.py` `open_prs` (line 381) pages
   `repos/<repo>/pulls?per_page=100` for every open PR of the repository, and
   `cli/wuwei/plan.py` `_owner_prs` (line 229) keeps only the owner's. On 2026-10-12 that was
   195 PRs in four pages for 2 owner PRs.
6. `cli/wuwei/commands/why.py`: `why` makes no network call today. It reads the day records
   only (`watch.days`, `watch.records`, `state.read_state`). The 100 to 120 s builders saw for
   `why` came from outside the command: the PreToolUse scanner path that #880 removed from the
   builder loop, and a machine loaded by a dozen seats. This feature pins the local read with
   a test so it stays that way.

## User Scenarios & Testing

### User Story 1 - the rate-limit message names the empty bucket (Priority: P1)

A gh call fails on a rate limit. The reason names the resource that call spends (core for
REST, graphql for GraphQL and `gh pr merge` or `ready`, search for search) and that
resource's reset. When that resource still has calls left, the reason says it is a
secondary limit.

**Acceptance Scenarios**:

1. **Given** a REST read refused with core at 0 and graphql at 4989, **Then** the reason is
   "GitHub rate limit until <core reset> UTC (0 of 5000 core calls left); retry after it".
2. **Given** a REST read refused while core has 4990 left, **Then** the reason names a
   secondary limit and the core counter, with a reset one minute out.
3. **Given** a GraphQL read refused with graphql at 0 and core at 4000, **Then** the reason
   names graphql and graphql's reset.

### User Story 2 - doctor finishes in seconds when GitHub is rate limited (Priority: P1)

**Acceptance Scenarios**:

1. **Given** GitHub refuses every call with a rate limit whose reset is 100 s away, **When**
   doctor runs, **Then** no GitHub call waits for the reset; the gh and config check rows are
   `waiting` with the reset, and doctor exits 2.
2. **Given** the config check's protection read is rate limited, **Then** the config check row
   is `waiting`, not `unmeasured`.

### User Story 3 - protection is read once a day (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a clean protection read today, **When** doctor or `config check` runs again the
   same day, **Then** it makes no protection call for that repository and branch.
2. **Given** a protection read with findings, **When** the owner fixes the branch settings and
   runs doctor again, **Then** protection is read again (findings are never cached).

### User Story 4 - plan propose asks GitHub for the owner's PRs only (Priority: P2)

**Acceptance Scenarios**:

1. **Given** three repositories and one owner login, **When** plan propose runs, **Then** it
   makes one search call per repository and login
   (`is:pr is:open repo:<repo> author:<login>`) and adopts the PRs it returns, as before.
2. **Given** a search whose total count exceeds the rows it returned, or that GitHub marks
   incomplete, **Then** the read fails closed (unmeasured), as a truncated page does today.

### User Story 5 - why stays local (Priority: P3)

**Acceptance Scenarios**:

1. **Given** a workspace with `code_host = "github"`, **When** `wuwei why <item>` runs with
   every adapter load and subprocess refused, **Then** it prints the item's chain and exits 0.

### Edge Cases

- No workspace: doctor still never waits (the wait cap is set for the process).
- A protection cache file that is unreadable or holds another shape is ignored and protection
  is read again.
- A login outside GitHub's login shape is refused before any call.

## Requirements

- **FR-001**: `gh_limit` reports the resource the failed call spends and that resource's
  counters and reset; with calls left it reports a secondary limit with a one-minute reset.
- **FR-002**: The rate-limit text says "secondary limit" whenever the named resource has
  calls left, on the gh path and the header path alike.
- **FR-003**: Doctor never waits for a rate-limit reset; a limited call returns at once and
  its row reads `waiting`.
- **FR-004**: The config check row is `waiting` when its output names a GitHub rate limit
  and no protection finding ("missing (") is due; a finding keeps the row `unmeasured` with
  its detail lines.
- **FR-005**: `config check` keeps each clean protection read in the day directory
  (`protection.json`, keyed `<repo>@<branch>`) and reuses it that day; reads with findings or
  errors are not kept.
- **FR-006**: The code host port's `open_prs` takes `(repo, author)` and returns that
  author's open PRs from one server-side search; plan propose calls it once per repository
  and owner login that can be a GitHub login (never a chat ID), plus
  `outbound.owner.code_host`.
- **FR-008**: A rate-limited gh read names the bucket and reset from the failed response's own
  headers; `gh api rate_limit` is the fallback when no headers come back.
- **FR-007**: `why` stays a local read (a test refuses every adapter load and subprocess).

## Success Criteria

- **SC-001**: the acceptance of #867: `why` completes with no network (FR-007 test), and
  doctor under a rate limit completes with no wait, reporting the GitHub rows as waiting
  (test with a fixed clock: zero seconds slept).
- **SC-002**: doctor's GitHub calls per run for three repositories drop from about 13 to
  about 4 after the first clean run of the day.
- **SC-003**: plan propose's PR listing for the owner's workspace drops from 4 paged core
  calls carrying 195 PRs to 3 search calls carrying the owner's PRs.

## Assumptions

- Review fix round (F1 residual): the limit is read from the failed response's own
  `X-RateLimit-Resource`, `-Remaining` and `-Reset` headers, which gh prints only with
  `--include`. A read already run with `--include` (conditional reads, token scopes) parses
  its own reply. After a primary limit (never a secondary one, which GitHub says to wait
  out and another request can extend: delta D1), any other read (a REST GET or a GraphQL
  query) is asked once more with
  `--include` and no pagination: a refused request spends no quota, and the reply carries the
  same bucket. `gh api rate_limit` is read only when no such headers come back. Calls that
  cannot expose headers fall back to `rate_limit` for their own resource: writes (never
  repeated: POST, DELETE, the revert mutation), `gh pr merge`, `gh pr ready`, `gh auth
  status`, and the GitHub tracker's `gh api graphql` (`adapters/tracker/github.py` `_gh`,
  whose queries include mutations). The tracker's token path already reads the headers
  (`_github_limit`).
- GitHub's search index lags a new PR by seconds to about a minute, so a PR the owner opened
  just before plan propose can be missing from the claims, with no sign in that run (review
  F3). The next propose picks it up, or the owner claims it with `wuwei pr claim`.
- Only owner handles that can be GitHub logins are searched (review F1): chat IDs
  (`[UW][A-Z0-9]+`, checked before casefold) and handles outside `[A-Za-z0-9][A-Za-z0-9-]*`
  are skipped, because GitHub search answers 422 for an unknown author and one failed search
  would make the whole sweep unmeasured. `outbound.owner.code_host` is always searched.
- Doctor's no-wait reaches the adapters through the environment variable
  `WUWEI_RATE_LIMIT_WAIT` (seconds), which `_http.cap` honours before the config value; the
  CLI never imports an adapter module, and the adapters read their wait from the workspace.
- Review-requested PRs are not fetched: no consumer in plan propose, discovery or derive reads
  them today (plan propose adopts the owner's own PRs). The day's raised and claimed PRs are
  already read by reference (discovery) and through the per-round listing (`derive.refresh`).
- The planner-side snapshot the owner asked for already exists: `derive.refresh` writes the
  day's `prs.json`, and every seat's `next` reads it until it is older than
  `pr.poll_seconds`. No second snapshot is added.
- Doctor runs no scanner; nothing to cache there.
- Protection cached clean for the day means a regression made during the day shows in doctor
  the next day. The merge policy and the shepherd read protection live, so no decision uses
  the cache.

## Deferred

- `merge.poll` (`cli/wuwei/merge.py` `poll`, line 726) reads every merge-journal PR merged in
  the last 28 days on each listing refresh: about 5 core calls per PR every
  `pr.poll_seconds`. With many auto-merges in the window this is the largest per-round core
  cost WUWEI itself makes. A follow-up issue should poll a merged PR only until its outcome
  is recorded and at a slower cadence.
- Seats' own gh polling (for example `gh pr checks --watch`) is outside the CLI and was not
  measured; it likely made most of the 07:32 to 07:52 burn.
