# Tasks: gate briefs carry the owner's approval wording

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real tool: brief tests use the `day` fixture and fakes of
`tests/test_brief.py`, plan tests the `root` fixtures of `tests/test_plan.py` and
`tests/test_intraday_intake.py`. Run only the touched test files after each pair, then the full
suite (`python -m pytest -q`).

## Phase 1: the record (FR-001, FR-002, FR-003, FR-006, US2)

- [X] T001 Test in `tests/test_plan.py`, beside `test_approve_selected_items_and_reserve_gate_fields`:
  `plan.approve(['A'], root, goals_confirmed=True, note='  keep it\n small ')` records
  `items.A.approved_as == f'{scope}; owner: "keep it small"'` where `scope` is the proposal
  candidate's scope flattened to one line; without `note` it is the scope alone; an imported
  carry-over item keeps the earlier day's value (or none) and never gets the note. Through
  `main(['plan', 'approve', '--items', 'A', '--goals-confirmed', '--note', 'x'])` the value
  ends in `owner: "x"`. Fails: `approve` takes no `note`, the CLI no `--note`.
- [X] T002 Test in `tests/test_intraday_intake.py`, beside
  `test_plan_add_admits_owner_named_item_under_a_goal`: `plan.add('OWN-1', root, goal='G-1',
  note='only the annotator change')` records `approved_as == 'owner: "only the annotator change"'`;
  `plan.add('OWN-2', root, goal='G-1')` and a discovery candidate added without a note record no
  `approved_as` key; a second `plan.add('OWN-1', root, goal='G-1', note='more')` raises
  `state.StateError` matching `decision template` and leaves the value unchanged; through `main`,
  `plan add OWN-3 --goal G-1 --note x` records it. Fails: `add` takes no `note`.
- [X] T003 Test in `tests/test_state.py`, beside the reserved item field tests (line 247):
  `state.set_state('items.A.approved_as', 'x', root)` raises `StateError` matching
  `reserved; written by wuwei plan approve or wuwei plan add`. Fails: the message names
  `its dedicated command`.
- [X] T004 Implement `_approval` and the `note` parameters in `cli/wuwei/plan.py` (`approve` item
  dict at line 444; `add` existing-item refusal at line 478 and `admit` at line 557), the two
  `--note` arguments and pass-throughs in `cli/wuwei/commands/plan.py`, and the `approved_as`
  producer entry in `cli/wuwei/state.py` `_producer_error`.

## Phase 2: every builder and gate brief quotes it (FR-004, US1)

- [X] T005 Test in `tests/test_brief.py`, beside `test_builder_and_gate_briefs_name_the_live_read`
  and reusing `docs_brief`: with `items.X.approved_as = 'owner: "only the annotator change"'`,
  parametrized over `('builder', 1), ('arch', 1), ('quality', 1), ('security', 1), ('goal', 1),
  ('steward', 0)`, the header (text before the first blank line) contains exactly `count` lines
  equal to `Approved as: owner: "only the annotator change"`; a second gate brief for the same
  item (a delta, new seat name) carries it too; with no `approved_as` no line starts with
  `Approved as:`. Fails: no such header line.
- [X] T006 Test the issue's acceptance end to end in `tests/test_brief.py`: an item admitted with
  `plan.add(..., goal=..., note=...)` (the T004 producer, no direct state write), moved to phase
  `gate` with `state._write_state(..., reserved=False)`, then `brief` for `arch`, `quality` and
  `security` with `--gate --worktree tree`: every written brief contains the note under
  `Approved as:`. Fails until T007.
- [X] T007 Implement the `Approved as:` header line in `cli/wuwei/brief.py` `write`, inside the
  `if role == 'builder' or gate:` block at line 525.

## Phase 3: why shows the record (FR-005, US2)

- [X] T008 Test in `tests/test_why.py`: on `merged_item(root)` with
  `items.fix-login.approved_as = 'owner: "login only"'` written through
  `state._write_state(..., reserved=False)`, `why fix-login` prints `BRIEF` with
  `approved as: owner: "login only"` inserted right after the queued line; `why fix-login --full`
  ends that line with `(event not recorded; .wuwei/days/<DAY>/state.json)`; `why fix-login --json`
  has the line in `steps`; an item carried over two days prints it once. The existing
  `test_item_chain_lists_every_recorded_step` stays unchanged and green. Fails: no such step.
- [X] T009 Implement the `approved` group in `cli/wuwei/commands/why.py` (`GROUPS` at line 16, the
  step from the latest day's row after line 211).

## Phase 4: charters, skill, docs (FR-007, US3)

- [X] T010 Test in `tests/test_charters.py`: `agents/sentinel-arch.md`, `sentinel-quality.md`,
  `sentinel-security.md` and `sentinel-goal.md` each contain `Approved as:` and `scope`;
  `agents/planner.md` and `skills/wuwei-plan/SKILL.md` contain `--note`; `docs/site/daily.md`
  contains `Approved as:`. Fails: none of them do.
- [X] T011 Edit `charters/_common.md` rule 7 (the one sentence, version 1.10.0),
  `charters/planner.md` rule 3 (the `--note` form and the approve sentence, minor version bump),
  `skills/wuwei-plan/SKILL.md` line 20 and `docs/site/daily.md` (lines 208 and 235), keeping
  `wuwei plan add <item> --goal G-n` as a substring; then run `bin/wuwei agents build` to
  regenerate `agents/*.md`. `tests/test_agents.py`, `tests/test_charters.py` (one-home rule) and
  `tests/test_intraday_intake.py::test_plan_skill_and_charter_say_how_an_item_joins_an_approved_plan`
  pass.

## Phase 5: finish

- [X] T012 Run the full suite (`python -m pytest -q`); check every file written for em-dashes,
  emojis and absolute local paths.
