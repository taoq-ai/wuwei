# Implementation Plan: a gate is read from its verdict at the newest head on this PR

**Branch**: `fix/verdict-at-head` | **Spec**: `specs/verdict-at-head/spec.md`

## Summary

`evidence.gate_gaps` walks each gate's verdicts with the ancestry walk `breaking_gaps` gained in
#1135, instead of taking the last one in ledger order. A PASS counts only for this PR; a finding
at an ancestor head holds from any PR of the item.

## Technical Context

Python 3.11 stdlib. Tests in `tests/test_evidence.py`; fixtures in `tests/test_guards.py` that
named another PR are pointed at the PR their door reads. Runtime budget 3,400 lines; main is at
2,993 and this item's budget is 5.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; an existing gap reads fewer verdicts as passes. The ancestry
  checks are the compare calls `gate_gaps` already makes.
- V. Test first: the new fixtures ran red on main (7 failed), green at the head.
- VI. Budgets: no config key, no ledger kind; runtime +5 (2,998).

## Design

- `cli/wuwei/evidence.py`:
  - `newer(repo, v, held, head)`: the #1135 walk's replacement test, moved out of
    `breaking_gaps` so both readers share it. It is true when nothing is held, or when v's head
    differs from the held head (first 7 characters), descends from it, and is an ancestor of the
    PR head.
  - `breaking_gaps` calls `newer`; its behaviour is unchanged for parsed verdicts.
  - `verdicts` gives each parsed verdict a `ref` (`owner/repo#n`, or `owner/repo` before the
    draft), read from the verdict body.
  - `gate_gaps` walks each gate oldest first. A verdict is read only at an ancestor of the PR head.
    A PASS is read only when its `ref` is this PR, this repository alone, or absent (an imported
    0.34 verdict); with no PR read (the create and ready doors) its repository must match. A
    verdict replaces the held one when `newer` says so, or when it is a finding and the held one
    is a PASS. The small-delta carry rule is unchanged.
- `docs/design.md`: the verdict paragraph states the reading.
- `.claude/wuwei/` re-vendored with `setup.vendor('.')`.
- `specs/verdict-at-head/probe.py` and `route_probe.py`: the main-versus-head probes.
