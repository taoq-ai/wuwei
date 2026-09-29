# Tasks: Briefing pack

## Setup

- [X] T001 Create specs/096-briefing-pack/spec.md and specs/096-briefing-pack/plan.md from issue #96.

## US1: Pack and ports

- [X] T002 [US1] Add failing pack, due-window and no-audio tests in tests/test_brief_pack.py.
- [X] T003 [US1] Implement pack assembly and command in cli/wuwei/brief_pack.py and cli/wuwei/commands/brief.py.
- [X] T004 [US1] Add failing port and ICS fixture tests in tests/test_brief_pack.py and tests/fixtures/calendar/meeting.ics.
- [X] T005 [US1] Implement registry/config and adapters in cli/wuwei/registry.py, cli/wuwei/workspace.py and adapters/{tts,calendar,transcripts}/.

## US2: Drill and metric

- [X] T006 [US2] Add failing answer, streak, reserved-state and metric tests in tests/test_brief_pack.py.
- [X] T007 [US2] Implement answer recording and metric in cli/wuwei/brief_pack.py, cli/wuwei/state.py and cli/wuwei/metrics.py.

## Polish

- [X] T008 Update templates/workspace/config.toml and run the complete suite plus hygiene checks.

## Dependencies

T001 to T008 in order. Every implementation task follows its failing test task. US1 is independently testable by pack files and adapter results; US2 by feedback, state and metric assertions.
