# Implementation Plan: a plan pass offers a goal as met when its date passed

**Branch**: `feat/goal-met` | **Spec**: `specs/goal-met/spec.md`

## Summary

One reader in `view.py` (beside `goals()`) turns goals.md and the goal.met rulings into the goals to
offer and the goals met. `wuwei plan pass` prints the first, `report.day` the second, and
`hook._answers` writes the rulings.

## Technical Context

Python 3.11 stdlib. Tests in tests/test_plan.py, tests/test_hook.py, tests/test_report.py and
tests/test_codex.py. Runtime 2,986 lines at 3d2eb29; the item's budget is 13.

## Constitution Check

- I. Stdlib only: yes, `re`.
- III. An auditor: WUWEI records the owner's answer and reads goals.md; it never edits goals.md.
- V. Test first: the new tests ran red (5 failed, 0 recorded of 20,736 probe questions) before the
  change.
- VI. Budgets: no config key; one new ruling kind; runtime at 2,999.

## Design

- `view.goal_status(root)` returns `(due, met)`. It maps each goal id to its latest goal.met ruling
  as `(approved, day)`. `due` holds the `G-n` goals whose ISO date is before today, whose latest
  ruling is not met, and whose latest ruling day is before the date (no ruling reads as '').
  `met` holds the goals whose latest ruling is met.
- `__main__` imports `view` at the top (the lazy import in the `view` action goes) and prints one
  line per due goal after "plan pass recorded".
- `hook._answers` matches `\s*goal: *(G-[0-9]+) met\?` (any case), records the ruling with the id
  upper-cased and adds a note: "recorded as met." or "recorded as open; ...".
- `report.day` adds `Met goals: ...` to the Plan section.
- `charters/lead.md`, `skills/wuwei-run/SKILL.md` and `docs/design.md` gain one sentence each;
  `bin/wuwei agents build` and `setup.vendor('.')` refresh the copies.

## Lines

view.py +6, hook.py +3, `__main__.py` +1 (+2, -1), report.py +1: runtime 2,986 to 2,999.
