# Tasks: State writer

## Setup and foundation

- [X] T001 Read design, constitution and existing cli/wuwei/workspace.py; create specs/004-state-writer/spec.md and plan.md.

## US1: Safe persistence (P1)

- [X] T002 [US1] Add failing get/set, defaults, schema, failure, atomic replacement and N-process concurrency tests in tests/test_state.py.
- [X] T003 [US1] Implement validated read_state/write_state, locked read-modify-write, atomic replacement and state-write events in cli/wuwei/state.py; register get/set in cli/wuwei/commands/state.py.

## US2: Lifecycle (P1)

- [X] T004 [US2] Add failing legal/illegal edges, terminal, parked/escalated resume and set-bypass tests in tests/test_state.py.
- [X] T005 [US2] Implement the single phase dictionary, phase-change enforcement and transition command in cli/wuwei/state.py and cli/wuwei/commands/state.py.

## US3: Explicit events (P2)

- [X] T006 [US3] Add failing explicit event, shared timestamp, payload and short-write tests in tests/test_state.py.
- [X] T007 [US3] Finish append_event contract in cli/wuwei/state.py and expose cli/wuwei/commands/event.py.

## Polish

- [X] T008 Run full suite, review correctness/security/simplicity and check all authored files for banned characters; record results in specs/004-state-writer/tasks.md.

## Dependencies and implementation strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
US1 is the persistence MVP; US2 and US3 complete the issue. No parallel implementation
because all stories share cli/wuwei/state.py. Independent full-suite test modules can
be run concurrently, but this task uses the required single pytest invocation.

## Verification results

- US1 red: 26 tests failed because the state module/command did not exist; green: 26 passed.
- US2 red: 31 lifecycle tests failed for missing transition enforcement; green: 57 passed.
- US3 red: 8 tests failed for missing event CLI, unchecked short writes, unchecked
  imported event payloads and midnight rollover data loss; green: 66 passed.
- Full suite with the requested interpreter: 154 passed in 4.65s.
- Review: all writes reside in cli/wuwei/state.py; no additional locator or clock;
  sidecar lock spans read-modify-write and append; errors propagate through existing
  fail-closed CLI handling. Phase mutations through set and write_state are checked.
- Files checked for whitespace errors, em dashes and emoji characters.
- No commits, pushes, external tools or network calls.

## Adversarial review fixes

- [X] T009 [US2] Correct the transition matrix to the design graph, remove done as a phase, and preserve pause/resume constraints (F2).
- [X] T010 [US2] Reject item removal and require later new items to start planned; reproduce the delete/recreate bypass before fixing (F1).
- [X] T011 [US3] Reserve state.* kinds in the event CLI and test exit 1 without append (F3).
- [X] T012 [US1] Flush/fsync the temporary state before replace and fsync the directory afterward; test unsupported directory fsync (F4).
- [X] T013 [US3] Lock explicit event timestamps and appends; test both writer and explicit paths hold the same flock (F6).
- [X] T014 Remove dict-based writes, validate event payload once, and trim redundant tests while retaining short-write, transition and resume coverage (F7).
- [X] T015 Document the state/event crash gap and test the same-phase retry diagnostic (F5).
- [X] T016 Run the requested full suite and inspect final changes.

Review-fix red checks: F2 had 4 matrix failures; F1 had 2 bypass failures;
F3 had 1 forged-event failure; F4 had 2 sync-order failures; F6 had 1
explicit-event lock failure; F5 had 1 retry-diagnostic failure.
Focused suite after fixes and test simplification: 63 passed.

Requested full-suite verification after review fixes: 151 passed in 6.33s.
Final inspection: no banned characters or code trailing whitespace; changes remain uncommitted.
