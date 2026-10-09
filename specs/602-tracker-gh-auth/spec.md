# Feature Specification: tracker.github through the owner's gh login, HTTP status in adapter failures, credential shape check

**Feature Branch**: `602-tracker-gh-auth`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #602 (owner request, 2026-10-09): `adapters/tracker/github.py` authenticates only with
`GITHUB_TRACKER_TOKEN` against `https://api.github.com/graphql`. Fine-grained tokens are
created only in the GitHub web UI, and pasting one into `.wuwei/env` is error-prone: an
owner's setup failed because the clipboard held a command instead of the token, and the
adapter reported only `github.backlog: could not run: HTTPError`, with no status code.
`code_host.github` already uses the owner's gh login (`gh auth: set`), so a solo owner with
gh signed in still has to mint a separate token. Do: (1) an explicit opt-in config key that
lets `tracker.github` run its GraphQL calls through the owner's gh login when
`GITHUB_TRACKER_TOKEN` is unset, with the trade-off documented and a decision on how seats
reach it; (2) HTTP failures in `adapters/_http.py` report the status code and a one-line
hint; (3) `wuwei config check` and `doctor` sanity-check a token's shape without printing
it; (4) tests and docs (adapters.md, configuration.md).

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which wins when `tracker.auth = "gh"` and `GITHUB_TRACKER_TOKEN` is also set? A: The
  token. It is the narrower credential, and the request says "when GITHUB_TRACKER_TOKEN is
  unset".
- Q: How do seats reach the gh path: owner-side process only, or inherited? A: The same way
  they reach the token path today, through the CLI only. Tracker operations run inside the
  `bin/wuwei` process (`tracker create`, `tracker log`, the watch, doctor, discovery), behind
  the outward policy; the opt-in puts no credential in `.wuwei/env` or in a seat's
  environment. gh keeps its login in its own store, which `code_host.github` already uses
  and which any process running as the owner can already reach (design 9.1: no local file is
  a boundary). An owner-side-only gate would need the CLI to tell a seat's call from the
  owner's, which the session registry cannot prove (9.1), so it would add a refusal without
  a guarantee. What the opt-in gives up is least privilege on the tracker path: a defect in
  the adapter would act with the full gh login (classic scopes such as `repo`, `workflow`)
  instead of an issues-and-projects token. Hence opt-in, documented, and the default stays
  the fine-grained token.
- Q: Who may switch it on? A: The owner. `tracker.auth` is a `config.toml` key; `config set`
  from a session needs the owner's card answer, and a seat cannot write `config.toml` (the
  `records` floor). No new guard is needed.
- Q: Which gh environment? A: The one `code_host.github` uses: the process environment, so
  `config check`'s `gh auth: set` line describes the same login. A write-scoped `GH_TOKEN`
  in `.wuwei/env` stays a `config check` finding (security.md, "keep write-scoped GH_TOKEN
  out of .wuwei/env").
- Q: What counts as a malformed token value? A: Whitespace anywhere (a pasted command such
  as `gh auth token` or two lines), a path-like start (`/`, `~`, `./`, `../`), or a shell
  character (`` $ ` ; | & < > ( ) `` or a quote). Checked only for token-type credentials,
  never for URLs, emails, sites or channel ids. The value is never printed.

## User Scenarios and Testing

### User Story 1 - A solo owner uses the gh login for the GitHub tracker (Priority: P1)

The owner has gh signed in and sets `tracker.auth = "gh"`. With no `GITHUB_TRACKER_TOKEN`,
every `tracker.github` operation runs `gh api graphql --hostname github.com --input -` with
the same GraphQL payload it would POST, and returns the same data.

**Acceptance Scenarios**:

1. **Given** `tracker.auth = "gh"` and no token, **When** the port contract runs (backlog,
   claim, transition, create, comment, history, created), **Then** every call returns exit 0
   with the same results as the token path, no HTTP request is made, and each gh call
   carries exactly the GraphQL payload.
2. **Given** `tracker.auth = "gh"` and a token, **Then** the token path runs and gh is not
   called.
3. **Given** the default (`tracker.auth = "token"`) and no token, **Then** the call returns
   exit 2 naming `GITHUB_TRACKER_TOKEN is missing` and the opt-in, and gh is not called.
4. **Given** gh exits nonzero with `(HTTP 401)` on stderr, **Then** the reason names
   `gh api graphql exited 1`, `HTTP 401` and a hint, and no stderr text beyond that.
   **Given** stderr mentions a missing scope, **Then** the hint names
   `gh auth refresh -s project`. **Given** a GraphQL error body, **Then** the hint is
   `GitHub error response`. **Given** gh is not on PATH, or runs past 30 s, **Then** the
   reason says so (exit 2, never an uncaught exception).
5. `config check` prints `tracker.github: gh login (tracker.auth = "gh")` when the token is
   unset and counts no missing credential; doctor's tracker row reads the backlog through
   gh and its fix names `gh auth status`.

### User Story 2 - An HTTP failure names its status (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a provider answers 401, 403, 404 or 429, **When** any HTTP adapter call fails,
   **Then** the reason reads `<op>: could not run: HTTP <code>: <hint>`, with no provider
   text or credential.
2. **Given** a 5xx, **Then** the hint says the provider failed and to retry. **Given** any
   other status, **Then** the reason is `HTTP <code>`.
3. `wuwei doctor`'s tracker row shows that reason.

### User Story 3 - A malformed token is named, never printed (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `GITHUB_TRACKER_TOKEN` holds whitespace, a path-like or a command-like value,
   **When** `wuwei config check` runs, **Then** the line reads
   `GITHUB_TRACKER_TOKEN: malformed (<why>)`, the command exits 1, and the value appears
   nowhere in stdout or stderr. Doctor's `config check` row carries the same line.
2. **Given** the same value, **When** an adapter reads it, **Then** the call returns exit 2
   with `GITHUB_TRACKER_TOKEN is malformed (<why>)` and makes no request.
3. URLs, emails, `JIRA_SITE` and channel ids are not shape-checked.

## Requirements

- **FR-001**: `tracker.auth` in `config.toml`, `"token"` (default) or `"gh"`; any other value
  is a config error.
- **FR-002**: With `GITHUB_TRACKER_TOKEN` set, `tracker.github` uses it whatever
  `tracker.auth` says. Unset with `"gh"`, it runs `gh api graphql --hostname github.com
  --input -` (timeout 30 s) with the GraphQL payload on stdin, in the process environment.
  The response is parsed and checked exactly as the HTTP one (errors and missing `data` are
  failures).
- **FR-003**: A gh failure reports `gh api graphql exited <n>`, the HTTP status when gh
  printed one, and a hint; never gh's stderr text or the response body.
- **FR-004**: `adapters/_http.request` turns an HTTP error into `HTTP <code>` plus a one-line
  hint for 401, 403, 404, 429 and 5xx.
- **FR-005**: One function, `env.malformed(name)`, returns why a token-type credential's value
  is malformed, or `''`. `_http.credential` refuses a malformed value; `config check` reports
  it as a finding (exit 1). The value is never printed.
- **FR-006**: `config check`, doctor's tracker row, the setup interview's GitHub choice, the
  template and the docs name the opt-in. adapters.md documents the trade-off and how seats
  reach it; configuration.md documents the key and the malformed line.

## Success Criteria

- **SC-001**: A solo owner with gh signed in runs the GitHub tracker with one config line and
  no token.
- **SC-002**: The pasted-command failure now reads as `malformed (contains whitespace)` in
  `config check` and doctor, and a rejected token reads `HTTP 401: ...` instead of
  `HTTPError`.

## Assumptions

- The GitHub issue is #602, filed after the pull request branch was ready (issue creation was
  refused to this session at first).
- The default gh login has `repo` and `read:org`; Projects v2 Status writes also need
  `project`. The adapter does not check scopes; a GraphQL scope error comes back as a failure
  whose hint names `gh auth refresh -s project`.
- No guard or decision rule changes, so no design 9.2 invariant row.

## Design spec conflict (raised, not resolved)

Design 5.11's adapter table names the `github` credential as `GITHUB_TRACKER_TOKEN, a
fine-grained token for issues and projects only`. This feature keeps that as the default and
adds an owner opt-in beside it. The design spec is amended only by its owner, so the pull
request asks the owner to amend that row (proposed text: "`GITHUB_TRACKER_TOKEN`, a
fine-grained token for issues and projects only; or, with `tracker.auth = "gh"` and no token,
the owner's gh login").

## Deferred

- None.
