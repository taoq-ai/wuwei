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
- [X] T004 [F1] Test: `scanner._park` raises `TimeoutError`; the recorder returns 0, `scanner_hold`
  returns 1, the warning names the honeytoken and not a missing span. Run: red. Implement: on
  an exception `scanner.honeytoken` appends the critical finding and re-raises; `traces.check`
  warns as a `traces.gap` with its own text.
- [X] T005 [review residual] Test: a seat (and a subagent seat) sending the honeytoken value in
  `gh issue create` is refused at PreToolUse and parks; another session only pages. Run: red.
  Implement: `hook.enforce` calls `scanner.honeytoken(traces.seat_session(payload))` when a
  refusal names `security.honeytoken`.
- [X] T006 [D1] Test: with `state.lock` held, `hook.enforce` on a refused honeytoken send returns
  the refusal within 5 s (was 60 s). Run: red. Implement: `state._write_state` takes the
  `timeout` `append_event` already has; `scanner.honeytoken` and `_park` pass it through, and
  `hook.enforce` parks with `timeout=1`.
