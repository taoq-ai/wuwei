# Tasks: a review-driven commit status reads as review, not CI

## Phase 1: Tests first

- [x] T001 FakeGh answers `actions/runs?event=...`, `actions/runs/<id>` and returns `target_url` (tests/conftest.py)
- [x] T002 [US1] Pending review status gives `waiting on review: Review Gate` (tests/test_evidence.py)
- [x] T003 [US2] Failing review status gives `change request outstanding: Review Gate` (tests/test_evidence.py)
- [x] T004 [US3] Ordinary failing status stays `CI failing: lint` (tests/test_evidence.py)
- [x] T005 [US3] No commit status, no `/actions/` call (tests/test_evidence.py)
- [x] T006 [US3] Refused Actions read leaves the status CI (tests/test_evidence.py)
- [x] T007 The review path list is read once a day (tests/test_evidence.py)
- [x] T007a A blank, external or other-repository target_url stays CI with no Actions call (tests/test_evidence.py)
- [x] T008 The merge door refuses both review gaps with and without `--auto` (tests/test_guards.py)
- [x] T009 Run the new tests red

## Phase 2: Implementation

- [x] T010 `gh.pr` keeps `target_url`; add `gh.workflow_paths` (cli/wuwei/gh.py)
- [x] T011 Add `review_contexts`; teach `ci_gaps` the review gaps (cli/wuwei/evidence.py)
- [x] T012 Free lines in evidence.py and gh.py until the runtime is at 3,000
- [x] T013 Run the full suite green

## Phase 3: Docs and checks

- [x] T014 docs/design.md section 6 and docs/site/concepts/evidence.md
- [x] T015 Live read of ai-stacks #3300, #3291, #3274 from a copy of the tree

## Phase 4: Fix round 1 (arch FIX at 3fb3f40)

- [x] T016 A failing review status still names an approval at an older commit (tests/test_evidence.py, cli/wuwei/evidence.py)
- [x] T017 A repository without review workflows reads no run (tests/test_evidence.py)
- [x] T018 An oddly shaped Actions reply or a non-string target_url leaves the status CI (tests/test_evidence.py, cli/wuwei/evidence.py)
