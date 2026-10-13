# Tasks: #952 housekeeping

## Setup and foundation
- [x] T001 Specify, clarify by assumptions and plan specs/952-housekeeping.
- [x] T002 Write and run failing tests in tests/test_housekeeping.py for FR-001 through FR-007.

## US1: Owned leftovers
- [x] T003 Add process reading and verified TERM/grace/KILL to adapters/host/local.py and host port/fake.
- [x] T004 Add shared registration and housekeeping derivation/reaping to cli/wuwei/watch.py.

## US2: Owner findings and seat recovery
- [x] T005 Include orphans, terminal worktrees and inactive seats in cli/wuwei/watch.py.

## US3: Lifecycle integration
- [x] T006 Integrate cli/wuwei/commands/next.py, doctor.py, close.py and guards/lifecycle.py.
- [x] T007 Report reaping evidence through cli/wuwei/report.py and document entry points.

## Validation
- [x] T008 Run all tests importing changed modules with explicit test-file arguments.
- [x] T009 Review correctness, security and simplicity; save evidence and mark tasks complete.

Dependencies: T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009.
Work is sequential because the shared findings contract connects all stories.

## Review follow-up
- [x] T010 Reproduce H1, M2 and L4; narrow wrapper and unwrap Bash guard commands.
- [x] T011 Reproduce H2/H3/M4/L1/L2; isolate cwd failures, exclude active worktrees/ancestors and use fast PID checks.
- [x] T012 Reproduce M1/M3/L3/L5/L6; simplify wait identity, failed cleanup and historical owner listings.
- [x] T013 Run explicit impacted files plus hooks and signal status; record diff reduction and exact results.

## Round 2 follow-up
- [x] T014 Specify, clarify assumptions, plan and analyze FR-008 through FR-012.
- [x] T015 Port the field reproduction and observe expected failing regressions.
- [x] T016 Fix H1/M1/L1-L5 at shared scan, wrapper and orientation boundaries.
- [x] T017 Run every impacted test file plus hooks and signal status; review diff and save evidence.

## Round 3 follow-up
- [x] T018 Specify, clarify assumptions, plan, analyze and check FR-013 through FR-015.
- [x] T019 Write and observe failing regressions for close inspection, scoped waits and housekeeping argv.
- [x] T020 Apply the three minimal fixes and verify focused regressions.
- [x] T021 Run explicit impacted files plus hooks, all close files and signal status; record results and review changes.

Dependencies: T018 -> T019 -> T020 -> T021.
