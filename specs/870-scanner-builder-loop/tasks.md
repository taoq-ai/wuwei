# Tasks: the builder loop is not a parking scanner chain

- [X] T001 [US1, US2] Test: in `tests/test_traces_seats_only.py`, a seat with chains
  `Bash -> Write`, `Bash -> Edit`, `Edit -> Bash -> Write` is not parked and writes no
  `scanner.finding`; a seat with `Read -> WebFetch` parks with `reason` on the event. Point
  `test_seat_wins_over_registration` at an outward chain. Run: red for the builder loop.
- [X] T002 [US1, US2] Implement FR-001 to FR-003 in `cli/wuwei/scanner.py`; T001 green; update
  the payload assertion in `tests/test_ziran.py`.
- [X] T003 [US3] Test: in `tests/test_signal_status.py`, three `Read -> WebFetch` and two
  `Bash -> WebFetch` findings give two scanner rows with counts 3 and 2, each reason naming
  the chain. Run: red (five rows).
- [X] T004 [US3] Implement FR-004 in `cli/wuwei/commands/status.py`; T003 green.
- [X] T005 Run every test file that imports `scanner` or `status` under 3.12 and 3.11.
- [X] T006 [F1] Test: Read, Bash, Glob or Grep naming a private file, then curl, then a write
  (`Bash -> Write`), raw and hashed session ids, still parks; the builder loop with
  worktree-only paths (plus another session) does not. Run: red (8 failed, 0 owed).
- [X] T007 [F1] `scanner._private_read` reads the session's spans; T006 green. (The shared
  `redact.private_file` of fix round 1 was reverted by T010.)
- [X] T008 [F2] Record the bare `Read -> Bash` egress gap under Deferred.
- [X] T009 [D1] Test: the builder loop also greps for `secret|credential`, runs `git diff -G`,
  reads `.env.example`, edits `tests/test_env_credentials.py` and Greps pattern `secret`, and
  does not park; the attack forms (`.aws/credentials`, `.ssh`, `.netrc`, `.npmrc`, `.env`,
  `gh/hosts.yml`, a python one-liner) park. Run: red.
- [X] T010 [D1, D2, D3] `scanner._credential_path` with the exact locations and the ponytail
  ceiling; `redact.py` back to main; `trace_sweep` passes its `traces.jsonl` path into
  `_trace_response`; T009 green.
