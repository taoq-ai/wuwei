# Tasks: Documented schemas and actionable errors

## Phase 1: Templates [US1]

- [X] T001 [US1] Add failing template contract tests in tests/test_templates_errors.py
- [X] T002 [US1] Implement plan, rank and decision templates and stdin in cli/wuwei/commands/plan.py, cli/wuwei/commands/rank.py and cli/wuwei/commands/decision.py

## Phase 2: Reference [US2]

- [X] T003 [US2] Add failing documentation contract test in tests/test_docs.py
- [X] T004 [US2] Add docs/site/reference.md and link it from docs/site/index.md

## Phase 3: Errors and timeout [US3]

- [X] T005 [US3] Add failing message table and timeout tests in tests/test_templates_errors.py
- [X] T006 [US3] Improve refusal reasons at their sources in cli/wuwei and adapters

## Phase 4: Verify

- [X] T007 Run full pytest suite and check changed files for prohibited characters
