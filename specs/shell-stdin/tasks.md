# Tasks: a shell fed its commands on stdin and a named-fd redirect meet the doors

## Phase 1: Real execution and tests first

- [x] T001 Run the lead's generated probe at main a5edd81: 912 generated, 803 ran the push, 586 holes
- [x] T002 [US1] Named-fd pushes in six positions meet the push door (tests/test_guards.py)
- [x] T003 [US1] Shells fed a door command by here-string, pipe, `|&`, `0<<<`, `< file` and `-o pipefail -c` are refused (tests/test_guards.py)
- [x] T004 [US3] No-door shapes pass, the five acceptance ones plus `pytest -q 2>&1 | tail` and `cat file | python3 script.py` (tests/test_guards.py)
- [x] T005 Infra ask and leak check see the program after a named fd (tests/test_guards.py)
- [x] T006 [US1] Real bash with a stub `git` on PATH logs the push for the six acceptance shapes (tests/test_guards.py)
- [x] T007 Run the new tests on main: 18 red

## Phase 2: Implementation

- [x] T008 `segments` drops `{name}` before a redirect
- [x] T009 `_unwrap` leaves `UNREAD` beside a shell segment without a `-c` body
- [x] T010 Run the tests green: 34 passed

## Phase 3: Integration

- [x] T011 design.md names the new unreadable shape and `{fd}>x`
- [x] T012 Re-vendor `.claude/wuwei/cli/wuwei/guards.py`
- [x] T013 Merge origin/main 86135fa (free-lines-4, #1112); runtime 2,976
- [x] T014 Generated probes at head: 0 holes
- [x] T015 Route corpus dumped at main and head with the corpus sha256
- [x] T016 Full suite green
