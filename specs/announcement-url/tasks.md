# Tasks: announcement-url

## Phase 1: Tests first

- [x] T001 [US1] [US2] `test_an_announcement_counts_only_as_one_http_url_alone_on_its_line` in tests/test_evidence.py (32 rows: 6 count, 26 leave the gap)
- [x] T002 [US1] New gap text in `ANNOUNCE` (tests/test_evidence.py) and tests/test_breaking.py; the moved-head test names a URL instead of `CHANGELOG.md`
- [x] T003 [US3] `test_the_shepherd_asks_for_an_announcement_url_that_exists_at_the_head` in tests/test_charters.py
- [x] T004 Run them on main in a `git archive` copy: red

## Phase 2: Implementation

- [x] T005 [US1] [US2] The pattern and the gap text in `breaking_gaps`
- [x] T006 [US3] charters/shepherd.md Merge section
- [x] T007 `bin/wuwei agents build`, `setup.vendor('.')`
- [x] T008 `specs/announcement-url/probe.py` in a `git archive` copy: no hole, no mutant survives
- [x] T009 Full suite green; runtime 2,992 lines, unchanged

## Phase 3: Gate round 1

- [x] T010 Timing row `test_a_body_at_the_github_limit_is_read_in_linear_time`: red at 46d4737 (77.9 s)
- [x] T011 One host character in the pattern; the gap text says "without brackets"
- [x] T012 docs/design.md, docs/site/reference.md, docs/site/concepts/evidence.md, charters/_common.md name the shape
- [x] T013 Probe mutants written to both copies; a slow-pattern mutant added: 9 mutants, 0 survived
