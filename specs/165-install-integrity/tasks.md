# Tasks: Checkout install integrity

## Setup

- [X] T001 Read integrity and VCS code and reproduce the operator failure read-only; record findings in specs/165-install-integrity/plan.md.
- [X] T002 Complete specs/165-install-integrity/spec.md and plan.md with assumptions and design.

## US1: Confirm a development checkout once

- [X] T003 [US1] Add and run failing clean-checkout, moved-HEAD, dirty-tree, malformed evidence, confirmation-race and scope tests in tests/test_integrity.py using tests/fakes/vcs.py.
- [X] T004 [US1] Implement shared checkout evidence, confirmation pinning and cached validation in cli/wuwei/integrity.py; pass focused tests.

## US2: Install the signed release

- [X] T005 [US2] Add and run regression assertions in tests/test_integrity.py and failing release-installation documentation assertions in tests/test_docs.py.
- [X] T006 [US2] Update README.md, docs/site/index.md and .claude-plugin/marketplace.json to document signed releases and development confirmation; pass focused tests.

## Final verification

- [X] T007 Run the full pytest suite, review scope and producer protections, and check every changed file for hygiene; record results in specs/165-install-integrity/tasks.md.

## Review fixes

- [X] T008 [US1] Reproduce F1 with ignored file and symlink regressions; hash on-disk paths tracked at the confirmed HEAD through the existing VCS read_tree operation, allowing the repository root selector and failing closed on unavailable tree evidence.
- [X] T009 [US2] Reproduce F2 with a documentation assertion and correct docs/integrity.md to describe clean-commit confirmation.
- [X] T010 Run the full suite after review fixes and record the final result.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007.
US1 is the minimum functional increment; US2 completes the required installation flow.
Independent test criteria are the lifecycle table for US1 and signed release plus
entry-document assertions for US2. No parallel execution is needed for this small diff.

## Deferred

F3: Checkout PreToolUse still reads HEAD and status with two Git processes. The review
reported about 106 ms wall time versus 54 ms for signed installs. These wall timings
do not establish the spec's 50 ms p95 CPU budget. Defer optimization to a combined
porcelain-v2 status operation if needed; no performance change in this fix round.

## Validation results

- Checkout red phase: 15 failed, 4 passed; failures showed missing commit metadata,
  stale cache acceptance and missing confirmation race checks.
- Documentation red phase: 1 failed, 84 passed; the release download path was absent.
- Focused green phase: 91 passed across integrity, docs and manifest tests.
- Full suite: 4949 passed, 5 skipped in 110.38s (0:01:50).
- Final review: existing scope helpers, integrity producer restrictions and signed
  verification remain intact. No new port, dependency or configuration.
- Diff whitespace and all 10 added or changed files passed local-path and character
  hygiene checks. Changes remain uncommitted in the working tree.
- Review red phase: 7 failed, 2 passed for ignored artifacts, unavailable tree evidence
  and the root tree selector; documentation regression: 1 failed, 3 passed.
- Review focused green phase: 159 passed across integrity, VCS and documentation tests.
- Review full suite: 4956 passed, 5 skipped in 98.65s (0:01:38).
