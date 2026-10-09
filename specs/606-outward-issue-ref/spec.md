# Feature Specification: An issue reference no longer fails the outward lint

**Feature Branch**: `606-outward-issue-ref`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #606 (light tier)

## Promise

A bare `owner/repo#N` reference that names an issue, not a pull request, is read as an
issue reference: the outward lint goes on without PR context instead of stopping with
the 404 from the pulls endpoint.

## Root cause

`cli/wuwei/outward.py` `_pr_context` (line 267) treats every `owner/repo#N` reference as a
pull request and calls `host.pr(ref)` (line 293). The GitHub adapter's `pr`
(`adapters/code_host/github.py` line 192) reads `repos/{repo}/pulls/{N}`; for an issue
that endpoint 404s, `_run` (line 113 onward) raises `gh exited 1 (owner/repo): gh: Not
Found (HTTP 404)` and `_operation` returns exit 2 with that reason. `_pr_context` returns
any nonzero exit as is (line 294 to 295), so the outward step stops with "could not run".

## User Scenarios and Testing

### User Story 1 - Issue reference in a configured repository (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a body citing `acme/app#1` where #1 is an issue in a configured repository,
   **When** the outward lint runs, **Then** it completes without an error and without PR
   context (the same result as a reference it does not recognise).
2. **Given** a reference to an open internal pull request, **When** the lint runs,
   **Then** the PR context is read as today.
3. **Given** a code host error other than not found, **When** the lint runs, **Then** it
   still reports it (exit 2).
4. **Given** a `https://github.com/owner/repo/pull/N` URL that 404s, **When** the lint
   runs, **Then** it still fails as today.

## Requirements

- **FR-001**: When the code host `pr` lookup on a bare `owner/repo#N` reference (no
  `/pull/` URL, no `pull_number` in the context) returns exit 2 with an `(HTTP 404)`
  reason, `_pr_context` returns the no-PR-context result `(1, '')`.
- **FR-002**: Every other `pr` error keeps returning its exit.
- **FR-003**: No second network call.

## Assumptions

- The GitHub adapter's 404 reason carries gh's stderr line `... (HTTP 404)`; matching that
  text narrowly is the signal. Other code host adapters that never report it keep today's
  behaviour.
- A context that names `pull_number` explicitly asserts a pull request, so its 404 keeps
  failing like the `/pull/N` URL.
- Out of scope: the GitHub tracker auth fallback.
