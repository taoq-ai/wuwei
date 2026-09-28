# Tasks: Read-only cockpit lanes

## Phase 1: Read model

- [X] T001 Test pending D- and C- records, people, PR references, signals, briefing and unmeasured inputs in `tests/test_dashboard.py`.
- [X] T002 Implement the read-only cockpit snapshot in `cli/wuwei/commands/dashboard.py`.

## Phase 2: HTTP boundary

- [X] T003 Test cockpit GET, exact Host, POST refusal, and no writes in `tests/test_dashboard.py`.
- [X] T004 Serve the snapshot and refuse POST in `cli/wuwei/commands/dashboard.py`.

## Phase 3: View

- [X] T005 Extend the Node render test for every lane, missing measurements, and hostile text in `tests/test_dashboard.py`.
- [X] T006 Render Decisions, People, PRs, signals, and briefing in `templates/dashboard.html`.

## Phase 4: Verification

- [X] T007 Run the full pytest suite and scan changed files for prohibited characters and local paths.

## Phase 5: Review fixes

- [X] T008 Test and share clarification field parsing between lint and cockpit snapshot.
- [X] T009 Test and isolate cockpit fetch failures so the Work board still renders.
