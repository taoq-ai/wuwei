# Implementation Plan: Review Item Dispatch

**Issue**: #939 | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

## Summary

Carry an explicit candidate kind and review target through admission. Move review items into the existing one-role gate phase at approval. Prepare the same-repository PR worktree, then use the ordinary gate brief, receipt, and decision path.

## Technical Context

- Python 3.11+ stdlib runtime, pytest development tests.
- Existing day JSON state and CLI writers only.
- Reuse existing PR listing, worktree, brief, seat, and verdict paths.

## Constitution Check

- Runtime remains stdlib-only.
- Admission validates the new external fields once.
- Tests reproduce PR-3168-DELTA before the fix.
- No new module or persistent service.
- The design document remains owner-only.

## Source Changes

- `cli/wuwei/plan.py`: validate and retain kind and review target.
- `cli/wuwei/dispatch.py`: prepare the PR head, refuse forks, and route a review through the existing gate decision.
- `cli/wuwei/dispatch.py`: check stale worktree ancestry before offering a fast-forward, and include verdict paths in done actions.
- `adapters/code_host/github.py`, `cli/wuwei/commands/worktree.py`: carry PR branch metadata and reuse an existing branch worktree.
- `cli/wuwei/brief.py`, `cli/wuwei/derive.py`: validate a live PR head at briefing and receipt, and show the one-role gate lifecycle.
- `cli/wuwei/commands/plan.py`: expose kind and review target on add and set.
- `cli/wuwei/derive.py`: exclude review verdict items from ordinary PR duties.
- `charters/lead.md`, generated agent: name the candidate kind.
- Existing plan, dispatch, and brief test files: prove the field case.
- Close omits done review items and avoids the unclaimed pushed branch finding for an unfinished review.
- Report lists finished review verdicts and workspace-relative verdict files in Done.
