# Feature Specification: a 403 rate-limit reply is reported as a rate limit, never as missing gh auth

**Feature Branch**: `784-doctor-rate-limit`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #784 (owner, 2026-10-10, item 73): while REST was on a secondary rate
limit, `doctor` reported "gh auth: missing" although the account was authenticated and the
hourly counter was full (5000 of 5000). Deliver: the doctor auth row tells an authentication
failure (401, `gh auth status` says not logged in) from a rate limit (403 with the rate-limit
text or headers, 429); the row reads `gh: rate limited until <time>` with status `waiting`,
not `missing`; the `rate_limited` result from #738 is the one source.

## Root cause (read on main at cb33150)

1. `adapters/code_host/github.py` `auth_status` (lines 655-665) runs
   `gh auth status --hostname github.com` and maps every exit 1 to
   `Result(1, reason='gh auth: missing')` (line 662).
2. `gh auth status` is not offline. It validates the token with `GET https://api.github.com/`
   (gh's `GetScopes`), and on any non-200 reply, a 403 secondary rate limit included, it
   prints `X Failed to log in to github.com account <login> (<source>)` and
   `- The token in <source> is invalid.` and exits 1. The reply's text and status are not
   printed (checked in the gh 2.93.0 binary's strings: both format strings are there, and
   `auth status` has no rate-limit text). So nothing in its output says "rate limit", and
   #738's `gh_limit` (`adapters/_http.py` lines 74-90, which keys on `rate limit` in stderr)
   never fires for it.
3. #738's spec assumed the opposite ("the `gh` row runs `gh auth status`, which reads no
   API"), so the doctor `gh` row (`cli/wuwei/commands/doctor.py` `_host`, lines 172-175) was
   left mapping exit 1 to status `fail`, value `gh auth: missing`, fix `gh auth login`.

Reproduced read-only on main with the adapter and a stubbed `subprocess.run` (no workspace,
no network): with `gh auth status` exiting 1 with gh's "Failed to log in ... token ... is
invalid" text, `github.auth_status()` returns `Result(exit=1, reason='gh auth: missing')`
after one call, and nothing asks the API why. The orchestrator notes file named in the task
(`notes/784-full.md`) does not exist, so there was no dry-run workspace; this reproduction
stands in for it.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: `gh auth status` prints no reason. How does the adapter tell a rate limit from a bad
  token? A: Only when `gh auth status` exits 1, ask the API once with `gh api user`, a call
  the adapter's allowlist already has (`case ['api', 'user']`), through the same `_run` every
  gh call uses. A secondary limit makes gh print `You have exceeded a secondary rate limit
  ... (HTTP 403)`, so #738's `gh_limit` and `retry` handle it and `_run` raises the #738
  reason `GitHub rate limit until <HH:MM:SS> UTC [(<n> of <m> <resource> calls left)]; retry
  after it`. A 401 (`Bad credentials`) or "please run gh auth login" (not logged in) is not a
  rate limit and stays `gh auth: missing`. A healthy `gh auth status` (exit 0) costs no
  extra call.
- Q: What does `auth_status` return for a rate limit? A: `Result(2, reason=<the #738 reason
  unchanged>)`: could not measure, not a finding. No new `Result` field, no new text: the
  #738 reason is the one source.
- Q: And when `gh api user` answers after `gh auth status` failed (for example the limit
  lifted during #738's wait, or a second, inactive account on the host has a stale token)?
  A: `Result(0)`: the API answered as the user, so gh works for WUWEI.
- Q: Does doctor wait? A: As every GitHub call does since #738: when the reset is within
  `host.rate_limit_wait_seconds` (default 120; a secondary limit is now + 60 s), the probe
  waits once and retries. No new knob; `0` makes doctor report at once.
- Q: What is the row? A: Name `gh` (unchanged), status `waiting` (new doctor status), value
  `rate limited until <HH:MM:SS> UTC ...` (the #738 reason from its time on, so the calls
  left that #738 asked doctor to show stay), fix `wait until the reset it names (another job
  on the same GitHub account shares the limit), then run doctor again` (#738's tracker-row
  text). Rendered: `waiting    gh: rate limited until 14:05:00 UTC (5000 of 5000 core calls
  left); retry after it`.
- Q: What does `waiting` count as? A: Exit 2 (unmeasured class) in `doctor.CODES` and in
  `outcome`: the row could not be measured now; it is not a finding (exit 1). The summary
  line counts it: `doctor: 0 fail, 0 warn, 0 unmeasured, 1 waiting`.
- Q: The tracker row already handles a rate limit (#738) as `unmeasured`. Does it change?
  A: Yes, to the same `waiting` row through the same doctor helper, so one condition reads
  one way in one report. One helper used by both rows replaces #738's inline check.

## User Scenarios and Testing

### User Story 1 - Doctor says rate limited, not missing auth (Priority: P1)

The owner runs `wuwei doctor` while another job on the same GitHub account holds a secondary
rate limit. The `gh` row says the account is rate limited until a time, with status
`waiting`, and no row tells the owner to log in again.

**Independent Test**: with `gh auth status` exiting 1 and `gh api user` failing with gh's
secondary rate-limit text, `auth_status()` returns exit 2 with the #738 reason, and doctor's
`gh` row is `waiting` with `rate limited until <time>`.

**Acceptance Scenarios**:

1. **Given** a 403 secondary rate-limit reply (`gh auth status` exits 1; `gh api user` exits
   1 with `You have exceeded a secondary rate limit ... (HTTP 403)`; `gh api rate_limit`
   shows 5000 of 5000 left), **When** doctor runs, **Then** the `gh` row is status `waiting`,
   its value starts `rate limited until <HH:MM:SS> UTC`, its fix says to wait for the reset,
   and no row is `fail` with `gh auth: missing` or the fix `gh auth login` (no auth finding).
2. **Given** the same, **When** the adapter's `auth_status()` runs with the wait cap at 0,
   **Then** it returns exit 2 and reason `GitHub rate limit until <NOW+60> UTC (5000 of 5000
   core calls left); retry after it`, does not sleep, and makes exactly three gh calls:
   `auth status`, `api user`, `api rate_limit`.
3. **Given** `gh api rate_limit` shows `core` at 0 remaining with reset R (a primary limit),
   **Then** the reason names R.

### User Story 2 - A real auth failure is still missing (Priority: P1)

**Independent Test**: with `gh auth status` exiting 1 and `gh api user` failing with
`Bad credentials (HTTP 401)` or gh's "please run gh auth login", `auth_status()` returns
`Result(1, reason='gh auth: missing')` and doctor's row is `fail` with `gh auth login`.

**Acceptance Scenarios**:

1. **Given** `gh api user` fails with `gh: Bad credentials (HTTP 401)`, **Then**
   `gh auth: missing`, exit 1.
2. **Given** `gh api user` exits 4 with `To get started with GitHub CLI, please run:  gh auth
   login`, **Then** `gh auth: missing`, exit 1.
3. **Given** `gh auth status` exits 0, **Then** `Result(0)` after that one call (no probe).
4. **Given** `gh auth status` exits 1 and `gh api user` succeeds, **Then** `Result(0)`.
5. **Given** the probe's output holds a token value, **Then** no output or reason holds it
   (the probe's error text is discarded unless it is the #738 rate-limit reason).

### User Story 3 - One reading of a rate limit across doctor (Priority: P2)

**Independent Test**: doctor's tracker row, when the backlog read returns the #738 reason,
is `waiting` with `rate limited until <time> ...` and the same fix as the `gh` row.

**Acceptance Scenarios**:

1. **Given** the tracker backlog read returns `github.backlog: could not run: GitHub rate
   limit until 14:05:00 UTC (0 of 5000 graphql calls left); retry after it`, **Then** the
   tracker row is `waiting`, value `rate limited until 14:05:00 UTC (0 of 5000 graphql calls
   left); retry after it`, and the fix names waiting until the reset.
2. **Given** `waiting` rows and otherwise only `ok` rows, **Then** doctor exits 2 and the
   summary line counts them (`... 0 unmeasured, 1 waiting`).
3. **Given** setup's ending reads a `waiting` row, **Then** `doctor.CODES` maps it without a
   `KeyError`.

### Edge Cases

- `gh auth status` exits 2 or more, or raises: unchanged (`gh auth: could not run`).
- The probe times out or gh vanishes between calls: the existing outer handler returns
  `Result(2, 'gh auth: could not run; check gh installation and authentication')`.
- `config check` and `setup` call `auth_status` too: a rate limit there now reads
  `gh auth: unmeasured` (exit 2) with the reason on stderr instead of `missing`; their
  wording is not otherwise changed.
- Under a limit within the cap, doctor waits up to `host.rate_limit_wait_seconds` once (the
  #738 rule for every GitHub call).

## Requirements

### Functional Requirements

- **FR-001**: When `gh auth status --hostname github.com` exits 1, the code host adapter's
  `auth_status` MUST probe once with `gh api user` through `_run`, and MUST return
  `Result(2, reason=<#738 reason>)` when the probe fails with a rate limit, `Result(0)` when
  the probe succeeds, and `Result(1, reason='gh auth: missing')` otherwise.
- **FR-002**: The rate-limit reason MUST be the #738 `RateLimited` text exactly, never
  rebuilt, and no probe error text other than it MUST reach any reason or output.
- **FR-003**: Doctor MUST show a reason that holds `GitHub rate limit until ` as a row with
  status `waiting`, value `rate limited until ` followed by the reason's text after that
  marker, and the fix `wait until the reset it names (another job on the same GitHub account
  shares the limit), then run doctor again`, for the `gh` row and the tracker row.
- **FR-004**: `waiting` MUST be a doctor status with code 2 in `doctor.CODES`, MUST make
  `outcome` 2 when no row is `warn` or `fail`, and MUST be counted in the summary line.
- **FR-005**: The adapters doc row for `code_host.github` MUST say that a failing
  `gh auth status` is checked with `gh api user`, and that doctor shows a rate limit as
  `waiting`.

### Key Entities

- None new. `Result` and the #738 `RateLimited` reason are reused unchanged.

## Success Criteria

- **SC-001**: Under a secondary rate limit, doctor never reports `gh auth: missing` or the fix
  `gh auth login`.
- **SC-002**: A revoked or absent login still reports `gh auth: missing` with `gh auth login`.

## Assumptions

- gh's `auth status` prints no reply text on a non-200 (verified in the gh 2.93.0 binary's
  format strings), so a second call is the only way to learn why; `gh api user` is the
  cheapest allowlisted call, and gh prints its error message, which names a secondary limit.
- `Result(0)` when the probe succeeds after `gh auth status` failed: the API answering as the
  user is the measure WUWEI needs. A stale inactive second account no longer reads as
  missing auth.
- `waiting` is exit 2 (could not measure now), like `unmeasured`; it is not a finding.
- The tracker row joins the `gh` row on `waiting` for consistency (one helper); #738's tracker
  test is updated, not kept.
- `config check` and `setup discover` keep their wording (`unmeasured` for exit 2); only
  doctor gains the `waiting` row, as the issue asks.
- No guard or decision rule changes, so no invariant row (constitution, Workflow).

## Deferred

- None.
