# Tasks: PR guards

## Setup

- [X] T001 Read contracts and create spec and plan in specs/009-pr-guards/.

## US1: PR creation

- [X] T002 [US1] Write and run failing verdict/reviewer/port tables in tests/test_pr_guards.py.
- [X] T003 [US1] Implement current-HEAD verdict checks in cli/wuwei/guards/pr.py.

## US2: Merge, approval and protection

- [X] T004 [US2] Write and run failing command/API/profile tables in tests/test_pr_guards.py.
- [X] T005 [US2] Implement action checks and merge_check stub in cli/wuwei/guards/pr.py.

## US3: Scope and bypass resistance

- [X] T006 [US3] Write and run failing relevance, scope, wrapper and mutation tests in tests/test_pr_guards.py.
- [X] T007 [US3] Implement scoped normalization and registration in cli/wuwei/guards/pr.py.

## Verification

- [X] T008 Run full pytest, inspect diff and hygiene, and finish specs/009-pr-guards/tasks.md.

## Dependencies and delivery

T001 precedes test tasks; each test task precedes its implementation. US1, US2 and
US3 share a module, so implementation is sequential. Independent test tables can
be designed in parallel, but no additional agents are needed. US1 is the initial
increment; all three stories are required before completion. Every task includes
its file or validation target and each story has independent table assertions.

## Execution evidence

The initial table failed with 103 missing-guard assertions. The implementation
passed those cases, then additional failing regression tests covered compound
creation, malformed port success, method ordering, endpoint normalization, global
flags, target scope and lint consistency. The focused suite now has 140 passing
cases. Read-only adversarial review received one fix round and a delta review.

Prior full-suite result: `2671 passed in 22.73s`.

## Adversarial review fixes

- [X] T015 [F5] Extend the init permissions test and existing deny list for approval and admin merges.
- [X] T016 [F9] Test repeated options and share the PR/deploy option reader in cli/wuwei/shell.py.
- [X] T017 Run the requested full pytest suite after the deferred fixes.

- [X] T009 [F1] Verify the existing alias refusal and unknown-command table in tests/test_pr_guards.py (10 passing cases).
- [X] T010 [F2] Reproduce outside-workspace false refusals, then scope parse failures from cd/pushd targets in cli/wuwei/guards/pr.py.
- [X] T011 [F3, F8] Add failing branch-merge/ref API and merge-context tests, then implement protected-ref checks and the contextual merge_check signature.
- [X] T012 [F4] Add failing environment tables, then limit PR-create refusals to repository-selecting variables.
- [X] T013 [F6, F7] Add failing help/version and endpoint normalization tables, then implement the small compatibility fixes.
- [X] T014 Run the requested full pytest suite and inspect the final working tree.

Each changed correctness behavior was observed failing before its fix. Focused
validation: 242 passing PR guard cases, including query/fragment endpoint regressions.
F1 was already implemented on arrival and
needed verification only. F5 was deferred before the rebase because this branch had neither deploy
rules nor the init settings writer to extend. F9 was deferred because deploy.py was
absent and commit_push had no equivalent workspace scope helper to reuse; creating
and migrating that shared layer would broaden this review fix.

Final full-suite result with the requested interpreter: `2773 passed in 27.55s`.
The preceding run had one PostToolUse latency failure (60.10 ms CPU p95); the
unchanged rerun measured 44.08 ms and passed. Hygiene checks passed. All changes
remain in the working tree; no commit, push or gh command was run.

## Deferred findings after rebase

F5 now extends the existing PERMISSIONS_DENY list with the four requested approval
and admin-merge patterns. The init writer is unchanged; its test checks the exact
merged deny list and preservation of existing settings.

F9 now uses shell.operands in both guards, with last-value-wins for repeated
options and method/repository aliases. PR global flags retain their original
order. The existing workspace scope helpers remain outside this change.

The initial regressions produced nine expected failures, then two additional
failures exposed reordered global repository flags. Full validation after the
fixes with the requested interpreter: `3287 passed, 3 skipped in 35.90s`.
No git commands were run or local machine paths added to the changed files.
