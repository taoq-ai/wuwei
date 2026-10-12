# Implementation Plan: why reads local state only and doctor caps its network probes

**Branch**: `867-github-fanout` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

Name the resource a rate-limited gh call spends; doctor never waits for a reset and marks a
rate-limited config check as waiting; `config check` keeps clean protection reads for the
day; `open_prs` becomes one search per repository and owner login.

## Technical Context

Stdlib Python 3.11+. Runtime files: `adapters/_http.py`, `adapters/code_host/github.py`,
`adapters/code_host/none.py`, `cli/wuwei/registry.py`, `cli/wuwei/plan.py`,
`cli/wuwei/commands/config.py`, `cli/wuwei/commands/doctor.py`. No new module, no new state
field; one plain day-directory file (`protection.json`), as `prs.json` is.

## Constitution Check

- II: a search that is incomplete fails closed; an unreadable cache is ignored, never parsed
  as data; a rate limit stays exit 2 (`waiting`).
- III: one function per behaviour: `gh_limit` names the limit, `cap` the wait,
  `_protection` the cached read.
- IV: each change starts with a red test.
- V: no cache module; the day directory holds one JSON file; the wait override is one line.
- VII: the search endpoint is allowlisted by an exact pattern in `_run`; the login is checked
  against GitHub's login shape before the call.

## Changes

- `adapters/_http.py`
  - `RateLimited.__init__`: with calls left, the text reads
    `(secondary limit, N of M <resource> calls left)`.
  - `cap(root)`: `WUWEI_RATE_LIMIT_WAIT` (digits) wins over `host.rate_limit_wait_seconds`.
  - `gh_limit(stderr, env=None, resource='core')`: read `resources[resource]` only.
- `adapters/code_host/github.py`
  - `_run`: pass the call's resource to `gh_limit` (`graphql` for `api graphql`, `pr merge`
    and `pr ready`; `search` for `search/...`; else `core`); allow
    `search/issues?q=is%3Apr%20is%3Aopen%20repo%3A<repo>%20author%3A<login>&per_page=100`
    with `-H Cache-Control: no-cache`.
  - `open_prs(repo, author, root=None)`: that search; fail closed when
    `incomplete_results` is true or `total_count` differs from the item count.
- `adapters/code_host/none.py` `open_prs(repo, author, root=None)`;
  `cli/wuwei/registry.py` `'open_prs': ('repo', 'author')`.
- `adapters/tracker/github.py` `_gh`: `gh_limit(result.stderr, resource='graphql')`.
- Review fix round: `adapters/_http.py` `included_limit(text)` parses a `gh api --include`
  reply's status and X-RateLimit headers through `_github_limit`; `adapters/code_host/github.py`
  `_headers_limit(args, payload, result, env)` reads them from the failed call (already
  `--include`) or asks a read once more with `--include` and no pagination, before
  `gh_limit`. `plan._owner_prs` searches login-shaped handles only. `doctor._gates` lets a
  protection finding outrank a rate limit.
- `cli/wuwei/plan.py` `_owner_prs`: one `host.open_prs(repo, login)` per repository and
  login; the author filter moves to the server.
- `cli/wuwei/commands/config.py` `_protection(host, repo, solo, gate, root=None)`: read
  `<day>/protection.json`; a dict under `<repo>@<branch>` replaces the call; a read whose rows
  are all ok is written back.
- `cli/wuwei/commands/doctor.py`
  - `diagnose`: set `WUWEI_RATE_LIMIT_WAIT=0` for the run, restoring the previous value.
  - `_gates`: the config check row is `_limited(...)` when a detail line names the limit.
- Tests: `tests/test_code_host.py` (rate-limit table, open_prs recording),
  `tests/fixtures/code_host/recordings.json` (open_prs search),
  `tests/fakes/code_host.py`, `tests/test_adapters.py`, `tests/test_plan.py`,
  `tests/test_doctor.py`, `tests/test_why.py`, `tests/test_tracker_adapters.py` if it pins
  the gh_limit text.
- Docs: `docs/site/configuration.md` (`host.rate_limit_wait_seconds`: doctor never waits),
  `docs/site/reference.md` (doctor: protection read once a day).

## Calls per run, owner's workspace (three repositories, one owner login)

| Path | Before | After |
|------|--------|-------|
| doctor, GitHub calls | ~13 core (auth 2, protection 9, token scopes 0 to 2) | ~4 core after the day's first clean run (auth 2, token scopes 0 to 2) |
| doctor under a rate limit | up to 120 s wait per call | no wait; rows `waiting` |
| plan propose PR listing | 4 paged core calls, 195 PRs | 3 search calls, the owner's PRs |
| next round (`derive.refresh`, per `pr.poll_seconds`, shared by seats via `prs.json`) | 3 GraphQL | 3 GraphQL (unchanged) |

## Verification

`python -m pytest -q` on every test file that imports a changed module, with the pipeline
venv (3.12), then the code_host, doctor, why, plan (discovery) and next files under 3.11.
