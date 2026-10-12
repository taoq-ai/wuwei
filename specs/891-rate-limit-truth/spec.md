# Feature Specification: a rate limit refusal names the bucket only when gh api rate_limit confirms it

**Feature Branch**: `891-rate-limit-truth`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #891: "pr act refuses on '0 of 5000 core calls left' while gh api
rate_limit shows the core bucket full"

## What happened

On 0.29.0 `pr act` refused three PRs with `github.pr: could not run: GitHub rate limit until
11:55:45 UTC (0 of 5000 core calls left)`. In the same minute, with the same token, `gh api
rate_limit` showed core 5000 of 5000 with a reset an hour out. A minute later the refusal came
back with the same 11:55:45. Every PR command was blocked while the quota was full.

## Root cause

#867 (PR 885) made the failed reply's own `X-RateLimit-*` headers decide the bucket. In 0.29.0,
`_run` (`adapters/code_host/github.py:127`) calls `_headers_limit` before `gh_limit`. For a read
whose stderr says "rate limit" without "secondary", `_headers_limit` (`github.py:184-191`) asks
GitHub again with `--include`, and `included_limit` hands the headers to `_github_limit`
(`adapters/_http.py:149-150`). That function raises "0 of 5000 core calls left" until
`X-RateLimit-Reset` whenever `X-RateLimit-Remaining` is 0, and `gh api rate_limit` is never read.

Why the refused reply and rate_limit disagree is unproven. In #867 the header reset turned
out true; here it held steady across retries and gh printed the primary wording, which fits a
real counter for some token as well as a limit other than the bucket. The message can come only
from the header path (`gh_limit` would have read rate_limit and found calls left). Nothing is
persisted: each `pr act` asked GitHub, was refused, asked again and read the same header reset.
So the fix guesses neither way: it names both readings and the likely cause to check (a
different token for WUWEI and the owner's gh).

## User Scenarios & Testing

### User Story 1 - a full bucket is never reported empty (Priority: P1)

**Independent Test**: replay a `gh api repos/.../pulls/N` that fails with GitHub's primary
wording while `gh api rate_limit` shows core 5000 of 5000; `pr act` prints a secondary limit on
that endpoint.

**Acceptance Scenarios**:

1. **Given** gh's primary wording and a rate_limit row with calls left, **When** a gh call is
   refused, **Then** the reason names both readings (the refused endpoint and gh's wording, the
   refused reply's X-RateLimit headers when an `--include` read holds them, and rate_limit's
   calls left and reset), says to check that WUWEI and gh use the same token, waits 60 s, and
   the read is not asked again.
2. **Given** a refused `--include` read that carries `Retry-After: 30`, **When** rate_limit has
   calls left, **Then** the reset is now + 30 and the reason names `Retry-After 30 s`.
3. **Given** the rate_limit row for the call's resource at 0, **When** a call is refused,
   **Then** the reason is `0 of M <resource> calls left` until that row's reset.
4. **Given** a search endpoint, **When** it is limited, **Then** the reason names `search`,
   never the query.

## Requirements

- **FR-001**: The bucket and reset come from `gh api rate_limit` for the resource the call
  spends. A failed reply's `X-RateLimit-Remaining` and `X-RateLimit-Reset` never decide them.
- **FR-002**: "Secondary limit" is said only when gh's text says secondary or GitHub sent
  Retry-After; it is waited for Retry-After, else one minute. With the primary wording and calls
  left, both readings are named (FR-001 scenario 1) and the wait is one minute.
- **FR-002a**: Every word in the reason is fixed text or a number; gh's primary wording is
  matched, never echoed.
- **FR-003**: A failed call is never asked again to read headers.
- **FR-004**: A refusal names a rate limit only when gh's stderr says so (unchanged).
- **FR-005**: #867 guarantees hold: doctor never waits, no extra request after a secondary
  limit, one retry within the cap.

## Success Criteria

- **SC-001**: The #891 replay names both readings and the token hint, never calls it a
  secondary limit, and makes two gh calls (the read and rate_limit).

## Assumptions

- GitHub's `rate_limit` endpoint is the truth for a token's buckets. It costs no quota. The
  same `env` is passed to it as to the failed call, so it answers for the same identity.
- For a secondary limit without Retry-After, GitHub's guidance is to wait at least a minute.
- Which reading is true is left to the next field case; the reason carries both so it can be
  recorded.
- The tracker's token path (`_http.request`) still reads headers from its own failed reply,
  as before. It is out of scope; it is not on the `pr act` path.
