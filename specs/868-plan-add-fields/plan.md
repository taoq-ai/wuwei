# Implementation Plan: 868-plan-add-fields

**Spec**: `specs/868-plan-add-fields/spec.md` | **Branch**: `864-plan-admit` (shared with #864)

## Summary

`plan add` takes the fields `plan propose` carries and validates them with the same function.
The per-candidate track, flags and governed_by checks in `_proposal` move into one helper,
`plan._admitted(name, item, tree=None)`, which `_proposal` and `add` both call; governed_by
goes through #864's `plan.governed`. The item records `repo`, and `dispatch._start` reads it.

## Technical Context

Python 3.11+, stdlib only. Files: `cli/wuwei/plan.py`, `cli/wuwei/commands/plan.py`,
`cli/wuwei/dispatch.py`, `charters/planner.md` (one sentence). Tests: `tests/test_plan.py`,
`tests/test_dispatch.py`.

## Constitution Check

- III: one validation function for propose and add (no second path). IV: tests first.
  V: no new module; argparse adds plain options, validation stays in `_admitted`.
  II: an invalid value is a ValueError (exit 2), as propose.

## Design

1. `_admitted(name, item, tree=None)`: track SLICE or FULL, the three boolean flags, and
   `governed(name, item['governed_by'], tree)` when present. `_proposal` calls it in place of
   its three inline checks.
2. `add(..., repo=None, track='SLICE', governed_by=None, flags=())`: builds the candidate with
   these values; for an owner item, a repository is required when several are configured and
   must be a configured one; `_admitted(item, candidate, checkout(...))` before any write; the
   admitted record copies `repo` and `governed_by`.
3. CLI: `--repo`, `--track`, `--governed-by`, `--trust-surface`, `--boundary-relevant`,
   `--agent-surface`.
4. `dispatch._start`: the repository is the state item's `repo`, else the proposal row's.
5. Planner charter: the admission sentence names `--repo` (several repositories) and the track,
   flag and governed-by options.
