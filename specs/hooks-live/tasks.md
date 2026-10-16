# Tasks: hooks-live

- [x] T001 Write the failing doctor test in tests/test_setup.py (ledger rows warn, 5 s old stamp ok with its age, 121 s warn) and point the cloud doctor test at pre_tool
- [x] T002 Write the failing trace role and hook-seen tests in tests/test_hook.py
- [x] T003 Run them red (4 failed: two AssertionError, KeyError 'role', TypeError on a missing stamp)
- [x] T004 Stamp hook-seen in hook.pre_tool and add role to the PostToolUse trace row
- [x] T005 Replace the ledger scan in setup.doctor with the hook-seen read
- [x] T006 Re-vendor, run the full suite green, runtime at 3,000 lines or fewer
