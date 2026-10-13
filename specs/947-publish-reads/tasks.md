# Tasks: #947 publish reads

## Setup and foundation

- [x] T001 Record scope, assumptions and root causes in specs/947-publish-reads/spec.md and research.md.
- [x] T002 Complete plan, analysis and requirements review in specs/947-publish-reads/ before implementation.

## US1: Read deployment metadata

- [x] T003 [US1] Add read and mutation cases to tests/test_edges.py and observe the expected failing reads.
- [x] T004 [US1] Fix api and command_result in cli/wuwei/guards/edges.py with narrow read predicates.

## US2: Explain exact command approval

- [x] T005 [US2] Reproduce missing binding text and test corrected/compound workflow approval in tests/test_edges.py before implementation.
- [x] T006 [US2] Update the publish needs_owner detail in cli/wuwei/guards/edges.py.

## Validation and review

- [x] T007 Run tests/test_edges.py and all test files importing edges; record exact summaries in specs/947-publish-reads/analysis.md.
- [x] T008 Review correctness, security and complexity; inspect diff, branch and artifact hygiene, then mark specs/947-publish-reads/tasks.md complete.

## Dependencies and strategy

T001 -> T002 -> T003 and T005 (both test-first) -> T004 -> T006 -> T007 -> T008.
US1 and US2 share both edited files, so implement sequentially. No useful parallel agent work. US1 is the first independently testable delivery; US2 completes the issue. Do not commit or push.


## Authorized review follow-up

- [x] T009 Record F1/F3 scope, F2/F4 owner decisions and review analysis in specs/947-publish-reads/.
- [x] T010 [US1] Reproduce preview and multiple-target failures in tests/test_edges.py, then fix GH_VALUED and api() in cli/wuwei/guards/edges.py and verify green.
- [x] T011 [US1] Reproduce override-header failures in tests/test_edges.py, then add the header predicate in cli/wuwei/guards/edges.py and verify green.
- [x] T012 Run every test file importing edges plus tests/test_signal_status.py; record results and per-finding disposition in specs/947-publish-reads/analysis.md.

Follow-up dependencies: T009 -> T010 -> T011 -> T012. The user's follow-up explicitly authorizes this fix round; no host-permission or owner-design changes.
