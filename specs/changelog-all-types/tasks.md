# Tasks: changelog-all-types

## Phase 1: Tests first

- [x] T001 [US1] `test_every_commit_type_on_main_has_a_visible_changelog_section` in tests/test_setup.py
- [x] T002 Run it on the old config: 1 failed (no `changelog-sections` key)

## Phase 2: Implementation

- [x] T003 [US1] `changelog-sections` with the eleven types in release-please-config.json
- [x] T004 Full suite green

## Phase 3: After merge

- [x] T005 [US2] Read the release PR body for #1123, #1124 and this change once the Release workflow has run on the merge commit
