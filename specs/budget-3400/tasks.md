# Tasks: the runtime budget is 3,400 lines and config holds six keys

## Phase 1: Test first

- [x] T001 Run the size test on a scratch copy of main padded to 3,100 lines: it fails (red)
- [x] T002 Change the assertion and message to 3400 (tests/test_setup.py)

## Phase 2: Documents

- [x] T003 Constitution VI: 3,400 lines, six keys, the more-than-10-lines rule; version 3.2.0
- [x] T004 AGENTS.md and CONTRIBUTING.md: 3,400 lines
- [x] T005 design.md principle 8 and section 11: six keys with `models`, 3,400 lines
- [x] T006 philosophy.md: 3,400 lines and six keys
- [x] T006a SECURITY.md:135: 3,400 lines, the last budget statement a repo-wide grep finds

## Phase 3: Checks

- [x] T007 The padded copy of the head passes at 3,100 and fails at 3,401 naming 3400
- [x] T008 The grep for "3,000" in the five documents finds no budget line
- [x] T009 Full suite green
