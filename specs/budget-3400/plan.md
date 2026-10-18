# Implementation Plan: the runtime budget is 3,400 lines and config holds six keys

**Branch**: `docs/budget-3400` | **Spec**: `specs/budget-3400/spec.md`

## Summary

Raise the stated runtime budget from 3,000 to 3,400 lines and the config budget from five keys to
six, in the documents and the size test. Amend the constitution to 3.2.0.

## Technical Context

Docs and one test. Runtime at 2,976 lines (`cat cli/wuwei/*.py | wc -l`); it does not change. None
of the six files is vendored under `.claude/wuwei/` (it holds `bin`, `charters` and `cli`).

## Constitution Check

- I. Stdlib only: no runtime change.
- V. Test first: a scratch copy of main padded to 3,100 lines fails the size test (red); the same
  copy of the head passes, and a copy at 3,401 fails naming 3400.
- VI. Budgets: this item sets them. Runtime lines: 0. Config keys: none added here.
- Governance: the amendment is a commit to the constitution with a dated line in its message.

## Design

- tests/test_setup.py:113: 3000 to 3400 in the assertion and its message.
- Constitution VI: 3,400 lines, six keys named, one added rule; version 3.2.0, amended 2026-10-18.
- AGENTS.md, CONTRIBUTING.md: 3,000 to 3,400.
- design.md: principle 8 and section 11 say six keys, section 11 names `models` and 3,400.
- philosophy.md: 3,400 lines and six keys.
- SECURITY.md:135: 3,400 lines (added at the planner's request after a repo-wide grep).
