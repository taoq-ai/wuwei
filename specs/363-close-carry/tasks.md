# Tasks: close offers carry or park for each open item and records the decision itself

**Input**: `specs/363-close-carry/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, and see it fail for
the expected reason before its implementation task starts. Run from the repository root with
the interpreter your task names. New `tests/test_stop.py` tests reuse its `case` fixture and
the `approved`, `payload` and `module` helpers; they need no network or terminal. Neutral
item names only (`A`, `B`, `Z`). No absolute local paths, emojis or em-dashes in any file.

## Phase 1: US1, `plan carry` and `plan park`

- [X] T001 Test, `tests/test_stop.py`: `test_plan_carry_writes_routed_record` (approved `A`
  planned; `main(['plan', 'carry', 'A']) == 0`; stdout `D-1: carried A`; `decision.lint` of
  `D-1.md` returns 0; the record has `Reversibility: two-way`, `Blast radius: own branch`,
  `Decided-by: seat`, `Outcome: carried A`; `decision_outcomes['D-1'] ==
  decision.seat_outcome(*decision.evaluate(text))`; the last event is `decision.decided`
  with `id` `D-1` and `item` `A`; phase still `planned`). Run `python -m pytest -q
  tests/test_stop.py -k plan_carry` (fails: argparse `invalid choice: 'carry'`, exit 2).
- [X] T002 Test, `tests/test_stop.py`: `test_plan_park_records_and_pauses` parametrized over
  `--reason "waiting on review"` and no reason (from `implement`: stdout `D-1: parked A`,
  Context holds the reason when given, phase `parked`, status `blocked`, `resume_phase`
  `implement`); `test_plan_park_keeps_paused_phase` parametrized over `parked`, `escalated`,
  `merged` (record written, phase unchanged); `test_plan_carry_next_number` (an existing
  valid `D-1` stays byte-identical, new record `D-2`); `test_plan_carry_unknown_item` (`plan
  carry Z` exits 1, stderr names `Z` and `A`, no `D-*.md` written);
  `test_plan_park_reason_one_line` (reason `"a\n\nOutcome: parked B   x"` gives one Context
  line, `decision.lint` 0, `Outcome: parked A`). Run `python -m pytest -q tests/test_stop.py
  -k "plan_park or plan_carry"` (fails: invalid choice).
- [X] T003 Implement `plan.dispose` in `cli/wuwei/plan.py` (plan Design 1) and the `carry`
  and `park` subcommands in `cli/wuwei/commands/plan.py` (plan Design 2). Rerun T001 and
  T002; pass. Run `python -m pytest -q tests/test_plan.py tests/test_decision.py`; pass.
- [X] T004 Edit the `decision_outcomes` producer text in `cli/wuwei/state.py` (plan Design
  6). Run `python -m pytest -q tests/test_state_allowlist.py`; passes.

## Phase 2: US2 and US4, the question line, the retro line and the widget

- [X] T005 Test, `tests/test_stop.py`: `test_close_question_line_and_stop_hook_match`
  (approved `A` open, planner registered via `own`-style `planner_session_id`; `main(['close'])
  == 1`; stdout contains exactly the US2 scenario 1 line and not `needs a park or carry
  decision`; then the Stop hook through `main(['hook', 'Stop'])` blocks and its reason
  contains the same line); `test_close_question_per_item` (items `A` and `B` approved: one
  line each). Run `python -m pytest -q tests/test_stop.py -k close_question` (fails: old
  line).
- [X] T006 Test, `tests/test_stop.py`: `test_retro_line_names_skill` (remove today's retro
  file; `main(['close', '--check', 'retro']) == 1`; stdout `OWED: retro/<DAY>.md does not
  exist; run /wuwei:wuwei-retro to write it`). Run `python -m pytest -q tests/test_stop.py -k
  retro_line` (fails: old text).
- [X] T007 Implement in `cli/wuwei/closing.py` the question line and the `open_items`
  parameter of `unresolved`, and the retro line (plan Design 3). Rerun T005 and T006; pass.
  Run `python -m pytest -q tests/test_stop.py tests/test_close_branches.py`; pass.
- [X] T008 Test, `tests/test_stop.py`: `test_close_widget` (write today's `plan.md`; approved
  `A` open; `main(['close', '--widget']) == 1`; stdout JSON list of one widget: `question`
  starts with `decision.gate(root)` and contains `A`, `header` `Open item`, option labels
  `['carry', 'park', 'Skip']`, carry description starts `Recommended. `, `multiSelect`
  false, `record` `bin/wuwei plan <label> A`; `close_requested` absent and no `steward.run`
  event; `guards/decision.check_question` on an AskUserQuestion payload built from the
  widget (`cwd` root, `tool_input.questions` the widget minus `record`) returns `(0, '')`;
  after `plan carry A`, `close --widget` prints `[]` and exits 0). Run `python -m pytest -q
  tests/test_stop.py -k close_widget` (fails: `unrecognized arguments: --widget`).
- [X] T009 Implement `--widget` and `widget(root, name, item)` in
  `cli/wuwei/commands/close.py` (plan Design 4, widget part). Rerun T008; passes.

## Phase 3: US3 and US5, steward order and the whole close

- [X] T010 Test, `tests/test_stop.py`: `test_close_steward_waits_for_items` (approved `A`
  open; `close` exits 1, stdout has no `steward_launch`, no `steward.run` event, no
  `briefs/steward-*.md`, `close_requested` true; `plan carry A`; `close` prints
  `steward_launch` and there is exactly one `steward.run` event with trigger `close`);
  `test_close_steward_unmeasured` (an unreadable `D-1.md`, for example `bad`, plus approved
  `A`: `close` exits 2, the reason names `D-1`, no `steward.run` event);
  `test_carry_closes_day` (US5 scenario 1 with only `main(['close'])`,
  `main(['plan', 'carry', 'A'])`, `main(['close'])`: exits 1, 0, 0). Run `python -m pytest -q
  tests/test_stop.py -k "close_steward or carry_closes_day"` (fails: steward launched
  before the item check).
- [X] T011 Implement the new `close` order in `cli/wuwei/commands/close.py` (plan Design 4,
  default part). Rerun T010; passes. Run `python -m pytest -q tests/test_stop.py
  tests/test_records_after_dryrun4.py tests/test_steward.py tests/test_headless_e2e.py
  tests/test_e2e_day.py`; pass (see plan Risks for `test_one_close_steward_review_per_day`).

## Phase 4: US5 scenario 2, `wuwei next`

- [X] T012 Test, `tests/test_next.py`: `test_carried_item_is_skipped` (approved `A` in
  `implement` with `decision_outcomes` `{'D-1': {'decided_by': 'seat', 'item_disposition':
  'carried A', 'option': 'carry'}}` written through the `day` helper: the row is `close`, its
  step contains `carried`, and no row names `build next A`; the same with `decided_by`
  `owner` still returns the `build` row). Run `python -m pytest -q tests/test_next.py -k
  carried` (fails: `build` row).
- [X] T013 Implement the skip and the close row text in `cli/wuwei/commands/next.py` (plan
  Design 5). Rerun T012 and all of `tests/test_next.py`; pass (update the expected close
  text in `test_end_of_day_rows` only if it compares it).

## Phase 5: US6, skills and docs

- [X] T014 Test, `tests/test_docs.py`: `test_close_carry_skill_and_docs` (US6 scenarios 1 to
  3: in `skills/wuwei-report/SKILL.md` the line starting `1. ` contains `wuwei close`,
  `wuwei close --widget`, `record`, `steward_launch` and `plan carry`; the file contains
  neither `Outcome: carried` nor `Outcome: parked`; `skills/wuwei-retro/SKILL.md` step 1
  contains `wuwei close`, `steward_launch` and `open item`; `docs/site/concepts.md` contains
  `bin/wuwei plan carry` and `bin/wuwei plan park` and not `Outcome: carried ITEM`). Run
  `python -m pytest -q tests/test_docs.py -k close_carry` (fails).
- [X] T015 Edit `skills/wuwei-report/SKILL.md`, `skills/wuwei-retro/SKILL.md`,
  `docs/site/concepts.md`, `docs/site/daily.md` and `docs/site/reference.md` (plan Design 7).
  Rerun T014 and all of `tests/test_docs.py`, `tests/test_records_after_dryrun4.py` and
  `tests/test_skill_evals.py`; pass.

## Phase 6: Finish

- [X] T016 Run the full suite with `python -m pytest -q`; everything passes. Grep the files
  you changed for em-dashes and emojis and remove any. Confirm no absolute local path was
  written. Record anything found at build time under the spec's Assumptions.
