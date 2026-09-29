# Tasks: Live cockpit owner surfaces

## PR rows

- [X] T001 Add a failing test for two measured owned PR rows and a failed row in `tests/test_dashboard.py`.
- [X] T002 Map recorded PR action episodes in `cli/wuwei/commands/dashboard.py` without calling the producer.

## Briefing and pending work

- [X] T003 Add a failing test for the producer-recorded daily pack and pending CLI commands in `tests/test_dashboard.py`.
- [X] T004 Read the recorded pack path and expose pending commands in `cli/wuwei/commands/dashboard.py` and `templates/dashboard.html`.

## Status producers

- [X] T005 Add failing tests for reply due at 15:00, calendar meeting, unconfigured calendar, and adapter failure in `tests/test_signal_status.py`.
- [X] T006 Read obligations and configured calendar in `cli/wuwei/commands/status.py`, keeping adapter failures local to the meeting field.

## Verification

- [X] T007 Run the full pytest suite and scan changed files for em-dashes and emojis.
