# Plan: hooks-live

1. Tests first. In `tests/test_setup.py`, replace the #1065 since-init tests with one test: hook
   rows in the ledger warn; `pre_tool` 5 seconds ago gives `ok` with `fired 5s ago`; 121 seconds
   later it warns. Point the cloud doctor test at `pre_tool` instead of `session_start`. In
   `tests/test_hook.py`, add a trace role test and a `hook-seen` stamp test.
2. `cli/wuwei/hook.py`: one line at the top of `pre_tool` writes the stamp; the trace row gains
   `role`.
3. `cli/wuwei/setup.py`: drop `HOOK_ROWS` and the ledger scan; the hooks row reads
   `ws.cache_get(root, 'hook-seen', 120)`.
4. Re-vendor with `setup.vendor('.')`, run the suite, check the runtime line count.

Rollback: revert the commit; the cache key is per machine and unread by anything else.
