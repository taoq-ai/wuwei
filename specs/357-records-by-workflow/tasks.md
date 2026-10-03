# Tasks: the workflow writes its own records

**Input**: `specs/357-records-by-workflow/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, and see it fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. Tests build workspaces under `tmp_path`, set
`WUWEI_WORKSPACE` and `WUWEI_NOW`, use neutral goal text, and need no network or terminal.
No absolute local paths, emojis or em-dashes in any file.

Before T001, check whether #354 (`wuwei decide`, the `mcp decide <D-n> <option>` form and
its session allowance) is on main. If it is, reuse its allowance helper for T010 instead
of `_gate_edits`, leave `PENDING_354` out of T016, and note it under the spec's
Assumptions.

## Phase 1: US1, provisional goals

- [X] T001 Test, `tests/test_goals_rank.py`: `test_proposed_renders_lead_goals_on_template`
  (template text plus two goal objects returns provisional text that `goals.parse` reads
  as `G-1`, `G-2`), `test_proposed_keeps_defined_goals` (a `goals.md` with `## G-1`
  returns it unchanged, `False`), and `test_proposed_refuses_bad_objects` (missing field,
  unknown key, bad date, `bool` priority, a value containing `\n## G-9`: each raises
  `ValueError` starting `proposed goals`). Run `python -m pytest -q tests/test_goals_rank.py
  -k proposed` (fails: no `goals.proposed`).
- [X] T002 Implement `goals.defined` and `goals.proposed` in `cli/wuwei/goals.py`
  (plan Design 1). Rerun T001; passes.
- [X] T003 Test, `tests/test_plan.py`: `test_propose_runs_on_provisional_goals` (fixture
  with the template `goals.md`; lead JSON with two goal objects and candidate `A` citing
  `G-1`; `plan.propose` returns `plan.md` containing `G-1 (provisional)`, `G-2
  (provisional)` and the outcome text; `days/<date>/goals.md` parses to both ids;
  `proposal.json` `goals == ['G-1', 'G-2']`; `memory/goals.md` unchanged),
  `test_propose_refuses_goal_objects_once_goals_exist` (default fixture: exits with
  `goals must cite identifiers`), `test_repropose_on_confirmed_goals_removes_draft`, and
  `test_approve_needs_recorded_goals` (after a provisional propose, `plan.approve(['A'],
  goals_confirmed=True)` raises `ValueError` `no goals`). Plus a CLI case in
  `test_cli_propose_and_approve` style: `wuwei plan propose lead.json` exits 0. Run
  `python -m pytest -q tests/test_plan.py -k "provisional or goal_objects or draft or
  recorded_goals"` (fails: `no goals`).
- [X] T004 Implement the provisional path in `cli/wuwei/plan.py` `propose` (plan Design
  2). Rerun T003 and all of `tests/test_plan.py`; passes.
- [X] T005 Test, `tests/test_goals_rank.py`: `test_rank_lead_json_on_provisional_goals`
  (template `goals.md`, lead JSON with goal objects, `wuwei rank lead.json` exits 0 and
  prints candidate `A`). Run it (fails: exit 2 `no goals`).
- [X] T006 Implement in `cli/wuwei/commands/rank.py` `run` (plan Design 3). Rerun T005 and
  `tests/test_goals_rank.py`; passes.
- [X] T007 Test, `tests/test_plan.py`: `test_template_proposes_goal_on_empty_goals`
  (template `goals.md`: `wuwei plan template` exits 0, its `goals[0]` is a goal object,
  and piping it to `wuwei plan propose -` exits 0). Run it (fails: exit 2).
- [X] T008 Implement in `cli/wuwei/commands/plan.py` `template` (plan Design 4). Rerun
  T007; passes.

## Phase 2: US2, the planner records what the gate approved

- [X] T009 Test, `tests/test_decision.py`: `test_record_gate_notes_planner_topics`
  (planner `planner-1` registered with `plan.session`, today's `plan.md` present; a
  PostToolUse payload with one `Morning gate (days/<date>/plan.md): confirm goals G-1 and
  G-2?` question, header `Goals`, returns `(0, '')`, sets
  `state['sessions']['planner-1']['gate_asked'] == ['goals']` and appends one `gate.asked`
  event), `test_record_gate_ignores_seats_and_others` (`agent_id` present, another
  session id, a question without the plan citation, a non-gate question: no write), and
  `test_record_gate_voice_topic` (header `Voice` records `voice`; the topic comes from
  the header alone, never from the question text). Also extend
  `tests/test_hooks.py` expectations only if the MODULES pin needs it (it derives). Run
  `python -m pytest -q tests/test_decision.py -k record_gate` (fails: no `record_gate`).
- [X] T010 Implement `gate_question` (extracted, `check_question` uses it unchanged),
  `TOPICS`, `record_gate` and the new `GUARDS` row in `cli/wuwei/guards/decision.py`; set
  `MODULES['decision']['PostToolUse']` in `cli/wuwei/guards/__init__.py`; add
  `EVENT_PRODUCERS['gate.asked']` in `cli/wuwei/commands/event.py` and the `sessions`
  producer text in `cli/wuwei/state.py` (plan Design 5, 6, 8). Rerun T009,
  `tests/test_decision.py`, `tests/test_hooks.py`, `tests/test_interview.py`,
  `tests/test_control_plane.py`; pass.
- [X] T011 Test, `tests/test_owner_edits.py`: `test_planner_records_gate_approved_goals`
  parametrized over `observe` and `guarded` (plan Test approach: propose on provisional
  goals, register `planner-1`, `record_gate`, `check_bash` returns `(0, '')` for
  `bin/wuwei goals edit --file .wuwei/days/<date>/goals.md`, `cli(... 'goals', 'edit',
  '--file', draft)` exits 0, `memory/goals.md` equals the draft, `plan.approve(['A'],
  root, goals_confirmed=True)` succeeds); `test_strict_prints_host_terminal_command`
  (same under `strict`: `check_bash` returns 1, reason starts with today's owner-action
  reason and ends with `Run it in a host terminal: bin/wuwei goals edit --file
  .wuwei/days/<date>/goals.md`); `test_gate_allowance_needs_question_file_and_planner`
  (planner without a recorded topic: 1 with the host line; `goals edit` without `--file`:
  1; `voice edit --file` with only `goals` recorded: 1; same payload plus `agent_id`: the
  exact old reason; a different session id: the exact old reason; the call inside a
  `.sh` script: refused); `test_voice_edit_after_voice_gate` (topic `voice` recorded:
  `voice edit --file` returns 0); `test_queue_question_naming_a_goal_does_not_unlock_edit`
  (a header `Queue` gate question whose text names a goal and voice: both edits refused). Run `python -m pytest -q tests/test_owner_edits.py -k
  "gate or strict or voice_edit_after"` (fails: refused).
- [X] T012 Implement `_GATE_EDITS`, `_gate_edits`, the `edits` parameter of
  `_owner_action` and its use in `check_bash` in `cli/wuwei/guards/protect_state.py`
  (plan Design 7). Rerun T011 and all of `tests/test_owner_edits.py`,
  `tests/test_owner_actions.py`, `tests/test_protect_state.py`; pass, the existing seat
  refusal assertions unchanged.
- [X] T013 Test, `tests/test_protect_state.py`: a `Write` to `.wuwei/days/<date>/goals.md`
  returns 1 from `check_file`. Run it (fails: 0).
- [X] T014 Implement: add `'goals.md'` to the day-file tuple in `_protected_name` and
  replace `_STATE_HINT`'s owner sentence (plan Design 7). Rerun T013 and
  `tests/test_protect_state.py`; pass.

## Phase 3: US3, no owner-facing hand-edit text

- [X] T015 Test, `tests/test_owner_records_lint.py` (new, plan Design 9):
  `test_lint_catches_planted_instruction` and `test_no_owner_hand_edit_instructions`.
  Run `python -m pytest -q tests/test_owner_records_lint.py` (fails: lists at least the
  goals template line "replace this guide" with `templates/workspace/memory/goals.md:3`).
- [X] T016 Rewrite the texts the lint lists (plan Design 10): the goals template; add the
  two `ALLOWED` sentences and, if #354 is not on main, the `PENDING_354` sentences with
  their comment. Any other hit is rewritten to the command that records it, or, if it is a
  legitimate "you can edit later" or credentials mention, whitelisted by exact sentence
  with a one-line reason. Rerun T015; passes.
- [X] T017 Update the flow text with no new test beyond the existing doc tests (plan
  Design 10): design spec 5.2 paragraph and 5.7 sentence,
  `skills/wuwei-plan/SKILL.md` steps 2 and 4, `charters/lead.md` step 3 and regenerated
  `agents/lead.md` (`python3 -P -m wuwei agents build` with `PYTHONPATH=cli`),
  `docs/site/daily.md`, `docs/site/concepts.md`, `docs/site/configuration.md`,
  `docs/site/reference.md`. Run `python -m pytest -q tests/test_docs.py
  tests/test_agents.py tests/test_owner_records_lint.py`; pass.

## Phase 4: finish

- [X] T018 Run the full suite `python -m pytest -q`; everything passes. Grep the changed
  files for em-dashes, emojis and absolute local paths and remove any. Record anything
  found at build time under a "Found at build time" heading in the spec's Assumptions.
