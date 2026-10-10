# Tasks: the raise action is a ready-to-run shepherd launch that opens the PR with wuwei pr raise --item

**Input**: `specs/783-raise-is-a-launch/spec.md`, `specs/783-raise-is-a-launch/plan.md`

**Tests**: required (constitution IV). Each behaviour's test task comes before its
implementation task; run the test and see it fail for the expected reason before the code.
Run tests with `python -m pytest -q <file>` from the repository root; the full suite runs in
CI (owner, 2026-10-10).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: raise is the shepherd launch (User Story 1, P1)

- [X] T001 [US1] In `tests/test_dispatch.py`, after the #666 tests, add
  `test_issue_acceptance_raise_is_the_shepherd_launch(root, monkeypatch, capsys)`:
  `tree = built(root)`; `record` arch and security with `PASS` and quality with
  `PASS + 'Simplicity: none\nDesign: none\n'`; `monkeypatch.setenv('WUWEI_WORKSPACE', str(root))`.
  (a) `cli(capsys, 'dispatch', 'next', 'A')` and `build_next(capsys, root)` both exit 0 and
  print equal JSON with `action == 'raise'`, `notes == []`, `seats == []` and one
  `commands` entry starting `f'wuwei brief shepherd A shepherd-A --worktree {tree} --body '`
  that contains `bin/wuwei pr raise`, `--item A` and `gh pr create`.
  (b) Write `workspace.day_dir(root) / 'briefs/shepherd-A.md'` (`'brief\n'`): both print
  equal JSON with `seats == [brief.seat_action('shepherd', path, str(tree), root)]` and no
  `commands` key.
  (c) Record seat `shepherd-A` (`{'item': 'A', 'role': 'shepherd', 'status': 'running'}`,
  `state._write_state`, `reserved=False`): `seats == []`, no `commands`, and `reason`
  contains `shepherd-A`, `running` and `bin/wuwei why A` (spec US1 scenarios 1 to 3,
  FR-001, FR-002, FR-004). Run it; it fails at (a) on the missing `seats` and `commands`
  keys.
- [X] T002 [US1] In `tests/test_dispatch.py`,
  `test_delta_nonblocking_residual_becomes_review_note` (line 175): also assert
  `'Review note: ' in outcome['commands'][0]` (US1 scenario 4, the delta raise point). Run
  it; it fails (`KeyError: 'commands'`).
- [X] T003 [US1] In `cli/wuwei/dispatch.py`, add `SHEPHERD_BODY` and
  `raise_action(root, data, item, notes)` next to `GATE_BODY` (plan, Design 1), and make
  both raise returns in `next_step` (lines 379 and 397) return it (plan, Design 2). Run T001
  and T002; both pass.
- [X] T004 [US1] Update the whole-dict raise asserts that T003 changes:
  `tests/test_dispatch.py` lines 107, 698, 777, 813 and 1223 and
  `tests/test_parallel_dispatch.py` line 127 compare only `action` and `notes`, for example
  `assert {key: found[key] for key in ('action', 'notes')} == {'action': 'raise', 'notes': []}`
  (spec A8). Run both files; all pass.

## Phase 2: wuwei next renders the shared action (User Story 1, FR-005)

- [X] T005 [US1] Refactor under the existing tests: run
  `tests/test_next.py -k "verdict_rows_return_the_gate_action or shepherd_launch_then_card"`
  (green). In `cli/wuwei/commands/next.py`, make `_shepherd` render
  `dispatch.raise_action` and delete `SHEPHERD_BODY` (plan, Design 3). Run the same
  selection and `tests/test_dispatch.py::test_issue_acceptance_document_item_ships_its_notes_after_two_rounds`;
  all pass unchanged.

## Phase 3: the shepherd charter (User Story 2, P1)

- [X] T006 [US2] In `tests/test_charters.py`, `test_amended_role_rules`, assert that
  `texts["shepherd.md"]` contains `wuwei pr raise`, `--item <item>`, `gh pr create` and
  `wuwei pr claim`. Run it; it fails on `wuwei pr raise`.
- [X] T007 [US2] In `charters/shepherd.md`, bump the version to `1.1.0` and rewrite the
  first sentence of "PR raise" step 2 (plan, Design 5). Run `bin/wuwei agents build`;
  confirm only `agents/shepherd.md` changed. Run `tests/test_charters.py`,
  `tests/test_agents.py` and `tests/test_tone.py`; all pass (the "reviewer ladder" anchor
  stays exactly once).

## Phase 4: gh pr create names pr raise (User Story 3, P2)

- [X] T008 [US3] In `tests/test_pr_guards.py`, after
  `test_create_from_the_workspace_root_names_a_recorded_branch`, add
  `test_create_for_a_recorded_item_warns_naming_pr_raise(item, capsys, command)`,
  parametrized on that test's three commands: the result is `(0, '')` and stderr contains
  `warning: DIV-1 is a WUWEI item`, `bin/wuwei pr raise example/project` and
  `--item DIV-1` (US3 scenario 1). Run it; it fails (stderr is empty).
- [X] T009 [US3] In `tests/test_pr_guards.py`, add
  `test_create_for_a_recorded_item_is_refused_under_strict(item)`: append
  `[security]\nposture = "strict"\n` to `.wuwei/config.toml`;
  `guard().check(payload(root, 'cd worktrees/DIV-1 && gh pr create -r alice', cwd=root))`
  returns exit 1 with a reason starting `pr raise: DIV-1 is a WUWEI item` and containing
  `--item DIV-1` (US3 scenario 2). Run it; it fails (exit 0).
- [X] T010 [US3] In `tests/test_pr_guards.py`, add
  `test_create_without_an_unlinked_item_keeps_todays_result(item, case, capsys)`: record
  `pr = 'example/project#5'` on `DIV-1` (`state._write_state`, `reserved=False`); the same
  command from `cwd=root` returns `(0, '')` with no `pr raise` in stderr. Then the `case`
  command `gh pr create -r alice` from `root / 'repo'` (no recorded item) returns
  `(0, '')` with no `warning:` in stderr (US3 scenario 3, FR-008). Run it; it passes
  today. It is a guard against the change, not a red test.
- [X] T011 [US3] In `cli/wuwei/guards/pr.py`, add `import sys` and the #783 block in
  `create_check` (plan, Design 4). Run T008, T009, T010 and the whole of
  `tests/test_pr_guards.py`; all pass, including
  `test_create_from_the_workspace_root_names_a_recorded_branch` unchanged.

## Phase 5: Docs and polish

- [X] T012 [P] Update `docs/specs/2026-09-24-wuwei-design.md` (the 4.1 `gh pr create` row
  and the 5.3 paragraph after "(#666)"), `docs/site/daily.md` (steps 5 and 6) and
  `docs/site/reference.md` (posture paragraph) per plan, Design 6. Run
  `tests/test_docs.py` and `tests/test_tone.py`; both pass.
- [X] T013 Run the changed test files (`tests/test_dispatch.py`,
  `tests/test_parallel_dispatch.py`, `tests/test_next.py`, `tests/test_build_next.py`,
  `tests/test_pr_guards.py`, `tests/test_charters.py`, `tests/test_agents.py`,
  `tests/test_hooks.py`, `tests/test_invariants.py`, `tests/test_docs.py`,
  `tests/test_tone.py`); all pass.
- [X] T014 Check every changed file for em-dashes, emojis and absolute local paths; remove
  any.

## Dependencies

- T001 and T002 before T003; T003 before T004 and T005.
- T006 before T007.
- T008, T009 and T010 before T011.
- T012 after T003, T007 and T011 (it describes their behaviour).
- T013 and T014 last.
