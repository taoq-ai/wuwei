# Tasks: the vendored plugin in .claude/ matches the tree it was copied from

## Phase 1: Tests first

- [x] T001 [US1] Drift helper and the real-repository drift test (tests/test_setup.py)
- [x] T002 [US1] A mutated fresh copy names the changed, missing and extra paths only (tests/test_setup.py)
- [x] T003 [US2] release-please bumps both plugin.json files and their versions match (tests/test_setup.py)
- [x] T004 Run the new tests red (drift names plugin.json, evidence.py, gh.py, setup.py; config lacks the copy)

## Phase 2: Implementation

- [x] T005 [US2] Add the copy's plugin.json to extra-files (release-please-config.json)
- [x] T006 [US1] Re-vendor .claude/ with setup.vendor() at the head
- [x] T007 Run the full suite green and `bin/wuwei agents check`

## Phase 3: Docs

- [x] T008 ADR for cutting 1.2.1 before 1068 (docs/adr/0001-cut-1.2.1-before-1068.md)
