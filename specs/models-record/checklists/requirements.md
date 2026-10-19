# Requirements checklist: models-record

- [x] Every acceptance scenario of the item maps to a test in tests/test_models.py
- [x] `agents.py` defines no `MODELS`; `wuwei agents build` leaves git status clean
- [x] `TABLE` is tested against the rows parsed from planner.md
- [x] The hook never returns a permission decision or `updatedInput` (route_diff.py: 0 at the head)
- [x] The Haiku floor is not covered by a reason line or a `models` row; only the owner's `exception:` breaks it (code text, planner.md rule 4, models.md)
- [x] Unreadable model or effort is recorded as `unrecorded` or `unmeasured`, never guessed
- [x] Codex launches are recorded as unmeasured and get no note; Codex role files unchanged
- [x] Every "five keys" statement says six
- [x] Route corpus on main and head with its sha256; each moved case listed
- [x] .claude/ re-vendored; agents/ rebuilt
- [x] Rollback line in the spec
- [x] No emojis, no em dashes
