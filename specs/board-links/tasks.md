# Tasks: the board links every item a PR names, closes a just-merged item, and shows uncounted verdicts

## Phase 1: Tests first

- [x] T001 [US1] A PR naming A and B links both and closes both once merged (tests/test_watch.py)
- [x] T002 [US2] An item whose PR just merged closes despite a 2-minute-old merged cache (tests/test_watch.py)
- [x] T003 [US3] An approved item with no PR names its uncounted verdict (tests/test_watch.py)
- [x] T004 Run the new tests red

## Phase 2: Implementation

- [x] T005 [US1] Add `evidence.items_named(body)` and match PRs through `board.names`
- [x] T006 [US2] Read the merged list fresh when an open item has no open PR
- [x] T007 [US3] Append `evidence.uncounted` to no-PR rows
- [x] T008 Re-vendor `.claude/` with `setup.vendor('.')`
- [x] T010 [US1] A footer-less PR links by branch name and by the plan's prs list, and closes on merge (tests/test_watch.py; red against the fallback reversed to `or set()`)
- [x] T009 [US4] Run the new tests green, the full suite, and confirm the runtime is 3,000 lines or fewer
