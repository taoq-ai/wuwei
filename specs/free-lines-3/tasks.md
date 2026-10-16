# Tasks: one plugin path and version read in ws, one git helper in guards, and two dead or one-caller definitions go

## Phase 1: Tests first

- [x] T001 Verify the readers (`grep -rn "CONFIDENCE\|_confidence\|PLUGIN\|PR_STANDARD\|plugin.json" cli tests`): CONFIDENCE has none, _confidence one, PLUGIN read in tests only as hook.PLUGIN
- [x] T002 [US1] One module holds the plugin path and version; no CONFIDENCE or _confidence (tests/test_setup.py)
- [x] T003 [US2] origin and current_branch on a real repository and a non-directory cwd (tests/test_guards.py)
- [x] T004 [US2] origin and current_branch answer '' on OSError and TimeoutExpired (tests/test_guards.py)
- [x] T005 [US3] seat.stopped confidence is high or null (tests/test_hook.py)
- [x] T006 [US4] the first PR-create note is the charter with the plugin version (tests/test_guards.py)
- [x] T007 Session-start test reads ws.PLUGIN (tests/test_hook.py)
- [x] T008 Run the new tests on main: T002 and T007 red, T003 to T006 green (behaviour pins)

## Phase 2: Implementation

- [x] T009 [US1] Drop verdict.CONFIDENCE
- [x] T010 [US1] Add ws.PLUGIN and ws.version(); use them in __main__, hook, setup and guards; drop __main__'s pathlib import
- [x] T011 [US2] Add guards._git and rewrite origin and current_branch through it
- [x] T012 [US3] Inline hook._confidence in subagent_stop
- [x] T013 [US1] Re-vendor .claude/ with setup.vendor('.') and run bin/wuwei agents build
- [x] T014 Run the full suite green; count runtime lines (2,986); compare wuwei --version and --help with main
- [x] T015 Mutation probe in a scratch copy: confidence without lower, _git returning None, origin reading another remote, all killed
