# Implementation Plan: an owner-approved Owner step applies when run again

**Branch**: `924-owner-cards` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

Built with [../856-card-binding/plan.md](../856-card-binding/plan.md), which fixes the binding
that caused the field failure.

## Summary

`needs_owner` is the one function every owner-only refusal goes through. It approves on the
card's Yes (bound by #856), appends `owner.approved`, and otherwise returns the one-line refusal,
which now says where the answered command applies. No terminal answer is read.

## Technical Context

Stdlib Python 3.11+. One new event kind, `owner.approved` (silent); no state field.

## Constitution Check

- III: one approval function (`needs_owner`).
- IV: tests first: the field sequence through `main`, the refusal line, and a pseudo-terminal
  run that must refuse.
- V: no flag, no new command; the refusal gains one clause.
- VII: the card is the only approval (review F1).

## Files to edit

- `cli/wuwei/sessions.py`: `needs_owner`.
- `cli/wuwei/signal.py`: `owner.approved` is silent.
- Tests: `test_card_confirms.py`, `test_signal_status.py`.
- Docs: design 9.1 amendment (for owner review), `docs/site/concepts.md`.
