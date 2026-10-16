# Tasks: the test-only replay helper leaves the runtime and two cache copies fold into evidence._cached

## Phase 1: Tests first

- [x] T001 Verify the callers (`grep -rn "items_named\|_list(\|_default(\|replay.replay" cli tests`): one runtime caller each, replay only from tests
- [x] T002 [US1] No runtime module defines replay(, _list( or items_named( (tests/test_replay.py)
- [x] T003 [US1] wuwei evidence --record DIR writes DIR/case.json (tests/test_replay.py)
- [x] T004 [US3] A GhError on the default-branch lookup refuses a push to main and caches nothing (tests/test_guards.py)
- [x] T005 [US3] A cached default branch trunk refuses its push with no gh call (tests/test_guards.py)
- [x] T006 Run the new tests on main: T002 red, T003 to T005 green (behaviour pins)

## Phase 2: Implementation

- [x] T007 [US2] Move replay.replay into tests/test_replay.py as replay_case; drop import datetime
- [x] T008 [US1] Fold board._list into evidence._cached with TTL
- [x] T009 [US4] Inline evidence.items_named in board.names
- [x] T010 [US3] Rewrite guards._default through evidence._cached
- [x] T011 [US1] Re-vendor .claude/ with setup.vendor('.')
- [x] T012 Run the full suite green and `bin/wuwei agents check`; count runtime lines (2,962)
- [x] T013 Mutation probe in a scratch copy: renamed cache, empty fallback, first-item-only all killed
