# Tasks: a seat starts from an empty scratch directory and checks only a clean copy

Test first: each test task runs and fails for the expected reason before its implementation
task. Tests run in-process with the existing fixtures (`day` in `tests/test_brief.py`, `root`
and `record` in `tests/test_dispatch.py`); no subprocess, no network. Run the touched test
file after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: a new seat starts empty (US1, FR-001, FR-002)

- [X] T001 Test in `tests/test_brief.py`: `test_a_new_seat_moves_an_earlier_seats_scratch_aside`
  (next to `test_each_seat_gets_its_own_scratch_directory`). With the `day` fixture
  (`WUWEI_NOW` `2026-09-28T12:00:00+00:00`): create `.wuwei/scratch/X/builder/stale.py`, write a
  `builder` brief on `X`; assert `.wuwei/scratch/X/builder/` exists and is empty, and
  `.wuwei/scratch/X/builder.20260928T120000.000000/stale.py` exists. Then create an empty
  `.wuwei/scratch/Y/builder/`, write a brief on `Y`; assert the directory is kept and
  `.wuwei/scratch/Y/` holds only `builder`. Assert the `Scratch:` line contains
  `move it aside with a timestamp suffix when it holds files you did not write`. Run it: fails
  (`stale.py` still in place, no clause).
- [X] T002 Implement in `cli/wuwei/brief.py` `write`: the header clause (lines 424-426) and the
  move-aside before the final `mkdir` (line 586), as `plan.md` gives. T001 and
  `test_each_seat_gets_its_own_scratch_directory` pass.

## Phase 2: gates check only a clean copy (US2, FR-003)

- [X] T003 Test in `tests/test_charters.py`: `test_gate_copies_start_empty_and_match_the_tree`.
  Assert `charter_text()['_common.md']` contains each anchor exactly once:
  `in a new, empty directory under your brief's \`Scratch:\` directory`,
  `git ls-tree -r --name-only <sha>` and `list each extra file in the verdict`; and that every
  `agents/sentinel-*.md` (repository root) contains all three. Run it: fails (anchors absent).
- [X] T004 Implement in `charters/_common.md` rule 2: insert the two sentences after the
  detached-copy sentence (text in `plan.md`), bump `version: 1.9.0` to `1.10.0`, then run
  `bin/wuwei agents build` from the repository root with `WUWEI_WORKSPACE` unset so `agents/*.md`
  are regenerated. T003, `tests/test_agents.py` (`test_checked_in_agents_match_charters_and_allowlist`)
  and the rest of `tests/test_charters.py` (one home, ordered checklists) pass.

## Phase 3: receive warns on stale scratch evidence (US3, FR-004)

- [X] T005 Test in `tests/test_dispatch.py`: give the `record` helper a keyword
  `brief='Head: abc1234\n'` used for the brief text (existing callers unchanged). Add
  `test_receive_warns_on_scratch_evidence_older_than_its_brief`, parametrized over the brief's
  second line: `Written: 2099-01-01T00:00:00+00:00` (expects 2 warnings),
  `Written: 2000-01-01T00:00:00+00:00` (expects 0) and no line (expects 0). Create
  `root/.wuwei/scratch/A/sentinel-arch/copy/x.py`; the verdict is `PASS` with its `Probe:` row
  replaced by `Probe: ruff on .wuwei/scratch/A/sentinel-arch/copy/x.py:3 and <the same file as
  an absolute path, built from root> and .wuwei/scratch/A/sentinel-arch/gone.py: clean`
  (`gone.py` does not exist). Call `record(root, 'arch', 'arch-1', verdict, brief='Head:
  abc1234\n' + line)`; assert it returns verdict `PASS` and `A:arch:initial` is in
  `gate_verdicts`, and that stderr (capsys) holds the expected number of `warning:` lines, each
  naming `arch-1` and one of the two existing path forms, none naming `gone.py`. Run it: the
  2099 case fails (no warning).
- [X] T006 Implement in `cli/wuwei/dispatch.py`: `SCRATCH_PATH`, `_stale_scratch` and the warning
  loop after the state write in `receive`, as `plan.md` gives. T005 passes; the rest of
  `tests/test_dispatch.py` passes unchanged.

## Phase 4: docs and the suite (FR-005)

- [X] T007 Update the `Scratch directory` row in `docs/site/reference.md` (line 310) with the text
  in `plan.md`. Run any docs test that reads the reference page (`python -m pytest -q -k docs`).
- [X] T008 Run the full suite (`python -m pytest -q`); everything passes. Check every file this
  item wrote or changed for em-dashes and emojis and remove any; no absolute local paths in any
  test or doc.
