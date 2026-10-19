# Implementation Plan: a gate is read from its verdict at the newest head on this PR

**Branch**: `fix/verdict-at-head` | **Spec**: `specs/verdict-at-head/spec.md`

## Summary

`evidence.gate_gaps` walks each gate's verdicts with the ancestry walk `breaking_gaps` gained in
#1135, instead of taking the last one in ledger order. A PASS counts only for this PR; a finding
at an ancestor head holds from any PR of the item.

## Technical Context

Python 3.11 stdlib. Tests in `tests/test_evidence.py`; fixtures in `tests/test_guards.py` that
named another PR are pointed at the PR their door reads. Runtime budget 3,400 lines; main is at
3,026 (5fe8347) and this item's budget is 5.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no new door; an existing gap reads fewer verdicts as passes. The walk adds
  compare calls. Each verdict's head is asked about the PR head once, as on main; each verdict
  that could replace the held one is also asked whether it descends from it. Counted with a fake
  host over one line of N heads, three gates verdicted per head, read at the last head
  (`python3 -I specs/verdict-at-head/calls.py <tree> <scratch folder>`): main 27
  calls at 10 heads and 57 at 20; this head 54 and 114 (2.0x main). Round 0 asked the PR-head
  pair twice (78 and 168); round 1 removed the repeat. On the history probe's short histories
  (at most 3 verdicts) the PR filter skips more calls than the walk adds (see spec.md).
- V. Test first: the new fixtures ran red on main (7 failed), green at the head.
- VI. Budgets: no config key, no ledger kind; runtime +5 (3,026 to 3,031).

## Design

- `cli/wuwei/evidence.py`:
  - `newer(repo, v, held, head)`: the #1135 walk's replacement test, moved out of
    `breaking_gaps` so both readers share it. It is true when nothing is held, or when v's head
    differs from the held head (first 7 characters), descends from it, and is an ancestor of the
    PR head.
  - `breaking_gaps` calls `newer`. An arch `Breaking: no` clears a yes only when it names this PR
    or its repository alone; a yes holds from any PR, as a finding does.
  - `verdicts` gives each parsed verdict a `ref` (`owner/repo#n`, or `owner/repo` before the
    draft), read from the verdict body.
  - `gate_gaps` walks each gate oldest first. A verdict is read only at an ancestor of the PR head.
    A PASS is read only when its `ref` is this PR, this repository alone, or absent (an imported
    0.34 verdict); with no PR read (the create and ready doors) its repository must match. A
    verdict replaces the held one when `newer` says so, or when it is a finding and the held one
    is a PASS. `gate_gaps` passes the verdict's own head to `newer`, because it has already asked
    whether that head is under the PR head. The small-delta carry rule is unchanged.
- `docs/design.md` and `docs/site/concepts/evidence.md`: the verdict paragraph states the reading.
- `.claude/wuwei/` re-vendored with `setup.vendor('.')`.
- `specs/verdict-at-head/probe.py`, `route_probe.py` and `calls.py`: the main-versus-head probes.
