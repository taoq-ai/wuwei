# Tasks: Tracker hygiene (spec amendment)

Spec-only. The amendment text is in specs/416-tracker-hygiene-spec/contracts/design-amendment.md
(blocks A to E). The builder runs the phrase check (T002) red against a `git archive main`
export before pasting anything, then pastes, reruns it green, reviews and verifies. No
runtime code, no committed test.

## Phase 1: Setup

- [X] T001 Write specs/416-tracker-hygiene-spec/spec.md, plan.md, tasks.md and contracts/design-amendment.md from issue #416 and the orchestrator notes.

## Phase 2: Test first (US1, US2, US3)

Independent test: the check script in specs/416-tracker-hygiene-spec/plan.md "Verification commands".

- [X] T002 [US1] [US2] [US3] Copy the check script from specs/416-tracker-hygiene-spec/plan.md into a scratch directory outside the repository as check_416.py. Export `git archive main docs/specs .specify/memory` there and run the script on the export; confirm it fails with `AssertionError: 5.11 section`. Run it on the worktree before any paste; it fails the same way.

## Phase 3: Amendment (paste, then review)

- [X] T003 [US1] [US2] Paste block A of contracts/design-amendment.md into docs/specs/2026-09-24-wuwei-design.md as `### 5.11 Tracker hygiene (owner, 2026-10-03, #416)`, after the last `### 5.x` section and before `## 6. Memory`.
- [X] T004 [US3] Apply blocks B, C and D to docs/specs/2026-09-24-wuwei-design.md: the 4.1 PreToolUse `Agent` launch row, the 4.9 tracker-writes bullet after "Precedence:", the section 8 tracker row.
- [X] T005 [US3] Apply block E to .specify/memory/constitution.md: the Workflow bullet after the cycle budget bullet, and the version line (1.2.0, Last Amended 2026-10-03, or one minor above #411's bump if it merged first).
- [X] T006 [US1] [US2] [US3] Rerun check_416.py on the worktree; it prints `OK: tracker hygiene stated`.
- [X] T007 [US2] Consistency review of docs/specs/2026-09-24-wuwei-design.md as plan.md "Consistency review" lists (3.5, 4.1, 4.3, 4.6, 4.9, 5.3, 5.6, 5.7, 5.8.1, 8, 9.1). Walk the seven #417 acceptance lines against 5.11 and plan.md "Implementation map for #417"; each must have its answer. Edit only the design spec and only for a real conflict, extending check_416.py first and seeing it fail for any new phrase; rerun T006 after any edit.

## Phase 4: Verify (US3)

- [X] T008 [US3] Run `git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts docs/site tests README.md` (must be empty) and `git status --short` (only docs/specs/2026-09-24-wuwei-design.md, .specify/memory/constitution.md and specs/416-tracker-hygiene-spec/).
- [X] T009 [US3] Run `python -m pytest -q` from the repository root; everything passes, including tests/test_docs.py and tests/test_calibrate.py. Check docs/specs/2026-09-24-wuwei-design.md, .specify/memory/constitution.md and every file in specs/416-tracker-hygiene-spec/ for em-dashes, emojis and absolute local paths.

## Phase 5: Review fixes

- [X] T010 [US2] Review F1 and F2: extend check_416.py with the humanizer phrase (`[outward] humanize`, #420) and the external-party phrase (a GitHub `project` or `board` outside `outbound.code_host_orgs`), see it fail, then add both sentences to 5.11 Approval and the external-party sentence to the 4.9 tracker-writes bullet, in the design spec and in contracts/design-amendment.md blocks A and C. Rerun T006 and T009.
