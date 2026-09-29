# Implementation Plan: Generic writer allowlists

**Branch**: `114-state-allowlist` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Replace deny-by-name checks with explicit allowed state paths and the free event kind `note`.
Keep generic callback protection in the existing locked writer, comparing all state except
allowed fields. Check set paths explicitly so even no-op writes to producer fields refuse.
Preserve the approval freeze and disallow item creation through notes. Dedicated transition
and brief producers use `_write_state(..., reserved=False)` like other producers.

## Technical Context

- Language: Python 3.11+, stdlib runtime; pytest for tests.
- Storage: existing JSON state and JSONL events, flock and atomic writer, mode 0444.
- Platform: existing POSIX CLI; no new dependencies or adapters.
- Scope: `cli/wuwei/state.py`, `cli/wuwei/commands/event.py`, `cli/wuwei/brief.py`, tests.
- Performance: retain one lock per operation; source-driven meta-test runs in process.

## Constitution Check

Before and after design: passes. Reuse the single writer, validation, clock and lock. Tests
precede code. No new subprocess boundary or runtime dependency. Preserve three-state exits,
workspace discovery and the design's same-uid residual. No specification amendment required.

## Design Decisions

- Root `cap` and `seat_policy` are tunable before approval only. Descendants of seat_policy
  are policy data, not root evidence. Only `items.<existing-id>.note` is an editable item path.
- Remove RESERVED and recursive reserved-name scanning entirely. Compare a protected snapshot
  that excludes allowed settings and existing notes; unknown data remains protected by default.
- Producer hints are diagnostic mappings, not authorization lists. Unknown fields/kinds use
  the generic dedicated-command message. Keep the word reserved for existing diagnostics.
- The event command allows only note; internal append_event remains available to producers.
- A conservative source scan covers readers across cli/wuwei (excluding the generic writer
  and generic event command), collecting dictionary keys, helper arguments, container literals and event comparisons,
  including kind prefixes. Permission checks are independent of value validation. Exercise generic commands for these values and maintain coverage assertions.
- Existing tests using the generic API for trusted fixture setup move to internal producer
  writes. Transition-specific tests use transition. Validation tests still exercise the writer.

## Project Structure

- `specs/114-state-allowlist/{spec,plan,tasks}.md` and `checklists/requirements.md`.
- `tests/test_state_allowlist.py`: new refusals, allowed paths, producers and reader inventory.
- `tests/test_state.py` and affected suites: migrate fixtures and obsolete generic-write expectations.
- Existing runtime modules only; no new registry or abstraction.

## Implementation Strategy

Add failing allowlist and reader coverage tests, run them, implement state protection and
producer migrations, then implement event restriction after its failing tests. Update fixture
setup without weakening guard assertions. Run focused tests and the full requested suite.
Review the final diff for scope, unsafe invocations, local paths and prohibited characters.

## Deferred

Public PR-set and other metadata producers missing from main remain outside this patch.
Their test fixtures use the internal writer; refusal hints stay generic when no command exists.
