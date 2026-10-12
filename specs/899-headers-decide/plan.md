# Implementation Plan: a refusal's own rate-limit headers decide the bucket

**Branch**: `899-headers-decide` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

`_run` adds `--include` to every single-page `gh api` read (REST GET and GraphQL query) and
cuts the head off stdout before the body is parsed. On a refusal, `gh_limit` takes resource,
remaining, limit and reset from that head when they are valid and reads `gh api rate_limit`
only when they are not. The token hint and the "both readings" text go.

## Technical Context

Stdlib Python 3.11+. No new state, no config, no new request.

## Constitution Check

- III: one path for every gh rate limit (`gh_limit`), now with one decider per reply.
- IV: tests first, red, then code.
- V: shortest diff; the note shrinks, the rate_limit request is skipped whenever headers exist.

## Files to edit

- `adapters/code_host/github.py`: `_run` appends `--include` for reads (not writes, not the
  revert mutation, not `--paginate`), passes the parsed head as integers to `gh_limit`, and
  strips the head from a successful read.
- `adapters/_http.py`: `gh_limit` decides from `seen` when given, else from rate_limit; the
  note is one short sentence with no token hint.
- `tests/fixtures/code_host/recordings.json`, `tests/test_merge_ports.py`,
  `tests/test_env_credentials.py`: read argv carry `--include`.
- `tests/test_code_host.py`, `tests/test_pr_actions.py`: the #899 cases.
- `specs/891-rate-limit-truth/spec.md`: Assumptions note that #899 superseded its decider.
