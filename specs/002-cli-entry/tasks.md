# Tasks: CLI entry point

**Input**: spec.md, plan.md, contracts/cli.md

## Phase 1: Setup

- [X] T001 Read scaffold, constitution, and design; validate specs/002-cli-entry/spec.md.
- [X] T002 Record design and command interface in specs/002-cli-entry/plan.md and contracts/cli.md.

## Phase 2: Foundation and US1 (P1)

Independent check: fixture commands preserve 0/1/2, forward arguments, and fail closed.

- [X] T003 [US1] Write tests/test_cli.py tests for shared constants, discovered commands, exceptions, invalid results, and usage; observe failure.
- [X] T004 [US1] Implement cli/wuwei/__init__.py, exits.py, commands/__init__.py, and __main__.py; run US1 tests to green.

## Phase 3: US2 (P2)

Independent check: version and help work from unrelated directories through both entry points.

- [X] T005 [US2] Add version and metadata-error tests in tests/test_cli.py; observe failure.
- [X] T006 [US2] Add manifest-backed version handling in cli/wuwei/__main__.py; run tests to green.
- [X] T007 [US2] Add shim tests for spaces, working directory, arguments, and exit propagation in tests/test_cli.py; observe failure.
- [X] T008 [US2] Add executable bin/wuwei; run tests to green.

## Phase 4: US3 (P2)

Independent check: import audit rejects a temporary forbidden import.

- [X] T009 [US3] Add AST audit in tests/test_stdlib.py; demonstrate failure on a temporary forbidden import under cli/ and adapters/.
- [X] T010 [US3] Remove temporary mutation and verify tests/test_stdlib.py passes.

## Phase 5: Validation

- [X] T011 Run full pytest suite, review CLI failure boundaries, check written files for banned characters and whitespace, and record results in specs/002-cli-entry/tasks.md.
- [X] T012 Fix review F1: reproduce converter OSError, wrap parsing while preserving argparse SystemExit, and verify exit 2.
- [X] T013 Fix review F2: reproduce missing python3, CLI, and dirname failures; add shim preflight checks and verify exit 2.
- [X] T014 Fix review F3: reproduce private helper discovery failure, skip underscore names, and document the contract.
- [X] T015 Fix review F4: remove red-phase fixture scaffolding and redundant tests; retain three distinct invalid-result and metadata cases.

## Dependencies and Execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010 -> T011.
US1 supplies the minimal dispatcher; US2 adds installation entry points; US3 audits all runtime
sources. Work is sequential in this seat because the CLI tests and dispatcher are shared.
US3's audit could be authored independently after US1, but no parallel agents are needed.

## Deferred

Business commands, guards, adapters, and workspace state remain in later issues.

## Verification Results

- US1 red: 21 tests failed because the CLI package and entry point were absent; green: 21 passed.
- Version red: 4 failed before implementation; green: 25 CLI tests passed.
- Shim red: 5 failed because bin/wuwei was absent; green: 30 CLI tests passed.
- Import audit rejected temporary forbidden imports under both cli/ and adapters/;
  both mutations were removed and the audit passed.
- Review added null, numeric, and empty manifest-version cases: 3 failed, then version
  validation made the full suite pass.
- Full suite: 39 passed. Runtime subprocess tests use -S to exclude site packages.
- Local correctness and simplicity review completed. No production demo command, new
  dependency, or shared registry. No commits, pushes, or gh commands performed.
- Review regressions: F1 failed with exit 1 before the fix; F2 failed with exits 127,
  1, and 1; F3 failed with exit 2. Each passed after its corresponding fix.
- After review fixes and cleanup: 36 passed. Invalid-result cases retain non-integer,
  boolean, and out-of-range coverage; metadata cases retain read failure, non-string,
  and empty-string coverage. Existing help, usage, version, and shim argument tests remain.
