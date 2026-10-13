# Implementation Plan: Re-read GitHub quota after a zero-header refusal

**Branch**: `953-limit-reread` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Update the shared `gh_limit` classifier so a primary zero-remaining reply triggers one same-environment quota read. Compare the same resource, use a short hold on disagreement, and retain the refused reply's reset when the read fails or confirms exhaustion. Label the credential source without exposing its value. Secondary refusals use the short hold without a quota read.

## Technical Context

- Python 3.11+ standard library runtime; offline pytest with replayed subprocess replies.
- No storage, new module, dependency, or new CLI path.
- Existing `retry` applies the configured wait cap and retries a call once.

## Root Cause and Data Flow

`adapters/code_host/github.py:131-143` passes the refused call's `env`, resource, and parsed headers into `adapters/_http.py:84`. At `_http.py:95-98`, headers bypass the quota read, and line 111 chooses the stale reset. GitHub code-host operations and the gh-backed tracker use `gh_limit`, so this is the shared fix point.

## Constitution Check

- Stdlib only: pass. Use existing subprocess and JSON parsing.
- Three-state exits: pass. A failure still reaches the adapter as exit 2.
- One behavior in one function: pass. Classify in `gh_limit`; `token_scopes` passes its measured source name to the shared reason path.
- Test first: replay the reported primary wording and conflicting readings before implementation.
- Security: derive source from variable names, never values.
- Simplicity: no cache, token probe, or new API path.

## Project Structure

- `adapters/_http.py`: shared classification and safe reason.
- `adapters/code_host/github.py`: pass the original `token_scopes` variable name to the shared reason path.
- `tests/test_code_host.py`: recorded field case, same-env, fallback and source tests.
- `tests/test_pr_actions.py`: command-level regression.
- `specs/953-limit-reread/`: spec-kit artifacts.

## Verification

Run the issue's interpreter with explicit test files importing the changed module. Review the final diff for accidental secret values or extra requests.
