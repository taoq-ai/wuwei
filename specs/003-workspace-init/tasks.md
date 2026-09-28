# Tasks: Workspace

## Setup

- [X] T001 Read repository rules, CLI and spec; record design in specs/003-workspace-init/spec.md and plan.md.

## US1: Initialize (MVP)

Independent check: subprocess init creates the skeleton and refuses any existing destination.

- [X] T002 [US1] Write and run failing init layout, explicit path, no-overwrite and I/O tests in tests/test_workspace.py.
- [X] T003 [US1] Implement cli/wuwei/commands/init.py and templates/workspace/.

## US2: Configuration

Independent check: manual config files validate or report a precise finding.

- [X] T004 [US2] Write and run failing defaults, all-fields, nested typo/line, invalid value, syntax and I/O tests in tests/test_workspace.py.
- [X] T005 [US2] Implement schema/loading in cli/wuwei/workspace.py and cli/wuwei/commands/config.py.

## US3: Workspace and clock

Independent check: nested and overridden workspace discovery and deterministic dates.

- [X] T006 [US3] Write and run failing ancestor, override, missing workspace and clock tests in tests/test_workspace.py.
- [X] T007 [US3] Complete find_workspace, now and day_dir in cli/wuwei/workspace.py.

## Verification

- [X] T008 Run full suite, review diff and scan authored files for prohibited characters; record results in specs/003-workspace-init/tasks.md.
- [X] T009 Reproduce and fix review F1/F2/F3 with failing tests for dotted/inline key locations, unknown locations, interrupted copies and timezone-aware overrides.
- [X] T010 Address F5/F6: test placeholder exclusion, skip .gitkeep during staged initialization, and declare existing constraints in the schema.

## Dependencies and Execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008.
US1 is the skeleton MVP; its config-check acceptance completes with US2 and US3.
No parallel execution is needed: stories share tests and workspace.py. Independent template
and test reviews could run in parallel after implementation. Extension hooks are skipped
per the issue instructions.

## Verification Results

- US1 red: 6 failures for missing init command; green: 6 passed.
- US2 red: 30 failures for missing config command/loader; green: 36 passed.
- US3 red: 10 failures for missing discovery/clock helpers; green: 46 passed.
- Full suite using the issue-specified interpreter: 82 passed in 3.13s.
- Initial review was superseded by adversarial findings F1-F6.
- All 16 authored files contain ASCII only; no prohibited characters. Whitespace check passed.
- Unknown-key locations use the accepted text-scan heuristic. No extension hooks executed.
- Review regression red: 9 failed, 43 passed. All reported blocking scenarios reproduced.
- Review regression green, full suite using the issue-specified interpreter: 88 passed in 3.46s.
- F1/F2/F3/F5/F6 addressed. F4 deferred: new required repo fields and uniqueness rules change the existing configuration contract beyond the blocking fixes.
- Initialization stages in the destination parent, renames only after copying, and cleans staging on exceptions including KeyboardInterrupt.
