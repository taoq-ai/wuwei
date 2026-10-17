# Tasks: merge-evidence

## Phase 1: Tests first

- [x] T001 Read the real `pull_request_target` Actions runs shape for taoq-ai/wuwei with one read-only REST call
- [x] T002 [US1] Approved breaking and exception rulings leave the owner review gap; an owner review ruling clears it (tests/test_evidence.py)
- [x] T003 [US2] A docs and specs diff with an empty rollup gets no CI not started gap; a code diff does (tests/test_evidence.py)
- [x] T004 [US3] An unreadable Actions host names itself and the error in the gap (tests/test_evidence.py)
- [x] T005 [US4] Only pull_request_target runs read as CI (tests/test_evidence.py)
- [x] T006 Run the new tests on 86135fa: 6 red (the code-diff case holds on main)

## Phase 2: Implementation

- [x] T007 `owner_approved` counts only rulings with no kind
- [x] T008 The CI not started read skips docs-only diffs, reads pull_request_target after an empty pull_request answer, and names an unreadable host
- [x] T009 Update the two cache tests for the second read and the new text (old contract)
- [x] T010 Run tests/test_evidence.py green

## Phase 3: Integration

- [x] T011 Name the change in docs/design.md and docs/site/concepts/evidence.md
- [x] T012 Re-vendor `.claude/` with `setup.vendor`
- [x] T013 Full suite green; runtime at 2,977 lines
- [x] T014 Compare `wuwei evidence` on main and head with a stubbed code host for each acceptance input

## Phase 4: Gate findings at fc27033

- [x] T015 [US2] requirements.txt, CMakeLists.txt, docs/exploit.py, src/docs/x.py, LICENSE.py, an empty list, charters, agents, skills and AGENTS.md keep the gap; specs/a/plan.json and LICENSE plus README.rst skip it with 0 Actions reads (arch blocking, security, quality)
- [x] T016 [US2] A file renamed from cli/wuwei/x.py to docs/x.md keeps the gap (security)
- [x] T017 [US1] Falsy kinds and a blank head do not count as owner review (security)
- [x] T018 [US3] The unreadable-host test pins the exact error text for each reply (quality)
- [x] T019 Run red: 13 failed; implement `PROSE`, the previous filename and the kind test; run green: 133 passed
- [x] T020 Name the unreadable-host text and the docs-only relaxation in Breaking and the commit (arch)
