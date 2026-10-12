# Tasks: the scanner runs once per repository per day and never re-parks a resumed item

- [X] T001 [US1] Tests in `tests/test_ziran.py`: `line: null` and `files_analyzed: 0` with no
  findings are measured; `files_analyzed: 0` with a finding is unmeasured; drop the two rows
  that pin the old contract. Run: red.
- [X] T002 [US1] Implement FR-001 in `ziran._report`; T001 green.
- [X] T003 [US1, US2, US6] Tests in `tests/test_plan.py`: two repos, one unmeasured, keep the
  other's rows and name the repo and the switch-off command; a null line renders as the file;
  a second discover at the same HEAD runs no audit; a slow failure is remembered, a fast one
  is not; a new HEAD audits again; an approved gate refuses before discovery. Run: red.
- [X] T004 [US1, US2] Implement FR-002, FR-003, FR-005; T003 green.
- [X] T005 [US2] Test in `tests/test_brief.py`: a lead brief computes its candidates while
  `brief.lock` is free. Run: red. Implement FR-004; green.
- [X] T006 [US3] Tests in `tests/test_traces_seats_only.py`: park, `plan resume` with the
  owner's Yes, sweep again: still resumed, one `scanner.finding`; repeated rows in one sweep
  park once. Run: red. Implement FR-006; green.
- [X] T007 [US4] Test in `tests/test_close_parked.py`: two critical chains give one card
  naming both; one Yes passes; a new chain asks again. Run: red. Implement FR-007; green.
- [X] T008 [US5, US6] Tests in `tests/test_dispatch.py`: findings outside the changed files
  are dropped (PASS kept, no events); a brief without `Merge-base:` is unmeasured; a scanner
  error names the worktree and not doctor; the trace sweep error names the switch-off. Run:
  red. Implement FR-008, FR-009; green.
- [X] T009 Run every test file that imports a changed module under 3.12, and the scanner,
  ziran, traces, close, brief, plan and discovery files under 3.11.
- [X] T010 Rerun the audit's live drivers for S1 to S7 against the worktree; record before
  and after in `quickstart.md`.
- [X] T011 [F1] Tests: a seat Write or Edit to `days/<date>/scanner-audit.json` is refused by
  the file guard; forged cache entries (no `line`, bad severity, empty row) are ignored and the
  repo re-audited; a multi-line message becomes one-line evidence. Run: red. Implement
  FR-010 in `guards/protect_state._protected_name` and `discovery._shaped`; green.
- [X] T012 [F2] Test: a new symlink in the diff to an unchanged dangerous file still blocks.
  Run: red. Implement FR-011 in `scanner.rows`; green. Live: real ZIRAN on the review's
  symlink repo gives 3 blocking rows.
- [X] T013 [F3] Test: the first state write of a park times out; no `scanner.finding` is left,
  and the next sweep parks. Run: red. Implement FR-012 in `scanner._park`; green.
- [X] T014 [F5] Test: `files_analyzed: 0` at S4 keeps PASS with a lint-clean note. Run: red.
  Implement FR-013 in `scanner.rows`; green.
