# Implementation Plan: a cache entry or name never reads, writes or deletes outside .wuwei/cache

**Branch**: `leone/cache-paths` | **Spec**: `specs/cache-paths/spec.md`

## Summary

One helper, `ws._cached`, checks the name and the links; `cache_get`, `cache_put` and
`cache_prune` use it, and so do `ws.clone` and `hook._confirm`, the two direct users of the cache
path. guards.py is untouched.

## Technical Context

Python 3.11 stdlib, `pathlib` only. Tests in `tests/test_ledger.py` and `tests/test_hook.py`. A
normalisation probe (`specs/cache-paths/probe.py`, output in `probe.txt`) runs one name per path
class (`//`, `%xx`, `/./`, `/../`) and a linked entry, cache folder and `.wuwei`, against get, put
and prune, plus a linked clone entry and folder through `ws.record`, on main and on the branch.
The route differential (`route_diff.py`, output in `route_diff.txt`) runs every corpus route
through a planner PreToolUse with a pending answer entry, plain and with a linked cache folder. Runtime budget 3,600 lines; main is at 3,448, the branch at
3,463.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no door decision moves. hook.py changes in `_confirm`; the route differential
  on corpus sha256 de377966 moves 0 decisions and 0 door reasons in 576 cases.
- V. Test first: round 1's tests ran red on main (11 failed, 4 passed); round 2's ran red at
  b0956601 (4 failed, 6 passed) before the change.
