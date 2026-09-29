# Tasks: Step-wise build loop

- [X] T001 Read design, constitution and current implementation; reproduce dry-run failures read-only.
- [X] T002 Specify scenarios and write the implementation plan.
- [X] T003 Write failing tests for Claude actions, hook continuation, checks, idempotency, producer protection and legacy refusal.
- [X] T004 Implement shared next-action selection, result/check recording and valid park decisions; preserve Codex loop semantics.
- [X] T005 Integrate Agent registration and SubagentStop with producer-owned build state and safe continuation.
- [X] T006 Write failing tests for default four-seat capacity and host.seats refusal.
- [X] T007 Update host defaults and builder-only CAP enforcement.
- [X] T008 Update design 5.3, planner skill and site documentation.
- [X] T009 Run full pytest suite, inspect diff and check hygiene; mark completed tasks.
- [X] T010 Reproduce Codex timeout recovery failure, resume the persisted job on rerun, and remove unused build.result producer metadata (F1, F3).

## Fix review

- F1: Regression failed on the rerun with "builder is still running" before the fix.
  Reruns now poll the saved job without launching again or duplicating usage.
- F2: Deferred. Rebasing the uncommitted feature onto main is outside the small optional
  fixes in this round. The agent_launch.py merge conflict still needs integration resolution.
- F3: Removed the unused producer entry and its test parameter.

## Verification

- Final full suite after fix review: 4981 passed, 2 skipped in 84.52s (0:01:24).
- All three timing checks passed.
- Independent correctness and trust-boundary review plus delta completed. Regression tests
  cover replayed and delayed stops, delayed checks, dirty cached evidence and non-builder resumes.
- Diff whitespace and changed-file hygiene checks passed. Changes remain in the working tree.
