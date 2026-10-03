# Tasks: one approval at the morning gate, and no second interview on the first day

**Input**: `specs/365-one-gate-question/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, and see it fail for
the expected reason before its implementation task starts. Run from the repository root with
the interpreter your task names. Neutral names only (`acme/widget`, `acme/gadget`). No
absolute local paths, emojis or em-dashes in any file.

## Phase 1: US1, the first day asks the interview once

- [X] T001 Test, `tests/test_interview.py`: `test_questions_skip_recorded_answers` with the
  `offline` fixture. (a) No answer file: `main('calibrate', '--questions') == 0` and the
  widget ids are every row for both repositories (as today). (b) Write `DAY/interview.json`
  with `merge` for `acme/widget` only and `phone`: output has no `phone`, no
  (`merge`, `acme/widget`), still (`merge`, `acme/gadget`), and every other pair in table
  order. (c) Write `.wuwei/days/2026-09-30/interview.json` and
  `.wuwei/archive/2026-09-01/interview.json` that together answer every row (repo rows for
  both repositories, first choice label), with no file today: output is exactly `[]`, exit
  0. (d) Same full answers in `DAY/interview.json` alone: `[]`. Run
  `python -m pytest -q tests/test_interview.py -k questions_skip` (fails: every widget is
  still printed).
- [X] T002 Test, `tests/test_interview.py`: `test_questions_refuse_unreadable_answers`
  parametrized over a file that is not JSON, a JSON list, and a symlink to a valid answer
  file, each at `.wuwei/days/2026-09-30/interview.json`: `main('calibrate', '--questions')
  == 2`, stderr contains `days/2026-09-30/interview.json`, stdout is empty. Run
  `python -m pytest -q tests/test_interview.py -k questions_refuse` (fails: exit 0 with the
  full list).
- [X] T003 Implement `_recorded(root)` and the `widgets` filter in `cli/wuwei/interview.py`
  (plan Design 1). Rerun T001 and T002; pass. Run `python -m pytest -q
  tests/test_interview.py`; all pass, including
  `test_widgets_come_from_the_table_and_pass_the_question_guard`.
- [X] T004 Test, `tests/test_setup.py`: `test_shadow_records_posture_answer` parametrized
  over `shadow` True and False: `run_setup(Confirm(), shadow=shadow) == 0`; today's
  `DAY/interview.json` has `posture == 'Observe'` when `shadow`, and no `posture` key
  otherwise (the `terminal` fake never answers it); with `shadow`, the loaded config still
  has `security.posture == 'observe'`. Run `python -m pytest -q tests/test_setup.py -k
  shadow_records_posture` (fails: no `posture` key under shadow).
- [X] T005 Implement the `--shadow` posture answer in `cli/wuwei/commands/setup.py`
  (plan Design 2). Rerun T004; pass. Run `python -m pytest -q tests/test_setup.py`; all
  pass.

## Phase 2: US2 and US3, one gate question, its docs and the eval case

- [X] T006 Test, `tests/test_docs.py`: `test_one_gate_question`. (a) In
  `skills/wuwei-plan/SKILL.md`, the line starting `4. ` contains
  `Approve today's plan as proposed?`, `` `Change something` ``, `` header `Goals` ``,
  `` `Plan` ``, `calibrate --questions` and `` `[]` ``; it contains neither
  `one AskUserQuestion per decision` nor `Ask separately`; the text after
  ``Only on `Change something` `` (split once on that phrase) contains `goals`, `queue`,
  `seat policy`, `CAP`, `envelope` and `carry-over`. The line starting `5. ` contains
  `--import-yesterday` and `carry-over`. (b) `charters/planner.md` contains
  `Approve today's plan as proposed?` and `Change something`. (c) `docs/site/daily.md`
  section `## 3. Plan and the morning gate` contains `Approve today's plan as proposed?` and
  `Change something` and not `question per decision`; `docs/site/agent.md` line starting
  `3. Morning gate` contains `Approve today's plan as proposed?` and not `per decision`.
  (d) The `## Owner interview` section of `docs/site/configuration.md` contains `` `[]` ``.
  (e) `evals/wuwei-plan-positive-06/prompt.md` exists and its body mentions `once`. Run
  `python -m pytest -q tests/test_docs.py -k one_gate_question` (fails: phrase missing).
- [X] T007 Edit `skills/wuwei-plan/SKILL.md` steps 4 and 5 (plan Design 3). Rerun T006 (a)
  part passes. Run `python -m pytest -q tests/test_docs.py tests/test_charters.py`; the
  existing skill-phrase tests still pass.
- [X] T008 Edit `charters/planner.md` (plan Design 4). Run `python -m pytest -q
  tests/test_agents.py -k checked_in` and see it fail with drift (the failing test for this
  task). Run `bin/wuwei agents build` from the repository root; only `agents/planner.md`
  changes. Rerun `tests/test_agents.py`; pass.
- [X] T009 Edit `docs/site/daily.md`, `docs/site/agent.md` and `docs/site/configuration.md`
  (plan Design 5). Rerun T006 (c) and (d) parts; pass.
- [X] T010 Add `evals/wuwei-plan-positive-06/prompt.md` and `graders/skill.md` (plan Design
  7). Rerun T006; pass. Run `python -m pytest -q tests/test_skill_evals.py`; pass.
- [X] T011 Test, `tests/test_next.py`: in `test_morning_rows`, after the existing gate
  assertions, assert `"Approve today's plan as proposed?"` is in `found['step']`. Run
  `python -m pytest -q tests/test_next.py -k morning_rows` (fails: phrase missing).
- [X] T012 Edit the `gate` row in `cli/wuwei/commands/next.py` (plan Design 6). Rerun T011;
  pass. Run `python -m pytest -q tests/test_next.py`; all pass, including the SessionStart
  budget test.

- [X] T014 Test, `tests/test_plan.py`: `test_gate_widget_is_the_one_approval_question`
  pins the question, the `Plan`/`Goals` header switch, both options, the Approve
  description and the `record` command with and without `--import-yesterday`;
  `test_cli_propose_and_approve` runs `wuwei plan gate`. Run `python -m pytest -q
  tests/test_plan.py -k gate_widget` (fails: no `gate_widget`).
- [X] T015 Implement `plan.gate_widget` in `cli/wuwei/plan.py` and the `plan gate` action
  in `cli/wuwei/commands/plan.py`; rerun T014; pass.
- [X] T016 Extend `test_one_gate_question` with `` `wuwei plan gate` `` and
  `` `record` command `` in step 4; edit `skills/wuwei-plan/SKILL.md` steps 4 and 5 to ask
  the printed widget unchanged and run its `record` command on Approve.

## Phase 3: Polish

- [X] T013 Run the full suite, `python -m pytest -q`, from the repository root; everything
  passes. Grep every file this feature touched for the em-dash character and for emojis and
  remove any. Confirm no absolute local path was written.
