# Tasks: wide-specs

## Phase 1: Tests first

- [x] T001 [US1] [US2] `test_the_wide_trigger_counts_code_and_spec_lines_and_a_spec_contract_takes_arch` in tests/test_evidence.py (13 cases on `needed`)
- [x] T002 [US1] Two REST-shape cases in `test_the_diff_decides_which_gates_a_standard_item_needs`
- [x] T003 [US1] [US2] `test_a_long_docs_delta_carries_the_passes_and_a_long_spec_delta_is_read_by_arch`
- [x] T004 [US3] New threshold text in `test_decisions_and_done_are_stated_once_in_common`
- [x] T005 Run them on main in a `git archive` copy: 10 failed

## Phase 2: Implementation

- [x] T006 [US1] `wide` list and `lines(wide)` in `needed`
- [x] T007 [US2] `CONTRACT` matches spec contract folders; checked over `wide`
- [x] T008 [US3] charters/_common.md, docs/design.md, docs/site/concepts/evidence.md
- [x] T009 `bin/wuwei agents build`, `setup.vendor('.')`
- [x] T010 Full suite green; runtime 2,978 lines

## Phase 3: Fix round at a7654a8

- [x] T011 Rows for docs/conf.py, src/docs/x.py, NOTICE_handler.py, docs/requirements.txt, docs/openapi.yaml, a mixed-case spec contract, a proto under specs/ and code under contracts/; charter test asserts the verb and tier; run red: 4 failed
- [x] T012 `TEXT` prose test for `wide`; the contract check reads every file; docs/design.md breaking paragraph names spec contracts; site table names prose
- [x] T013 Breaking section; class probe main against head; full suite green; runtime 2,979 lines

## Phase 4: Fix round at 4b535bd

- [x] T014 Rows for requirements/prod.txt, CMakeLists.txt, charters/x.md, AGENTS.md, Specs/001-x/contracts/api.md; NOTICE_handler.py expects quality; charter test reads "lines that are not prose"; run red: 6 failed
- [x] T015 `wide` reads `PROSE`; `TEXT` dropped; `DOCS` anchors LICENSE and NOTICE; rule text in the charter, design and site
- [x] T016 Class probe and the security gate's 144,480 cases at the head; full suite green; runtime 2,978 lines
