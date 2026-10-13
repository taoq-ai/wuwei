# Tasks: Owner step card token binding

## Setup and foundation

- [x] T001 Trace identity, hints and all card callers; record root cause in specs/940-card-token/plan.md.
- [x] T002 Complete specification, clarification, plan, analysis and requirements checklists in specs/940-card-token/ before implementation.

## US1: Answer with context

- [x] T003 [US1] Add extended-question, latest-answer, seat and consumption regressions in tests/test_card_confirms.py and build continuation coverage in tests/test_one_action.py; observe red.
- [x] T004 [US1] Canonicalize the leading card identity in cli/wuwei/guards/answers.py; preserve hashed topics and reply lookup.

## US2: Name mismatches

- [x] T005 [US2] Add missing-token and wrong-command refusals in tests/test_card_confirms.py, tests/test_one_action.py and tests/test_dispatch.py, including build and dispatch; observe red.
- [x] T006 [US2] Extract shared mismatch reporting in cli/wuwei/sessions.py and route cli/wuwei/dispatch.py direct-card refusals through it.

## Verification

- [x] T007 Run focused tests and all changed-module importer test files under tests/ with explicit arguments; save exact summaries in specs/940-card-token/analysis.md.
- [x] T008 Review correctness, authorization and complexity; inspect git diff and complete specs/940-card-token/analysis.md.

## Dependencies and execution

T001 -> T002 -> T003 and T005 -> T004 -> T006 -> T007 -> T008. US1 and US2 share fixtures and core files, so execute inline and sequentially. MVP is US1, but completion requires both stories. No parallel agent work is necessary.

## Owner-requested review follow-up

- [x] T009 [US1] Reproduce F1 contradictory canonical-card replies through the real hook in tests/test_card_confirms.py, then fail closed in cli/wuwei/sessions.py.
- [x] T010 [US2] Reproduce F3 spent-history hints in tests/test_card_confirms.py, then bound diagnostic history by the command's latest approval in cli/wuwei/sessions.py.
- [x] T011 [US2] Reproduce F2 multiline tokenless mismatch hints in tests/test_card_confirms.py, then record the first-line diagnostic topic in cli/wuwei/guards/answers.py.
- [x] T012 Rerun requested and importer tests, review the delta, and record exact summaries in specs/940-card-token/analysis.md.
