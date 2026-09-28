# Tasks: Generic role charters

## Foundation

- [X] T001 Read the design, constitution, source charters and existing workspace config; write spec.md and plan.md.

## US1 and US2: Generic, traceable charters

- [X] T002 [US1] [US2] Write failing `tests/test_charters.py` for file/version coverage, role policy, generic identifier lint and one-home section 5.3 rule table; run red.
- [X] T003 [US1] [US2] Write `_common.md` and `_common-authoring.md` with shared rules and CHANGELOG convention.
- [X] T004 [US1] [US2] Write nine ordered role charters, including amended engineering, discovery, decision and merge rules.
- [X] T005 [US1] [US2] Run focused tests and fix gaps.

## Verification

- [X] T006 Run the requested full pytest suite; scan authored files for banned characters and inspect the final diff.

## Adversarial review fixes

- [X] T007 Write and run failing charter tests for generic identifier lint, promote ownership, gate and merge safety, class sweep and spec wording.
- [X] T008 Correct shared and role charter procedures and remove duplicate rules.
- [X] T009 Correct spec and plan artifacts; rerun focused charter tests and the full requested suite.
- [X] T010 Remove the engagement list and its tests; harden generic lint and deduplicate charter rules with red-green tests.

## Dependencies

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009. Shared policy and role anchors require a single sequence.

## Verification results

- Red: 19 charter tests failed because `charters/` was absent.
- Focused green: 20 passed.
- Initial full suite: 172 passed in 6.91s with the requested interpreter.
- Post-review focused suite: 25 passed. Full suite: 177 passed in 5.04s with the requested interpreter.
- Fix-seat focused suite: 34 passed with the requested interpreter.
- Fix-seat full suite: 186 passed in 5.04s with the requested interpreter.
- All 15 authored files passed the emoji, em dash and trailing-space scan; `git diff --check` found no whitespace errors.
