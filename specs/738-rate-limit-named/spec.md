# Feature Specification: a GitHub rate limit is named, not redacted

**Feature Branch**: `738-rate-limit-named`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #738 (owner, 2026-10-10): `wuwei brief` reported
`gh exited 1: [REDACTED]`; the hidden text was GitHub's secondary rate-limit message, which
holds no secret. A collection job on the same account tripped the limit, and the gate agents
hit 403s from the same cause. The code host and tracker ports recognise a 403 or 429
rate-limit reply and report the reset time; the call waits until the reset (capped by
`host.rate_limit_wait_seconds`, default 120) and retries once, then reports
`GitHub rate limit until <time>; retry after it` with no redaction; the redactor keeps the
error text of a known API reply when it matches no credential shape (the message scan still
runs on it). `doctor` shows the account's remaining calls and the reset time when the last
call was limited.

## Root cause (read on main at d3b7066)

Every code host call runs `gh` through `adapters/code_host/github.py` `_run` (line 59). On a
nonzero exit (lines 108-128) it builds `gh exited <n> (<subject>)` and appends the first
stderr line passed through `redact(line)[:200]` (line 127). `wuwei brief` reaches it through
`host.pr` (`cli/wuwei/brief.py:506-507`; `read` at line 126 raises the reason).

Two defects meet there:

1. The reply is never recognised as a rate limit. Nothing reads a reset time, nothing
   waits, and the reason carries GitHub's text (when it survives) capped at 200 characters,
   which cuts the request id and never says when to retry.
2. `cli/wuwei/redact.py` `redact` replaces a whole string when `SECRET` matches anywhere in
   it (line 117). `SECRET`'s first branch (line 56) is a field name from `SENSITIVE_FIELD`
   (lines 47-49, which include `message`) followed by an optional quote and `:` or `=`. A
   GitHub error reply in its JSON form, `{"message":"You have exceeded a secondary rate
   limit. ...","documentation_url":"..."}`, matches at `message":"Y`, so the reason becomes
   exactly `gh exited 1 (acme/app): [REDACTED]`.

Reproduced read-only on main with the adapter and a stubbed `subprocess.run`
(`returncode=1`): with that JSON line on stderr, `github.pr('acme/app#7').reason` is
`github.pr: could not run: gh exited 1 (acme/app): [REDACTED]`. With gh's plain form
`gh: You have exceeded a secondary rate limit. ... (HTTP 403)` nothing is redacted, but the
text is truncated at 200 characters and names no reset time. The orchestrator notes file
named in the task (`notes/738-full.md`) does not exist, so there was no dry-run workspace;
this reproduction stands in for it.

The tracker has the same gap on both of its paths:

- `adapters/tracker/github.py` `_gh` (line 50) maps a `(HTTP 403)` stderr to
  `_http.status(403)` (lines 60-62): `credential has no access (scopes, SSO authorization or
  a rate limit)`, which does not say it was a rate limit or when it ends.
- With `GITHUB_TRACKER_TOKEN`, `adapters/_http.py` `request` (lines 77-78) turns any
  `HTTPError` into `status(code)` and drops the `Retry-After`, `X-RateLimit-Remaining` and
  `X-RateLimit-Reset` headers GitHub sends with a limited reply.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where do the wait and the retry live, given "the caller waits"? A: In the one place
  every GitHub call routes through: the gh call inside code host `_run`, the gh call inside
  tracker `_gh`, and the request inside tracker `_query`. Every caller (brief, doctor, gates,
  shepherd, dispatch) then gets it without change. Retrying a whole port operation was
  rejected: an operation such as `create_pr` makes several calls, and re-running the ones
  that succeeded would repeat writes. One rejected call is safe to repeat: GitHub refused it.
- Q: What is the "rate_limited result"? A: An adapter-internal error carrying the reset time
  (`_http.RateLimited`, a `Failure`). The port result stays `(exit, data, reason)`: exit 2,
  reason `GitHub rate limit until <time> (<n> of <m> <resource> calls left); retry after it`.
  No new field on `Result`: no caller needs one, and the retry already happened inside.
- Q: How does a gh call learn the reset time? gh prints no headers on an error. A: After a
  gh failure whose stderr says `rate limit`, read `gh api rate_limit` (GitHub does not count
  it against the limit). If the `core` or `graphql` resource has 0 remaining, the reset is
  that resource's `reset`. Otherwise it is a secondary limit with no published reset, and
  GitHub's documented rule applies: wait at least one minute (reset = now + 60 s). If the
  `rate_limit` read fails, also now + 60 s, with no calls-left part.
- Q: And the token path? A: From the headers of the 403 or 429 reply: `Retry-After` seconds,
  else `X-RateLimit-Reset` when `X-RateLimit-Remaining` is `0`, else for a 429 now + 60 s.
  A 403 with none of those is not a rate limit and keeps today's `HTTP 403` hint. Only
  requests to `https://api.github.com/` are read this way; Linear, Jira and the other HTTP
  adapters keep today's behaviour.
- Q: Which time format? A: UTC, `HH:MM:SS UTC` (for example `14:05:00 UTC`). A primary
  window is at most an hour, so the date adds nothing; UTC is unambiguous on any host.
- Q: What does "the redactor keeps the error text of a known API reply" cover? A: A stderr
  line that parses as GitHub's error reply, a JSON object with a string `message` and a
  `documentation_url` (the same shape `_errors` in the code host adapter already treats as
  an error reply). Its `message` replaces the JSON line, and `redact` then runs on the
  message itself, so a credential shape or phone number in it is still hidden. Every other
  line is redacted exactly as today. `SECRET` and `SENSITIVE_FIELD` do not change: the
  `message` field rule protects traces and inbound text.
- Q: What does doctor show? A: Doctor measures with its own calls; it keeps no record of
  other processes' calls (a "last limited" record would be a new state file a seat could
  write). When a doctor row's call is limited, the row shows the reason, which names the reset
  time and the calls left, with status `unmeasured` (could not run, not a finding) and the fix
  `wait until the reset it names (another job on the same GitHub account shares the limit),
  then run doctor again`. Today the only doctor row whose call can be limited is the tracker
  backlog read (`_tracker`); the `gh` row runs `gh auth status`, which reads no API.
- Q: Is the cap configurable and can it be zero? A: `host.rate_limit_wait_seconds`, integer,
  default 120, minimum 0. Zero never waits: the first limited call reports at once. An
  unreadable or absent workspace config uses 120.

## User Scenarios and Testing

### User Story 1 - A rate-limited call names the limit and its reset (Priority: P1)

A seat or the owner runs a command whose GitHub call is rate limited. The reason says it is a
GitHub rate limit, when it ends and how many calls are left, and holds no `[REDACTED]`.

**Independent Test**: a code host read whose gh stderr is a secondary rate-limit message
returns exit 2 with `GitHub rate limit until <time>` in the reason and no `[REDACTED]`.

**Acceptance Scenarios**:

1. **Given** a gh call that fails with a secondary rate-limit message (plain or JSON form) and
   a reset beyond the cap, **When** the code host reads a pull request, **Then** the reason is
   `github.pr: could not run: GitHub rate limit until <HH:MM:SS> UTC (<n> of <m> <resource>
   calls left); retry after it` and contains no `[REDACTED]`.
2. **Given** `gh api rate_limit` shows `core` at 0 remaining with reset R, **Then** the reason
   names R.
3. **Given** `gh api rate_limit` shows calls remaining (a secondary limit), **Then** the reset
   is now + 60 s.
4. **Given** `gh api rate_limit` itself fails, **Then** the reset is now + 60 s and the reason
   has no calls-left part.
5. **Given** the tracker through gh (`tracker.auth = "gh"`) gets the same stderr, **Then** its
   reason is the same rate-limit text, not `HTTP 403: credential has no access`.
6. **Given** the tracker through `GITHUB_TRACKER_TOKEN` gets a 403 with
   `X-RateLimit-Remaining: 0` and `X-RateLimit-Reset: R`, or a 429 or 403 with
   `Retry-After: S`, **Then** its reason names R, or now + S.

### User Story 2 - A short limit is waited out (Priority: P1)

**Independent Test**: a limited call whose reset is within the cap sleeps until the reset and
succeeds on the one retry.

**Acceptance Scenarios**:

1. **Given** the reset within `host.rate_limit_wait_seconds`, **When** the call is made,
   **Then** it sleeps until the reset (never a negative time), runs the same call once more,
   and returns its data with exit 0.
2. **Given** the reset beyond the cap, **Then** it does not sleep and the reason says when to
   retry.
3. **Given** the retry is limited again, **Then** there is no second retry and the reason
   names the new reset.
4. **Given** `host.rate_limit_wait_seconds = 0`, **Then** no limited call sleeps.
5. **Given** the tracker token path or the tracker gh path, **Then** the same wait and single
   retry apply per query.

### User Story 3 - A known API error reply is readable (Priority: P2)

**Independent Test**: a gh failure whose stderr is GitHub's JSON error reply with a harmless
message shows the message in the reason.

**Acceptance Scenarios**:

1. **Given** stderr `{"message":"Resource not accessible by integration","documentation_url":"https://docs.github.com/rest"}`,
   **Then** the reason ends `gh exited 1 (acme/app): Resource not accessible by integration`.
2. **Given** a JSON error reply whose message holds a credential shape (for example a
   `ghp_` token), **Then** the reason holds `[REDACTED]` and not the token.
3. **Given** a JSON line without `documentation_url`, or any non-JSON line, **Then** it is
   redacted exactly as on main.

### User Story 4 - Doctor names the limit (Priority: P2)

**Independent Test**: doctor's tracker row, when the backlog read returns the rate-limit
reason, is `unmeasured`, shows the reason and gives the wait fix.

**Acceptance Scenarios**:

1. **Given** the tracker backlog read returns `GitHub rate limit until 14:05:00 UTC (0 of 5000
   graphql calls left); retry after it`, **When** doctor runs, **Then** the tracker row is
   `unmeasured`, its value is that reason and its fix names waiting until the reset.
2. **Given** any other tracker failure, **Then** the row is `fail` with today's fix.

### Edge Cases

- A reset already in the past: the wait is 0 and the call is retried at once.
- A stderr that names a rate limit on a search call: the rate-limit reason replaces the
  stderr line, so no email from the search query reaches it (today's rule for search holds).
- `gh auth status` and the 304 conditional read paths: unchanged.
- The token path against a non-GitHub URL: unchanged (`HTTP 429: rate limited; retry later`).
- A GraphQL `RATE_LIMITED` error inside a 200 reply on the token path is out of scope: its
  message already reaches the reason through `_error` (#617) and names the limit; it has no
  reset header.

## Requirements

### Functional Requirements

- **FR-001**: A gh call in the code host adapter or the GitHub tracker adapter that exits
  nonzero with `rate limit` (any case) in its stderr MUST be treated as rate limited, with
  the reset and calls left read from `gh api rate_limit` as clarified, or now + 60 s.
- **FR-002**: A token request to `https://api.github.com/` answered 403 or 429 with
  `Retry-After`, or with `X-RateLimit-Remaining: 0` and `X-RateLimit-Reset`, or answered 429
  with neither, MUST be treated as rate limited with the reset those give (now + 60 s for a
  bare 429).
- **FR-003**: A rate-limited call whose reset is at most `host.rate_limit_wait_seconds` away
  MUST sleep until the reset and run once more; beyond the cap, or when the retry is limited
  again, it MUST fail with exit 2 and the reason `GitHub rate limit until <HH:MM:SS> UTC
  [(<n> of <m> <resource> calls left)]; retry after it`, built only from numbers and fixed
  words, never passed through the redactor and never holding provider text.
- **FR-004**: `host.rate_limit_wait_seconds` MUST be a config key, integer, default 120,
  minimum 0, listed in the workspace template and the configuration docs.
- **FR-005**: The code host adapter's stderr line MUST, when it parses as a JSON object with a
  string `message` and a `documentation_url`, be replaced by that message before redaction;
  the redactor MUST still run on the message. Every other line MUST be redacted as on main.
- **FR-006**: Doctor's tracker row MUST show a rate-limit reason as `unmeasured` with the wait
  fix; every other row and failure MUST stay as on main.
- **FR-007**: `SECRET`, `SENSITIVE_FIELD`, `redact`'s existing behaviour, `_http.status`, the
  code host command allowlist, non-GitHub HTTP adapters and the `Result` shape MUST NOT
  change.

## Success Criteria

- **SC-001**: The issue's acceptance cases hold: a secondary rate-limit failure names the
  limit and its reset with nothing redacted; a reset within the cap waits and succeeds on the
  retry; beyond it, the reason says when to retry.
- **SC-002**: No test sleeps for real or reaches the network or a real `gh`.
- **SC-003**: The full suite passes; existing assertions change only where they list the
  full `host` defaults.

## Assumptions

- No orchestrator notes or dry-run workspace exist for #738; the failure was reproduced on
  main with the adapter and a stubbed `subprocess.run`, and the root cause is read from the
  code cited above. The owner's gh wrote the reply's JSON form to stderr; the plain form is
  handled the same way, so the fix does not depend on which one gh printed.
- #662, named in the issue's references, has no spec or note in this repository; nothing in
  this feature depends on it.
- "The caller waits" means the adapter's gh call or HTTP request, the one spot every caller
  routes through; retrying a whole port operation would repeat successful writes.
- A rejected rate-limited request was not applied by GitHub, so one retry of a write (a
  comment, a PR, a merge with `--match-head-commit`) is safe.
- The secondary-limit wait is a fixed 60 s, GitHub's documented minimum when no reset is
  given; it is a module constant, not configuration (constitution V).
- Doctor reports limits it meets on its own calls; it keeps no record of other processes'
  calls. A persisted "last limited" record is deferred until the owner asks for it.
- The wait runs in the process making the call. Seats run in the background; a foreground
  command can wait up to the cap. The owner sets `host.rate_limit_wait_seconds = 0` to never
  wait.
- `rate limit` in gh's stderr is specific enough: GitHub's primary (`API rate limit
  exceeded`) and secondary (`You have exceeded a secondary rate limit`) texts both hold it,
  and no other gh error does.

## Deferred

- A GraphQL `RATE_LIMITED` error inside a 200 reply on the token path gets no wait (no reset
  header); its message already names the limit.
