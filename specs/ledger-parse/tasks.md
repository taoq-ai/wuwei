# Tasks: well-formed ledger rows only (ledger-parse)

- [x] T001 Write the failing tests: record past `[1]`, `5`, `null`, `{"a": 1}`; ledger, rows and verify on malformed fields; traces on non-rows; doctor on `{"kind": [1]}`; a PreToolUse deny over a `[1]` last line
- [x] T002 Run them red (record TypeError at ws.py:145, ledger sort TypeError, traces AttributeError, doctor unhashable list at setup.py:152, hook deny lost to fail-open)
- [x] T003 Filter malformed rows in `_parse`; chain `record` to the last row with a hash
- [x] T004 `traces` reuses `_parse`; doctor drops its own isinstance filter
- [x] T005 Run the full suite green, runtime at 2,996 lines
- [x] T006 Fix round 1: cover the string-hash guard in record with `{"hash": null}` and `{"hash": 5}` last lines (red with the guard reversed to `'hash' in r`), and a deny over `[1]` for an unclassed AskUserQuestion
