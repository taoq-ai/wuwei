# Feature Specification: a refusal's own rate-limit headers decide the bucket; gh api rate_limit is only the fallback

**Feature Branch**: `899-headers-decide`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #899: "a refusal's own rate-limit headers decide the bucket; gh api
rate_limit is only the fallback"

## What happened

Same shell, same token, 2026-10-12. At 12:20 UTC a `gh api -i` read of a PR returned 200 with
`X-RateLimit-Resource: core`, `Remaining: 1215` and `Reset: 12:55:46`. Minutes later `pr act`
was refused with "0 of 5000 core calls left until 12:55:46". At 12:38, before that reset,
`gh api rate_limit` printed core 5000. The #867 review saw the same disagreement, and there the
header reset turned out true. So `gh api rate_limit` is not a reliable reading here; the refused
reply's own `X-RateLimit-*` headers are.

## Root cause

#891 (PR 893) made `gh api rate_limit` the decider. On a refusal whose headers say core 0,
0.30.0 names both readings, suggests a token mismatch that does not exist and retries after 60 s
instead of waiting for the real reset. Most reads ran without `--include`, so the headers that
held the truth were never seen.

## User Scenarios & Testing

### User Story 1 - the refused reply names its own bucket (Priority: P1)

**Independent Test**: replay a `gh api --include` read of a PR refused with headers core 0 of
5000, reset 12:55:46, while `gh api rate_limit` would say 5000; the reason names
`0 of 5000 core calls left` until 12:55:46 and rate_limit is never called.

**Acceptance Scenarios**:

1. **Given** a refused read whose headers say remaining 0, **When** it is refused, **Then** the
   reason is `GitHub rate limit until <header reset> UTC (0 of <limit> <resource> calls left)`,
   one gh call, no rate_limit call, no token hint.
2. **Given** a refused read whose headers carry Retry-After or whose gh text says secondary,
   with calls left, **Then** the reason names `secondary limit on <endpoint>` and the header
   counts, and the wait is Retry-After, else one minute. No rate_limit call.
3. **Given** a refused write (or `pr merge`, `pr ready`), which carries no headers, **When**
   it is refused, **Then** `gh api rate_limit` decides, as in #891.
4. **Given** a successful `--include` read, a paged read and a 304 conditional read, **Then**
   their bodies parse as before.

## Requirements

- **FR-001**: Every single-page `gh api` read in the code host adapter (REST GET and GraphQL
  query) runs with `--include`; the status line and headers are cut off the top of stdout before
  the body is parsed. No second request is ever made to read headers.
- **FR-002**: A refused reply with valid `X-RateLimit-Resource`, `-Remaining`, `-Limit` and
  `-Reset` headers decides the bucket: remaining 0 is a primary limit until that reset; calls
  left with Retry-After or gh's secondary wording is a secondary limit on the endpoint; calls
  left with neither is named as such, with a one-minute wait.
- **FR-003**: `gh api rate_limit` is read only when the refused reply carries no rate-limit
  headers (writes, `pr merge`, `pr ready`, paged reads, the tracker's gh path).
- **FR-004**: The token-mismatch hint and the "its headers say ... but rate_limit shows" text
  are removed. When headers are absent and rate_limit shows calls left on gh's primary wording,
  a short note names that disagreement, without a token hint.
- **FR-005**: Kept: the `GitHub rate limit until ` prefix, doctor never waits, one retry
  within the cap, no request inside a secondary limit when headers are present, search
  endpoints named only `search`.

## Success Criteria

- **SC-001**: The #899 field replay names `0 of 5000 core calls left` until 12:55:46 and makes
  one gh call.

## Assumptions

- With `--include`, gh prints the status line, the headers and a blank line before the body,
  on success and on failure (probed in the #867 review for a 403). Output that does not start
  with `HTTP/` is parsed whole, so recordings without a head still parse; a JSON body never
  starts with `HTTP/`.
- Paged reads (`--paginate --slurp`) stay without `--include` and keep the rate_limit
  fallback: gh prints a header block per page, and how those blocks sit next to the slurped
  array was not probed (the owner's quota is exhausted). They can follow once probed.
- Writes stay without `--include`; the issue scopes the change to reads. Adding it to a write
  costs no request and can follow if the field shows a write refusal misread.
- When headers say remaining 0 and Retry-After is also present, the header reset decides (the
  primary wait).
- The tracker's gh path does not share `_run`; it keeps the rate_limit fallback. Its token path
  (`_http.request`) already reads its own reply's headers, so the two paths now follow one rule.
- No clarifying questions were asked (AGENTS.md); the choices above are the recommendation.
