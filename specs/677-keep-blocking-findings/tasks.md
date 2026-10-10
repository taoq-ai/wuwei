# Tasks: receive keeps every blocking finding

Test first: run each test task and see it fail for the expected reason before its
implementation task. Tests are in-process, use neutral synthetic verdict text in the
reproduced shape (spec, Root cause) and the existing fixtures (`VALID`, `PASS`, `RETRO` in
`tests/test_verdict.py`; `root`, `record`, `FIX`, `PASS` in `tests/test_dispatch.py`). No
text from any real workspace goes into the repository. Run the touched test files, then the
full suite.

## Phase 1: every role's id starts a finding (FR-001; US1.2)

- [X] T001 Test in `tests/test_verdict.py`: a FIX verdict in the reproduced shape
  (`## Blocking findings`, `<id>. Severity: medium. File: src/a.py:80. blocks: yes.` with a
  prose line and a `Failure scenario:` line, a second blocking finding, `## Non-blocking
  findings` with an `N1.` finding `blocks: no`, and an `Assumption:` finding), parametrized
  over (role, id): (`sentinel-arch`, `A1`), (`sentinel-quality`, `Q1`),
  (`sentinel-security`, `S1`), (`sentinel-goal`, `G1`), plus `F1`, `[Q1]` and `Finding 1`
  under `sentinel-quality`. Assert `finding_blocks(active_text(text))` first lines start with
  the id, the second blocking id, `N1.` and `Assumption:` in that order, the first two carry
  `blocks: yes`, and `lint_file(path, role=role)` on the file (with the role's required rows:
  class line, and `Simplicity:`/`Design:` for quality) returns code 0. Fails today: the id
  lines are dropped.
- [X] T002 Implement `FINDING_ID` in `cli/wuwei/verdict.py` and use it at line 62 and line
  71 (plan, Design). T001 passes; `tests/test_verdict.py` marker tests
  (`test_numbered_and_id_findings_need_their_own_citation`,
  `test_finding_marker_with_separate_severity_row`) still pass.

## Phase 2: a FIX with no parsed blocking finding is refused (FR-002; US2.2, US2.3)

- [X] T003 Tests in `tests/test_verdict.py`: (a) a FIX whose blocking finding is a `### Q1
  high` heading plus a prose line ending `blocks: yes`, with one `Assumption: ... blocks:
  no` finding: `lint` returns 1 and the message contains `FIX verdict but no blocking
  finding parsed; the lines that look like findings are: ` followed by that prose line;
  (b) `VALID` with `blocks: yes` replaced by `blocks: no`: the message contains `findings are:
  none` and `Verdict: PASS`; (c) the same texts as PASS, PARK and ESCALATE carry no FIX
  failure; (d) a fenced example line with `blocks: yes` is not named. Plus one write-guard
  case through the existing `check_write` path (as in `test_write_guard_table`) refusing (a)
  with the same message.
- [X] T004 Update the tests that encode the old rule, keeping their intent (plan, table):
  `test_source_accepted_verdict_forms` keeps `blocks: yes` for FIX; `test_assumption_is_a_finding_kind`
  expects the FIX rule for `ASSUMED` and `OK: PASS` for its PASS form. Both in
  `tests/test_verdict.py`.
- [X] T005 Implement the FIX rule in `verdict.lint` in `cli/wuwei/verdict.py`, right after the
  PASS rule (plan, Design). T003 and T004 pass, `test_source_refusal_order` still passes.

## Phase 3: receive records blocking findings first and refuses the lost ones (FR-003; US1.1, US2.1)

- [X] T006 Tests in `tests/test_dispatch.py` with the `root` fixture and `record`: (a) the
  #677 acceptance: `record(root, 'quality', 'quality-1', <reproduced-shape FIX with Q1, Q2
  blocking, N1 and an assumption> + 'Simplicity: none\nDesign: none\n')` returns
  `blocks is True`, `findings[0]` starts `Q1.`, `findings[1]` starts `Q2.`, both contain
  `blocks: yes`, and `notes` hold the N1 and assumption blocks; write the verdict with the
  non-blocking section first so the order assertion fails on today's file order too;
  (b) the T003(a) text as a quality verdict: `record` raises `dispatch.Refused` matching
  `FIX verdict but no blocking finding parsed`, and `state.read_state(root)['gate_verdicts']`
  is empty.
- [X] T007 Update the dispatch and PR guard tests that record a FIX with only `blocks: no`
  residuals (plan, table): `test_delta_nonblocking_residual_becomes_review_note` and
  `test_issue_acceptance_document_item_ships_its_notes_after_two_rounds` in
  `tests/test_dispatch.py`, `test_pr_gate_accepts_nonblocking_delta_residual` in
  `tests/test_pr_guards.py`: the residual verdict (file and record) is `Verdict: PASS` with
  the same `blocks: no` finding; every outcome assertion stays.
- [X] T008 Implement the sorted blocks in `dispatch.receive` in `cli/wuwei/dispatch.py` line
  681 (plan, Design). T006 and T007 pass.

## Phase 4: invariant and docs (FR-004, FR-005)

- [X] T009 Test: add the invariant check (next free id, I36 on `main` today) to
  `tests/test_invariants.py` (plan, Design) and its row to design 9.2 in
  `docs/specs/2026-09-24-wuwei-design.md`; registered in `INVARIANTS` and `READS` with `()`.
  It passes once T002 and T005 are in; confirm it fails with either change reverted.
- [X] T010 Docs: `docs/site/reference.md` "Gate verdict layout" lint rules (lines 365-366):
  the FIX rule and the id forms (plan, Design). Run any docs test that reads the reference
  (`tests/test_docs.py` if it covers it).

## Phase 5: verify

- [X] T011 Run the full suite with `python -m pytest -q` from the repository root. Read any
  failure beyond the plan's table before changing it. Check every file written for
  em-dashes, emojis and absolute local paths.
