# Tasks: semver-policy

## Phase 1: Evidence first

- [x] T001 Read the cited lines at 5fe8347: `sentinel-arch.md:28-32` (rule 7, 66 words), `builder.md:40-42`, `_common.md:35`, `evidence.md:66`, `design.md:116`, `reference.md:70`
- [x] T002 Read the ESLint README "Semantic Versioning Policy" section to check the citation
- [x] T003 Write `test_a_breaking_change_is_a_semver_major_of_the_declared_public_api` and run it red: 1 failed, 1925 passed, 2 skipped

## Phase 2: Docs and charters

- [x] T004 [US2] `evidence.md` Breaking changes: public API, classification, citations, history sentence (FR-001)
- [x] T005 [US1] `sentinel-arch.md` rule 7 in 65 words (FR-002)
- [x] T006 `builder.md` rule 6 (FR-003)
- [x] T007 [US2] `_common.md`, `design.md`, `reference.md`, `decisions.md` (FR-004)

## Phase 3: Build and checks

- [x] T008 [US4] `bin/wuwei agents build`, `setup.vendor('.')`, `wc -w agents/*.md` at or under 2,250 (FR-005)
- [x] T009 Full suite green: 1926 passed, 2 skipped
- [x] T010 No emojis and no em dashes in the diff
- [x] T011 [US3] PR body holds `Release-As: 4.1.0` alone on a line (FR-006)
