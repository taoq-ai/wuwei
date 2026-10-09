# Implementation Plan: tracker.github through the owner's gh login

**Branch**: `602-tracker-gh-auth` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

Three small changes on existing code: a GraphQL transport switch inside
`adapters/tracker/github.py`, an `HTTPError` branch in `adapters/_http.request`, and one
shape function in `cli/wuwei/env.py` that `_http.credential` and `config check` share.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new port
operation, no new event kind. One new config key, `tracker.auth`.

## Constitution Check

- I stdlib: `subprocess` and `json` only; gh reached as a subprocess behind the adapter.
- II exits: every failure stays exit 2 with a local reason; a gh error body is never parsed
  as data.
- III one behaviour one function: the shape rule lives in `env.malformed`, read by
  `_http.credential` and `config check`.
- IV test first: each change starts with a failing test.
- V simplicity: no transport class; `_query` picks HTTP or gh in three lines.
- VII security: the opt-in is owner-only (config set needs the owner's answer), token wins
  when both exist, values never printed, gh stderr never echoed.

## Design

### adapters/tracker/github.py

- `_query(query, variables, root)`: payload `{'query', 'variables'}`. If
  `GITHUB_TRACKER_TOKEN` is set, or `settings(root)['tracker']['auth'] != 'gh'`, POST through
  `request(URL, credential(...), payload)` as today. Otherwise `_gh(payload)`.
- `credential` failure for this adapter adds the opt-in hint: the missing reason becomes
  `GITHUB_TRACKER_TOKEN is missing; set it in .wuwei/env, or set tracker.auth = "gh" to use
  your gh login`.
- `_gh(payload)`: `subprocess.run(['gh', 'api', 'graphql', '--hostname', 'github.com',
  '--input', '-'], input=json.dumps(payload), capture_output=True, text=True, timeout=30)`.
  `FileNotFoundError` becomes `gh is not on PATH; install the GitHub CLI and run gh auth
  login`. A nonzero exit becomes `gh api graphql exited <n>` plus `HTTP <code>: <hint>` when
  stderr holds `(HTTP <code>)`, else `: run gh auth status` (or `gh auth refresh -s project`
  when stderr mentions a scope). Success parses stdout as a JSON object.
- `root` is threaded through `_issue` and every `_query` call.

### adapters/_http.py

- `HINTS` by status: 401 credential rejected (wrong, expired or revoked); 403 no access
  (scopes, SSO authorization or a rate limit); 404 not found or not visible to the credential
  (check the project or repository name and the token's access); 429 rate limited, retry
  later; 5xx provider error, retry later.
- `status(code)` returns `HTTP <code>: <hint>` (or `HTTP <code>`); `request` catches
  `urllib.error.HTTPError` and raises `Failure(status(exc.code))`. The non-2xx branch uses
  the same text. The gh path reuses `status`.
- `credential(name)` raises `Failure(f'{name} is malformed ({why}); ...')` when
  `env.malformed(name)` says so.

### cli/wuwei/env.py

- `TOKENS`: the token-type names of `CREDENTIALS` (everything but `WUWEI_CALENDAR_URL`,
  `SLACK_API_BASE`, `SLACK_OWNER_DM_CHANNEL`, `JIRA_SITE`, `JIRA_EMAIL`,
  `CONFLUENCE_EMAIL`).
- `malformed(name)`: `''` for a non-token or unset name; else `contains whitespace`,
  `looks like a path` or `looks like a command (shell characters)`.

### cli/wuwei/workspace.py and template

- `"auth": (str, "token", ("token", "gh"))` under `tracker`; one commented line in
  `templates/workspace/config.toml`.

### cli/wuwei/commands/config.py

- `requirements(config)`: `('tracker', 'github')` needs nothing under `tracker.auth = "gh"`.
- The credential loop prints `<KEY>: set | missing | malformed (<why>)`; a malformed value
  counts as not present (exit 1).
- Under `tracker.auth = "gh"`: `tracker.github: gh login (tracker.auth = "gh")` when the token
  is unset; with it set, the token line as today plus `(used before tracker.auth = "gh")`.

### cli/wuwei/commands/doctor.py

- Tracker row fix: under `"token"` for github, add `or bin/wuwei config set tracker.auth
  '"gh"'`; under `"gh"`, `run gh auth status (with tracker.board: gh auth refresh -s
  project)`.

### cli/wuwei/interview.py

- The GitHub choice names the opt-in.

### Docs

- adapters.md credentials row for `tracker.github`, plus a short "GitHub tracker through gh"
  subsection: the switch, token wins, seats reach it only through the CLI, the trade-off,
  the project scope, and that strict or shared-credential workspaces keep the token.
- configuration.md: `tracker.auth` row; the malformed line under `config check`; the HTTP
  status reasons.

## Tests

- `tests/test_tracker_adapters.py`: port contract under gh (fake `subprocess.run`, no HTTP),
  token wins, missing token names the opt-in, gh failure reasons (HTTP 401, scope, not on
  PATH), malformed token makes no request.
- `tests/test_reference_adapters.py`: HTTP 401, 403, 404, 429, 500 and 418 reasons.
- `tests/test_env_credentials.py`: `env.malformed` table; config check prints malformed
  without the value and exits 1; config check under `tracker.auth = "gh"`.
- `tests/test_doctor.py`: tracker row fix under both auth modes.
- `tests/test_docs.py`: the template key is documented (existing test) and adapters.md names
  `tracker.auth`.
