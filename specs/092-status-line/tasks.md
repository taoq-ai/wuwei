# Tasks: Signal classification and status line

## User Story 1: Classify attention

- [X] T001 [US1] Add failing page, nudge, silent and unreadable event tests in tests/test_signal_status.py
- [X] T002 [US1] Implement pure classifier and signal command in cli/wuwei/signal.py and cli/wuwei/commands/signal.py

## User Story 2: Glance at the day

- [X] T003 [US2] Add failing line, JSON, unreadable state and read-only tests in tests/test_signal_status.py
- [X] T004 [US2] Implement status command in cli/wuwei/commands/status.py
- [X] T005 [US2] Add failing status CPU budget test in tests/test_hooks.py
- [X] T006 [US2] Verify status CPU budget and optimize cli/wuwei/commands/status.py if needed

## User Story 3: Install guidance

- [X] T007 [US3] Add failing init snippet test in tests/test_signal_status.py
- [X] T008 [US3] Print snippet in cli/wuwei/commands/init.py

## Verification

- [X] T009 Run full requested pytest suite and inspect hygiene
- [X] T010 Add emitted-kind coverage, state and resolution regressions, and realistic 10k-event latency fixture
- [X] T011 Reconcile current attention, skip decoding known silent events, and fail closed on recursive input
- [X] T012 Quote setup command and verify owner settings remain untouched
- [X] T013 Reject seat-written resolution events as page clearers, scan all emitted kinds, and share silent kinds between signal and status
