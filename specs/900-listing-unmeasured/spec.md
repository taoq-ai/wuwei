# Feature Specification: a failed listing read leaves that repository's PR rows unmeasured

**Feature Branch**: `907-github-reads` (feature 900-listing-unmeasured, batched with #907)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #900: `next` keeps a stale PR listing on a code-host 5xx, so an approved
PR with red CI raises no fix launch.

## Root cause (0.29.0)

On a failed `pulls` call, `derive.refresh` keeps the whole old listing and `next` prints one
stderr line (`cli/wuwei/commands/next.py:460`). `derive.offers` then decides merge, gates and
fix from that stale check state as if it were current.

## User Scenarios & Testing

### User Story 1 - no decision on stale check state (P1)

1. **Given** a raised PR whose repository's listing read failed (HTTP 502) and a stale row for
   it saying red, **When** next derives its offers, **Then** that PR gets no merge, gate, fix or
   park step, and its row is `unmeasured`, naming the repository, the reason and the time next
   reads it again (`at + pr.poll_seconds`).
2. **Given** another repository read fine, **Then** its PRs are offered as usual (a green PR
   merges).
3. **Given** only PR waits remain, **Then** next's wait line names each unmeasured PR and its
   retry time; in a launch set, each unmeasured row is a text line.

## Requirements

- **FR-001**: `derive.offers` short-circuits a raised item (or a stale `closed` row) whose PR
  repository's last read failed into an `unmeasured` row. A PR with no row at all keeps its
  `pr act` step, which reads that PR fresh; no stale state decides there.
- **FR-002**: `wuwei next` counts unmeasured rows as waits and prints their reason.
- **FR-003**: a counterpart line in a brief never quotes a failed repository's rows.

## Assumptions

- The listing already uses GraphQL (`adapters/code_host/github.py` `pulls`), so the issue's
  "retry through GraphQL" is the per-repository retry itself; no second path.
- A merged state from a stale row still counts: merged is final.
- "Raise fix whatever phase the record holds" (the issue's third ask) depends on #889's
  registration of fix rounds and is left to it.
- Plan, tasks and analysis are shared with `specs/907-github-reads/` (one batch, one diff).
