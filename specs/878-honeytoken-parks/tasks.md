# Tasks: a seat's honeytoken read parks its item and holds the close

- [X] T001 [US1, US2] Test in `tests/test_canary.py`: a bound seat and a seat bound by this
  call (transcript reference) each read the honeytoken; the item parks with reason
  `security.honeytoken read`, one critical `scanner.finding` names the session, and
  `closing.scanner_hold` returns 1. A non-seat session parks nothing and `scanner_hold`
  returns 0. Run: red.
- [X] T002 [US1] Implement FR-001 to FR-003 in `cli/wuwei/scanner.py` and
  `cli/wuwei/guards/traces.py`; T001 green.
- [X] T003 Run every test file that imports `scanner`, `security`, `closing` or
  `guards.traces` under 3.12, and the security, scanner, closing and hooks files under 3.11.
