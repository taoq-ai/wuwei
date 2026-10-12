# Implementation Plan: a seat's honeytoken read parks its item and holds the close

**Branch**: `878-honeytoken-parks` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

## Summary

Move the park update out of `scanner._trace_response` into `scanner._park(finding, reason, root)`
and add `scanner.honeytoken(session, root)`, which calls it for an item seat's session. The
recorder (`guards/traces.check`) calls `scanner.honeytoken` after `_record` has bound the
session. `closing.scanner_hold` holds the close on the critical finding with no change.

## Technical Context

Python 3.11+ stdlib. Files: `cli/wuwei/scanner.py`, `cli/wuwei/guards/traces.py`. Tests:
`tests/test_canary.py` (recorder with real security material).

## Constitution Check

- II: exits unchanged; the recorder never refuses (#601, #837).
- IV: failing test first.
- V: one extracted helper, one new function, one call; no new module or config.
- VII: the seat's strongest signal now parks and holds; the guards floor is untouched.

## Changes

1. `scanner.py`: `_park(finding, reason, root)` holds lines 137-147 of today's
   `_trace_response`, which calls it. `honeytoken(session, root)`: if a non-adhoc seat lists
   the session, `_park({'chain': ['security.honeytoken'], 'risk_level': 'critical',
   'session_id': session}, 'security.honeytoken read', root)`.
2. `guards/traces.py` `check`: after `_record` returns 0, if `'honeytoken' in findings`, call
   `scanner.honeytoken(payload['session_id'], root)` (the id `_record` bound, with the
   subagent suffix and hashing applied).
