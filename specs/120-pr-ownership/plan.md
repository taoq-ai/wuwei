# Implementation Plan: PR ownership loop

**Branch**: `120-pr-ownership` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Extend the existing PR action reader into the dedicated action producer. Share watch's fresh
code-host evidence validation with state classification. Return dispatch as data. Preserve
#16's Stop scope and owner disposition verification, and #15's watch scheduling and wake.

## Technical Context

Python 3.11+, stdlib runtime, pytest development tests. Existing day state and append-only
JSONL events under the shared writer lock. No new external commands or dependencies.
Only owned PRs are measured; tests use recorded fake ports and the injectable workspace clock.

## Constitution Check

Pass before and after design: stdlib only; 0/1/2 fail-closed results; one shared producer;
failing tests before implementation; existing scope and relevance helpers; no speculative
abstractions. The current worktree supplies isolation. No commits, pushes or extension hooks.

## Project Structure and design

- `cli/wuwei/pr_actions.py`: classification, dispatch data, persistent episodes in reserved
  `watch.actions`, review waiting in reserved `watch.reviews`, overdue events, and fresh Stop
  evaluation. Existing verified dispositions remain authoritative.
- `cli/wuwei/watch.py`: share fresh evidence with the producer from the existing poll loop.
  Keep snapshot comparisons and wake behavior. Unreadable evidence retains prior episodes.
- `cli/wuwei/commands/pr.py`: `state [refs...]` emits JSON rows and aggregate exit status.
- `cli/wuwei/workspace.py` and `docs/site/configuration.md`: validated timing configuration.
- `cli/wuwei/signal.py`, `cli/wuwei/commands/event.py`: classify and reserve action events.
- `cli/wuwei/security.py`: extend the existing `gh_outbound` helper called by guards/pr.py
  to inspect body-file disposition markers even without configured security tokens.
- `tests/test_pr_ownership.py`: classification, timing, command, trust and hook coverage.
  Update #16 placeholder action tests to use actual fresh code-host conflicts.

## State contract

An action stores state, human-readable action, created_at, deadline and last escalation tier.
Unchanged states retain timing despite head or comment updates. A measured transition retires
or replaces the action. A waiting record stores head and first observation time; it resets
when the head changes. The producer rereads ledgers under the shared lock before mutation.
Output includes PR, state, action, dispatch, deadline, overdue, parked and exit. Unreadable
rows include a reason. No comment bodies enter state or events. Poll and Stop use the same
producer as the command. No cache is used to decide current state.

## Verification

Three sequential test-first slices: classification/CLI, deadlines/watch/Stop/signals, native
body-file trust. Cover all code-host states, API failures, unanswered thread recurrence,
parking tampering, deadline boundaries, repeated reads, next-day isolation and scope. Then
run the complete suite, inspect diff, and scan authored files for forbidden text and paths.
