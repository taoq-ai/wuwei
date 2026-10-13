# Tasks: Narrow Vercel host permissions

- [x] T001 Reproduce old host denials and missing upgrade migration in `tests/test_edges.py`; run focused tests red.
- [x] T002 Replace broad `PERMISSIONS_DENY` rules in `cli/wuwei/guards/edges.py` with the exact narrow set for both aliases.
- [x] T003 Migrate legacy settings through `cli/wuwei/commands/init.py`, including fresh init, dry-run and idempotence.
- [x] T004 Run #947 guard tests and all tests importing changed modules with explicit pytest files.
- [x] T005 Review the diff for correctness, security and unnecessary complexity; record test evidence.
