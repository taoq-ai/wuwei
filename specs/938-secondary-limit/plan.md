# Implementation Plan: Scope secondary GitHub rate limits to the refused endpoint

**Branch**: `938-secondary-limit` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Classify explicit secondary-limit evidence before the zero-remaining primary branch in the shared `gh_limit` function. Keep secondary retry timing and endpoint wording local to the refused call. Preserve primary exhaustion behavior.
Apply the same precedence to direct GitHub HTTP 403 responses in `_github_limit`.

## Technical Context

- Language: Python 3.11+.
- Runtime dependencies: standard library only.
- Storage: none; no persisted rate-limit block exists.
- Testing: offline pytest replay in `tests/test_code_host.py`, primary-limit coverage in
  `tests/test_tracker_adapters.py`, and all test files importing the changed module.
- Constraint: no added module, subprocess, or network call.

## Root Cause and Data Flow

`adapters/code_host/github.py:133-142` extracts `Retry-After` and rate-limit headers from the refused `gh api --include` reply, then passes them to `adapters/_http.py:84`. At `adapters/_http.py:103`, `remaining == 0` is checked before secondary wording or `Retry-After`. The result uses the primary reset and the core-zero message. `retry` at `adapters/_http.py:113` is per call; neither `derive.py` nor the day state persists a GitHub block.

## Constitution Check

- Stdlib only: pass.
- Three-state exits and safe messages: pass; `RateLimited` still becomes exit 2 through the adapter.
- One behavior in one function: pass; classification changes in shared `gh_limit`.
- Test first: write and observe the failing field replay before runtime code.
- Simplicity: keep existing `RateLimited`, `retry`, and adapter path; no cache or new endpoint registry.
- Security: preserve the sanitized endpoint name and avoid provider body text.

## Project Structure

- `adapters/_http.py`: shared GitHub rate-limit classification.
- `tests/test_code_host.py`: Actions jobs to pulls regression and existing rate-limit cases.
- `tests/test_tracker_adapters.py`: primary-limit retry case using primary wording.
- `tests/test_doctor.py`: primary wording for the primary-reset and no-wait fixture.
- `specs/938-secondary-limit/`: feature artifacts and analysis.

## Verification

Run the exact interpreter named in the issue with `-m pytest -q -p no:cacheprovider` and explicit files that import the changed module. Keep all replayed GitHub calls offline.
