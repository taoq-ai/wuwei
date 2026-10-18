# Implementation plan: wide-specs

**Spec**: `specs/wide-specs/spec.md`
**Item**: wide-specs, tier full, goal G-2

## Technical context

- `cli/wuwei/evidence.py` `needed(root, tier, files)` picks the gates from the diff. `code` already
  leaves out prose and spec paths; the wide clause used `lines(files)`, every file.
- `CONTRACT` is used only in `needed`. `gate_gaps` calls `needed` on the delta after a pass, and
  `guards.create_door` reaches `needed` through `gates_for`, so the create and ready doors follow.
- Runtime at the base: 2,976 lines (`cat cli/wuwei/*.py | wc -l`); budget 3 for this item.

## Design

1. `wide = [f for f in files if f['path'] in code or f['path'].startswith(('specs/', 'openspec/'))]`:
   the files the wide trigger and the contract check read. One filter, so no file counts twice.
2. The arch clause reads `any(CONTRACT.search(f['path']) for f in wide)` and `lines(wide) > WIDE`.
3. `CONTRACT` gains `|^(specs|openspec)/(.+/)?contracts/`.
4. Rule text in charters/_common.md, docs/design.md line 77 and docs/site/concepts/evidence.md;
   `tests/test_charters.py` reads it; `bin/wuwei agents build`; `setup.vendor('.')`.

## Verification

- New tests red on main (in a `git archive` copy), green at the head; full suite green.
- `bin/wuwei agents build` reports the agents match and git status shows no change after it.
- Runtime 2,978 lines.

## Constitution check

Stdlib only, test first, no new config key, no new door, runtime within the cap and the item's
budget.
