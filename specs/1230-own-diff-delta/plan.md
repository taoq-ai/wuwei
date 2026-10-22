# Implementation plan: 1230-own-diff-delta

**Spec**: `specs/1230-own-diff-delta/spec.md`
**Item**: 1230, tier full, goal G-2

## Technical context

- Stdlib-only Python 3.11+, runtime under `cli/wuwei/`, cap 3,400 lines. Main fbf187b holds
  3,373; the item's budget is +8.
- `evidence.gate_gaps` finds the last passing head on the PR head's line, then measures
  `compare(root, repo, last, head)['files']` and asks `needed()` for the one gate.
- `evidence.compare` caches a compare a day when both ends are shas; `gh.compare` keeps path,
  additions and deletions per file. `gh._summary` keeps the base branch name only.
- Callers: `evidence.gaps` (board, `wuwei evidence`, merge door) and `guards.create_door` (create
  and ready doors), which already reads `gh.compare(repo, base branch, branch)`.

## Design

1. `gh.compare` keeps each file's `patch`; `gh._summary` keeps `baseRefOid` (`base.sha`).
2. `gate_gaps(..., base='')`: given a base sha, read `compare(base, last)` and `compare(base, head)`
   (three dots: each head's own diff), key each file by its patch with `@@` lines reduced to `@@`
   (a missing patch is a fresh `object()`, so it never matches). The moved files are the keys that
   differ, less those a dated `Generated (<repo>, <date>):` line of `.wuwei/standards.md` names.
3. The delta is each moved file's head-to-head entry, or its own entry when the head-to-head
   compare does not list it; with an own diff at GitHub's 300-file cap, the head-to-head compare.
4. `gaps` passes `pr.get('baseRefOid')`; `create_door` passes the compare's `merge_base_commit`.
   A missing base keeps today's measure.

## Cost

Two more compares per PR whose passes sit below the head, each cached a day for two shas. A warm
board makes no new host call.

## Proof

- Tests first: each acceptance scenario, the probes the brief named (a conflict resolution that
  edits the PR's own lines, a base merge in the PR's file on far and adjacent lines, an
  update-branch merge commit), the door paths, red at fbf187b.
- `probe.py`: real git merges, 13 kinds x 2 path classes, read at main and the head.
- `route_diff.py`: the route corpus under three hosts at main and the head.
- Mutants of each rule, applied to both runtime copies, one at a time.
