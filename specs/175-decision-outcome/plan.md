# Implementation Plan: Decision outcomes and two-way digest

**Branch**: `175-decision-outcome` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

## Summary

Use the existing decision evaluator and state writer for a confirmed owner outcome. Resume linked items with the existing lifecycle rules. Count reversal events. Let the watch sweep batch new seat outcomes, call the chat port, and retain approval-tier text as a local draft.

## Technical Context

Python 3.11+ stdlib runtime, pytest tests, existing JSON day state and JSONL events. No external tools in tests.

## Constitution Check

- Test each behavior red before implementation.
- Use the existing atomic writer, state allowlist, event reservation, chat port and outward tiers.
- Exit 0 for completion, 1 for invalid or declined actions, 2 for unreadable evidence and unavailable delivery.
- Keep owner confirmation outside agent tools, using the existing host terminal mechanism.

## Design

1. `decision outcome` evaluates today's record and validates the chosen option, existing route or seat outcome, and the linked item. A host challenge binds confirmation to the choice and current record. State stores the owner answer; the event records a reversal only if it differs from a seat choice. The linked item resumes through the state transition lifecycle.
2. Metrics use the trusted reversal event stream. Once a seat decision is recorded, zero is measured when there are no reversals.
3. The sweep selects seat outcomes absent from the watch digest ledger, sends one batch through chat DM, and stores the draft if outward policy requires review. It saves the digest timestamp and IDs in reserved watch state only after delivery or draft creation. A failed port is exit 2 with a reason.
4. Use a fixed two-hour digest interval.

## Validation

Run focused failing and passing tests, then the required full pytest suite. Check changed files for local absolute paths, em-dashes and emojis.

## Deferred

General approval draft sending belongs to issue 174.
