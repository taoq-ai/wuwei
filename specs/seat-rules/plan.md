# Implementation Plan: seat-rules

**Branch**: `claude/seat-rules` | **Spec**: `specs/seat-rules/spec.md`

## Summary

Six charter rules in four charters, `agents/` rebuilt and `.claude/` re-vendored.

## Technical Context

Charters in `charters/` are the one source for `agents/`; sentinels are built from `_common.md`,
`_gate.md` and the role charter, so a `_gate.md` rule reaches all four sentinels. `planner.md` is
not built into `agents/`; it is vendored into `.claude/wuwei/charters/`.

## Constitution Check

- I. Stdlib only: no runtime change.
- III. An auditor: no door or guard logic changes.
- V. Test first: six tests ran red before the edits.
- VI. Budgets: runtime lines unchanged.

## Design

- `_gate.md` rule 3: the differential-probe sentence. New rule 4: the generated combinatorial
  probe, its counts, the re-run, the door-word-free checks, the fixture rule. Old 4 to 6 become 5
  to 7.
- `builder.md` VAL: the generated probe, its counts in the PR, the fixture rule.
- `planner.md` Running the work 2: the together-forward rule.
- `steward.md` rule 4: lesson placement by scope.
- Tests in `tests/test_setup.py` read the built agents and the two charters.
