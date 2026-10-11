# Tasks: delete the invariant walk and the prose-pinning tests

Input: `spec.md`, `plan.md` in this directory. Tests only, plus governance and docs text; no
runtime code changes. Run only the touched test files with the interpreter the task names;
CI runs the rest. A moved test passes on arrival (it tests existing behaviour), so it is shown
red once with a temporary mutation that is reverted before the next task.

## Phase 1: move the process cases first (US2, FR-003, FR-004)

- [X] T001 Run `python -m pytest -q tests/test_merge.py tests/test_invariants.py` on the
  untouched tree; record the pass counts.
- [X] T002 In `tests/test_merge.py`, add `test_merge_waits_on_gates_at_a_moved_head(case)`
  (plan.md item 2): gate files at `evidence(BASE)`, `policy().execute(REF, root)` exits 1 with
  `pre-PR gates not passed at current HEAD` in the reason, `merged_calls(host) == []`.
- [X] T003 Show T002 red: temporarily monkeypatch `wuwei.guards.pr.gate_check` (the check
  `merge.check` imports at call time, `cli/wuwei/merge.py:371`) to return `(0, '')`, run the
  test, see it fail, revert.
- [X] T004 In `tests/test_merge.py`, add `test_owner_merge_holds_on_every_path` over the five
  paths with the flag set and no grant (plan.md item 2).
- [X] T005 Show T004 red: temporarily monkeypatch `merge.owner_hold` to return `None`, run,
  see every path fail, revert.
- [X] T006 Confirm the trust-surface home passes:
  `python -m pytest -q tests/test_merge.py -k "open_security_gate or owner_path_is_merged or trust_surface"`.
  No new test (FR-004).

## Phase 2: delete the walk (US1, FR-001, FR-002, FR-007, FR-008)

- [X] T007 In `tests/test_invariants.py`, delete lines 124-1766 and the unused imports, and
  rewrite the docstring (plan.md item 1). The three moved tests go with the cut.
- [X] T008 In `tests/test_dev_cycle.py`, remove the walk's tuple from `TIMING`.
- [X] T009 Run `python -m pytest -q tests/test_invariants.py tests/test_dev_cycle.py
  tests/test_merge.py`; all pass, `tests/test_invariants.py` collects one test.
- [X] T010 `git grep -n "test_invariants_hold\|INVARIANT_BUDGET\|from test_invariants"`
  finds nothing outside `specs/` and `CHANGELOG.md`; `.github/workflows` and `scripts/` name
  neither the walk nor its budget.

## Phase 3: delete the prose-pinning tests (US3, FR-005, FR-006)

- [X] T011 In `tests/test_docs.py`, delete the 81 tests and the helpers plan.md item 3 lists;
  drop the imports no kept test uses (check each name with grep in the file).
- [X] T012 In `tests/test_charters.py`, delete the 15 tests and `RULES` (plan.md item 4).
- [X] T013 Run `python -m pytest -q tests/test_docs.py tests/test_charters.py`; 9 and 10
  test functions collect and pass (parametrized cases count more).

## Phase 4: governance and design text (FR-009, FR-010, FR-011)

- [X] T014 `.specify/memory/constitution.md`: delete the invariant-row Workflow bullet; footer
  `**Version**: 2.0.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-10-11`.
- [X] T015 `docs/specs/2026-09-24-wuwei-design.md`: replace lines 2004-2061 with the "New 9.2"
  block of plan.md.
- [X] T016 `README.md` lines 113 and 282, `NOTICE` lines 107-108: the sentences in plan.md
  items 8 and 9.
- [X] T017 Run `python -m pytest -q tests/test_tone.py tests/test_calibrate.py
  tests/test_docs.py tests/test_charters.py`; all pass with no budget changed.

## Phase 5: close

- [X] T018 Run every touched file once more: `python -m pytest -q tests/test_invariants.py
  tests/test_merge.py tests/test_docs.py tests/test_charters.py tests/test_dev_cycle.py
  tests/test_tone.py tests/test_calibrate.py`.
- [X] T019 `git grep -nP "\x{2014}"` on the changed files finds no em-dash; no emoji, no
  absolute local path, no names in the diff.
- [X] T020 Mark these tasks done. Commit message for whoever commits: dated constitution line
  "constitution 2.0.0 (2026-10-11, #798): the invariant-row Workflow rule is removed".

## Dependencies

Phase 1 before Phase 2 (the moved bodies are copied from the file Phase 2 cuts). Phases 3 and
4 are independent of each other and of Phase 2. T017 after T016. T018 last.
