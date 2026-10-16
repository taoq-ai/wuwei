# Tasks: an error inside a door refuses the call

## Phase 1: Tests first

- [x] T001 [US1] The merge door with the template cache path as a directory denies, names IsADirectoryError, records hook.error (tests/test_hook.py)
- [x] T002 [US1] An injected error on each door kind denies and names the error (tests/test_hook.py)
- [x] T003 [US1] The deny holds when hook.error cannot be recorded (tests/test_hook.py)
- [x] T004 [US2] A deny or ask reaches the harness when ws.record raises OSError or ValueError (tests/test_hook.py)
- [x] T005 [US3] An error on ls, Read, a read-only MCP tool or an Agent launch fails open and records hook.error (tests/test_hook.py)
- [x] T006 [US3] An unreadable tool_input fails open without crashing the hook (tests/test_hook.py)
- [x] T007 Run the new tests red

## Phase 2: Implementation

- [x] T008 Keep the decision when its record fails in `pre_tool` (cli/wuwei/hook.py)
- [x] T009 `door` and the deny in `handle` (cli/wuwei/hook.py)
- [x] T010 One transcript reader for the report text and the tokens (cli/wuwei/hook.py)
- [x] T011 Run the full suite green, runtime at 3,000 or fewer

## Phase 3: Docs and checks

- [x] T012 docs/design.md names the door-error rule
- [x] T013 Mutants of each new condition, run in a scratch copy, each fail a test
- [x] T014 [US3] A PostToolUse error on a Write fails open (kills the mutant that drops the event check) (tests/test_hook.py)
- [x] T015 Merge origin/main and re-vendor .claude/ with setup.vendor('.')
