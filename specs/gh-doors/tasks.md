# Tasks: gh api graphql queries WUWEI cannot read, repositories/<id> writes, and merge flags meet the doors

## Phase 1: Real execution and tests first

- [x] T001 Run each gh api shape through gh 2.89.0 with `http_unix_socket` at a logging server; record the requests
- [x] T002 Compare the merge flag readings with a pflag v1.0.6 mirror (18 argv)
- [x] T003 [US3] `--auto` read as pflag reads it, with a PR whose only gap is CI running (tests/test_guards.py)
- [x] T004 [US3] `--admin` in every true spelling refused; `--admin=false` and `-t --admin` off (tests/test_guards.py)
- [x] T005 [US1] An `--input` file's mutation refused by name, escaped and batched forms too (tests/test_guards.py)
- [x] T006 [US1] Unreadable queries refused; readable ones with no door mutation pass (tests/test_guards.py)
- [x] T007 [US2] `repositories/<id>` writes refused naming `repos/<owner>/<repo>`; reads pass (tests/test_guards.py)
- [x] T008 [US4] 11 routes.json rows naming their source
- [x] T009 Run the new tests on 23625f3: 37 red

## Phase 2: Implementation

- [x] T010 Merge reads `--admin` and `--auto` through `_flags`
- [x] T011 `_api` reads the `--input` file's query and answers `unread`; `_read` skips `-`
- [x] T012 `gh_command` refuses unreadable graphql and `repositories/` writes; the segments clause goes
- [x] T013 Run the tests green

## Phase 3: Integration

- [x] T014 Docs: design.md section on refusals and docs/site/concepts/doors.md
- [x] T015 Re-vendor `.claude/` with `setup.vendor`
- [x] T016 Route corpus probe on main and head with the corpus sha256
- [x] T017 Full suite green; runtime at 3,000 lines
- [x] T018 Merge origin/main before the push
