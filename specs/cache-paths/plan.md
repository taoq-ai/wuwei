# Implementation Plan: a cache entry or name never reads, writes or deletes outside .wuwei/cache

**Branch**: `leone/cache-paths` | **Spec**: `specs/cache-paths/spec.md`

## Summary

One helper, `ws._cached`, checks the name and the links; `cache_get`, `cache_put` and
`cache_prune` use it. No caller changes; hook.py and guards.py are untouched.

## Technical Context

Python 3.11 stdlib, `pathlib` only. Tests in `tests/test_ledger.py` and `tests/test_hook.py`. A
normalisation probe (`specs/cache-paths/probe.py`, output in `probe.txt`) runs one name per path
class (`//`, `%xx`, `/./`, `/../`) and a linked entry, cache folder and `.wuwei`, against get, put
and prune, on main and on the branch. Runtime budget 3,600 lines; main is at 3,448, the branch at
3,460.

## Constitution Check

- I. Stdlib only: yes.
- III. An auditor: no door changes; guards.py and hook.py are unchanged, so the route corpus
  differential does not apply.
- V. Test first: the new tests ran red on main (11 failed, 4 passed) before the change.
