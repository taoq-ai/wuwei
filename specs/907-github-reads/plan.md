# Implementation Plan: one evidence read per PR action, a listing read per repository, briefs without a standing doctor run

**Branch**: `907-github-reads` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

Also covers [../900-listing-unmeasured/spec.md](../900-listing-unmeasured/spec.md): both change
how WUWEI reads GitHub and share `derive.refresh`.

## Summary

Pass the evidence `evaluate` read to the action. Give `prs.json` a `repos` map (`at`, `failed`)
so each repository is due on its own, and a failed one waits for its retry instead of making the
batch stale. Offers turn a failed repository's PR rows into `unmeasured`. The brief's Doctor
line becomes conditional and counterparts come from the listing. One common charter rule.

## Technical Context

Stdlib Python 3.11+. One optional key in `prs.json`; a file without it reads as before (one time
for every repository).

## Constitution Check

- III: one listing writer (`refresh`), one staleness rule (`stale`), shared by next and offers.
- IV: tests first, each seen red.
- V: shortest diff; no cache module, no retry loop, no GraphQL second path.

## Files to edit

- `cli/wuwei/pr_actions.py`: `evaluate(root, refs, read=None)`; `launch`, `act`, `_rebase` use it.
- `cli/wuwei/derive.py`: `listing` returns `repos`; `stale` returns due repositories; `refresh(root,
  config, names)`; `offers` writes `unmeasured` rows and uses the repository's read time for G1.
- `cli/wuwei/commands/next.py`: refresh only the due repositories; unmeasured rows wait and print.
- `cli/wuwei/brief.py`: conditional `DOCTOR`; counterparts from `derive.listing`.
- `charters/_common.md` (1.10.6) and `agents/*.md` via `bin/wuwei agents build`.
- Tests: `test_pr_actions.py`, `test_derive.py`, `test_next.py`, `test_brief.py`, `test_charters.py`.
