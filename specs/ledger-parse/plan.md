# Plan: well-formed ledger rows only (ledger-parse)

## Approach

- `cli/wuwei/ws.py`: `_parse` keeps a parsed line only when it is a dict whose `ts` and `kind`,
  where present, are strings and whose `data`, where present, is a dict (+3 lines). `record` takes
  `prev` from the last kept row with a string `hash`, else GENESIS (same line count). `traces`
  returns a comprehension over `_parse` (-7 lines). `verify` is unchanged.
- `cli/wuwei/setup.py`: doctor's hooks scan drops its own `isinstance(row, dict)` filter.
- Tests: `tests/test_ledger.py` for scenarios 1 to 3 and traces; `tests/test_setup.py` for doctor
  on the malformed-field rows; `tests/test_hook.py` for a deny that holds when the last ledger
  line is `[1]` (the refusal the fail-open used to lose). The size test holds scenario 4.
- Runtime goes from 3,000 to 2,996 lines.

## Constitution check

Stdlib only, no new module, runtime under 3,000 lines, test first. guards.py and hook.py are not
touched (item 1068 changes them).
