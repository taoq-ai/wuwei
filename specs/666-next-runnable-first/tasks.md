# Tasks: a PR waiting on people never hides work that can run now, and build next and dispatch next give one answer

**Input**: `specs/666-next-runnable-first/spec.md`, `specs/666-next-runnable-first/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: User Story 1 - runnable rounds come before a PR that waits on people (P1)

### Tests first

- [X] T001 [US1] In `tests/test_next.py`, add `test_issue_acceptance_runnable_rounds_before_a_waiting_pr`:
  `approved(root, {'P': ('raised', {'pr': 'example/project#7'}), 'A': ('fix', {}), 'B': ('delta', {})}, cap=2)`;
  `found = coarse(root)`; assert `(found['state'], found['item'], found['command']) ==
  ('build', 'A', 'wuwei build next A')` and `[(r['state'], r['item']) for r in found['rows']]
  == [('build', 'A'), ('verdicts', 'B'), ('pr', 'P')]` with the `pr` row's command
  `wuwei pr act example/project#7` (spec US1.1, SC-001). Run it; it fails with state `pr`.
- [X] T002 [US1] In the same file, add a text-mode test on the same day: `main(['next'])`
  output contains the line `Queue: build A, verdicts B, pr P` (US1.2). Run it; it fails.
- [X] T003 [US1] In the same file, add a test that `step` on `approved(root, {'P': ('raised',
  {'pr': 'example/project#7'})})` with a `steward.due` event returns the steward row
  (`wuwei steward run --trigger tool-calls`), and without the event returns the `pr` row
  with no `rows` key (US1.3, US1.4). Run it; the steward assertion fails.
- [X] T004 [US1] In the same file, add a `--json` test that `rows` survives resolution:
  on the T001 day, monkeypatch `build.next_action` to return a `launch` action (as
  `test_build_rows_return_the_build_loop_action` does) and assert `row(capsys)[1]['rows']`
  equals the `rows` from T001 (FR-003). Run it; it fails (no `rows` key).

### Implementation

- [X] T005 [US1] In `cli/wuwei/commands/next.py` `step`, turn the item loop's returns into
  appends to `found` (build, docs, verdicts, one dispatch row) and `prs` (pr rows); after
  the loop build `rows` and return `found[0]` with them; after the steward block return
  `prs[0]` with them (plan.md Design 1). Update the ponytail line of the docstring. T001
  and T003 pass.
- [X] T006 [US1] In `cli/wuwei/commands/next.py` `run`, carry `row['rows']` onto the
  resolved action (plan.md Design 2). T004 passes.
- [X] T007 [US1] In `cli/wuwei/commands/next.py` `text`, append the `Queue:` line when
  `rows` is present (plan.md Design 3). T002 passes. Run `tests/test_next.py`: every
  existing test stays green (one-row answers carry no `rows`).

## Phase 2: User Story 2 - `build next` and `dispatch next` name the same step (P1)

### Tests first

- [X] T008 [US2] In `tests/test_dispatch.py`, add `test_issue_acceptance_build_next_and_dispatch_next_agree_on_a_gate_fix`,
  parametrized on call order (`build` first, `dispatch` first). Setup: `built(root)`,
  `gate_fix(root)`, `monkeypatch.setenv('WUWEI_WORKSPACE', str(root))`; read `brief` and
  `worktree` from `state.read_state(root)['builds']['A']` and call
  `main(['build', 'next', 'A', brief, worktree])` (the `built` fixture logs no brief event,
  so pass the paths) and `main(['dispatch', 'next', 'A'])` in the given order, parsing
  stdout each time. Assert: both exit 0; the dispatch answer is
  `{'action': 'fix', 'roles': ['quality'], 'command': 'wuwei build next A'}`; the build
  answer is `state.read_state(root)['builds']['A']['action']`, its `action` is `continue`
  with `resume == 'old-builder'` and the gate feedback; the item is in `fix`; exactly one
  `build.fix_opened` event (`fix_events(root)`). Run it; the build-first order fails with
  `{'action': 'done'}` (US2.1, US2.2, SC-002).
- [X] T009 [US2] In `tests/test_dispatch.py`, add the delta variant: `built`, `gate_fix`,
  `dispatch.next_step('A', root)` (round 1 opens), then mark the build `status='done'` with
  `action={'action': 'done'}`, `state.transition('A', 'delta', root)`, and
  `record(root, 'quality', 'quality-1', FIX + 'Simplicity: none\nDesign: none\n', 'delta')`
  (as `test_open_fix_from_delta_opens_the_next_round_and_moves_the_verdicts` does).
  `main(['build', 'next', 'A', brief, worktree])` exits 0 and prints the round-2 builder
  action; the item is in `fix`, `fix_rounds == 2`; a following `dispatch next A` answers
  `fix` naming `wuwei build next A` (US2.3, SC-002). Run it; it fails with `done`.
- [X] T010 [US2] In `tests/test_dispatch.py`, add a test that `build next` exits 1 with the
  refusal on stderr when `dispatch.next_step` refuses (monkeypatch it to raise
  `dispatch.Refused('builder must stand down before gates')` on a gate item with a done
  build), and exits 1 printing the answer when it returns
  `{'action': 'escalate', 'reason': 'r'}` (FR-005). Run it; it fails (exit 0, `done`).

### Implementation

- [X] T011 [US2] In `cli/wuwei/commands/build.py` `run`, the `next` branch: when
  `next_action` answers `done` and the item is at `gate` or `delta`, answer from
  `dispatch.next_step`; on `fix` print `builds[item]['action']` read after the call; catch
  `dispatch.Refused` locally (exit 1); exit 1 on `escalate` (plan.md Design 4). T008 to
  T010 pass. Run `tests/test_build_next.py`, `tests/test_build.py` and
  `tests/test_dispatch.py`: existing tests stay green (the Codex loop still ends on `done`).

## Phase 3: Docs (FR-007)

- [X] T012 [P] `docs/site/reference.md` line 49: the `bin/wuwei next` row names `rows` and
  the `Queue:` line (plan.md Docs).
- [X] T013 [P] `docs/site/reference.md` line 304: the Automatic phases row says `build next`
  past a done build at `gate` or `delta` answers what `dispatch next` decides.
- [X] T014 [P] `docs/specs/2026-09-24-wuwei-design.md` Step loop amendment (line 587): one
  sentence for the same rule, citing #666.

## Phase 4: Verify

- [X] T015 Run the full suite (`python -m pytest -q` from the repository root with the
  interpreter the task names); all green. Grep the changed files for em-dashes and emojis.
