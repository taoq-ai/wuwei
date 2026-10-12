# Implementation Plan: the builder loop is not a parking scanner chain

**Branch**: `870-scanner-builder-loop` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

One set and one early return in `scanner._trace_response`: a seat chain made only of local
file and shell tools returns before it pages or parks. The parked chain's event carries its
`reason`. `status.attention` keys `scanner.finding` by chain so doctor shows one row per class.

## Technical Context

Python 3.11+ stdlib. Files: `cli/wuwei/scanner.py`, `cli/wuwei/commands/status.py`. Tests:
`tests/test_traces_seats_only.py` (sweep), `tests/test_signal_status.py` (attention),
`tests/test_ziran.py` (the payload assertion gains `reason`).

## Constitution Check

- II: unchanged exits; ZIRAN unmeasured stays unmeasured.
- IV: each change has a failing test first.
- V: one frozenset, one `if`, one key branch; no new module, no config.
- VII: the outward chain keeps parking; the edges floor is untouched.

## Changes

1. `scanner.py`: `LOCAL = frozenset({'Read', 'Grep', 'Glob', 'Edit', 'MultiEdit', 'Write',
   'NotebookEdit', 'Bash'})`; in `_trace_response`, after the non-seat branch,
   `if LOCAL.issuperset(finding['chain']): return False`. Append `{**finding, 'reason': reason}`.
2. `status.py` `attention`: for `scanner.finding` with a dict payload, key
   `(kind, ' -> '.join(chain) or rule)`.
3. Update `test_seat_wins_over_registration`, which pinned the bug (seat `Bash -> Write`
   parks), to an outward chain.
