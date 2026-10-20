# Implementation Plan: the one-way ADR note follows the repository's own ADR home

**Branch**: `fix/adr-home` | **Spec**: `specs/adr-home/spec.md`

## Summary

Reword the one-way note, the planner's one-way bullet and the arch charter's ADR reference so the
ADR goes where the repository keeps its ADRs, and a re-confirmed ADR is amended.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_hook.py and tests/test_charters.py. Runtime budget 3,400
lines; main is at 3,317 (after #1172) and the item allows one line.

## Constitution Check

- I. Stdlib only: yes, text only.
- III. An auditor: no door changes; the note is advice in PostToolUse context.
- V. Test first: both new tests ran red (2 failed) before the change.
- VI. Budgets: no config key; runtime 3,317 to 3,318; arch agent 2,250 to 2,249 words.

## Design

- `hook._answers`: the note string grows from two lines to three.
- `charters/planner.md`: the one-way bullet becomes three sentences: the ADR through the item's PR,
  where it goes, and the amend rule.
- `charters/sentinel-arch.md`: "the ADRs under `docs/adr/`" becomes "the repository's ADRs".
- `docs/site/concepts/decisions.md` and `index.md` follow the charter.
- `bin/wuwei agents build`, then `setup.vendor('.')`.

## Lines

hook.py 565 to 566: runtime 3,317 to 3,318.
