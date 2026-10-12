# Implementation Plan: a rate limit refusal names the bucket only when gh api rate_limit confirms it

**Branch**: `891-rate-limit-truth` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

Delete the `--include` re-ask and `included_limit`. Every gh rate limit goes through
`gh_limit`, which reads `gh api rate_limit` for the call's resource: 0 left is the bucket and
its reset; calls left is a secondary limit only when gh's text says secondary or Retry-After
was sent, else both readings are named with a same-token hint.

## Technical Context

Stdlib Python 3.11+. No new state, no config.

## Constitution Check

- III: one path for every gh rate limit (`gh_limit`); a deletion, not a new branch.
- IV: tests first, red, then code.
- V: shortest diff; fewer requests than 0.29.0.

## Files to edit

- `adapters/code_host/github.py`: `_run.call` raises `gh_limit(stderr, env, resource, where,
  after)`; `where` is the endpoint without its query (`search` for a search); `after` is
  `Retry-After` from an `--include` reply's head. `_headers_limit` deleted.
- `adapters/_http.py`: `gh_limit` takes `where` and `after`; `RateLimited` names them on a
  secondary limit; `included_limit` deleted.
- `tests/test_code_host.py`: the header-trusting #867 tests replaced by the #891 cases.
- `tests/test_pr_actions.py`: `pr act` through the real adapter with replayed gh.
