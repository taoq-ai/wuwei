# Tasks: quoted owner mentions are data, lead goals in either shape, question lint warns outside strict

**Input**: `specs/471-gate-shapes/` (spec.md, plan.md)

Test first, always: write each test task, run it with the command given, and see it fail
for the expected reason before its implementation task starts. Run from the repository
root with the interpreter your task names. Tests build workspaces under `tmp_path`, reuse
the existing fixtures (`places` in `tests/test_owner_actions.py`, `empty` and `lead()` in
`tests/test_plan.py`, `ws` and `question_payload` in `tests/test_decision.py`,
`fakes.integrity.seed` for hook-level runs under `guarded`), use neutral text and need no
network. No absolute local paths, emojis or em-dashes in any file. Do not touch
`cli/wuwei/shell.py`.

## Phase 1: US1, a mention of an owner command in data is data

- [X] T001 Test, `tests/test_owner_actions.py`: `test_owner_mentions_in_data_pass`
  parametrized over, with `{out}` the `outside` directory of `places`:
  `jq '.sweep.ranking = "wuwei rank exit 2: ... bin/wuwei goals edit ..."' lead.json > {out}/lead.ranked.json`,
  `echo 'run bin/wuwei goals edit later' > {out}/note.txt`, and
  `cat <<'EOF' > {out}/x.txt` / `bin/wuwei goals edit` / `EOF`: each `bash(root, ...)`
  returns `(0, '')`. Add `test_owner_mentions_in_data_leave_no_event`: the first two
  through the `hook()` helper inside the workspace exit 0, and the day's events hold no
  `hook.refusal` or `guard.would_refuse`. Flip the `test_regression_list` row
  `("echo 'bin/wuwei decision outcome' > notes.md", 2)` to `0` with a `#471` comment. Run
  `python -m pytest -q tests/test_owner_actions.py -k "data or regression"` (fails:
  `Opaque owner action`).
- [X] T002 Test, `tests/test_owner_actions.py`: `test_owner_commands_beside_data_stay_refused`
  with a seat payload (`agent_id` set): `bin/wuwei goals edit`, `sh -c 'bin/wuwei goals edit'`,
  `xargs bin/wuwei goals edit` give exit 1; `echo 'exec bin/wuwei goals edit' > x.tcl; tclsh x.tcl`
  and `cat <<'EOF' | tclsh` / `exec bin/wuwei goals edit` / `EOF` give exit 2. Run
  `python -m pytest -q tests/test_owner_actions.py -k beside_data` (passes on main; it is
  the guard rail for T003, keep it green).
- [X] T003 Implement plan Design 1 in `cli/wuwei/guards/protect_state.py` `_owner_action`:
  import `reads` from `wuwei.shell`, `readers` uses `_READERS` or `reads(c.argv, cwd)`,
  line 196 uses `readers[index]`, line 235 adds `and not all(readers)` with a one-line
  comment, and refresh the `_READERS` comment. Rerun T001 and T002; then
  `python -m pytest -q tests/test_owner_actions.py tests/test_protect_state.py tests/test_launcher_relevance.py tests/test_owner_edits.py`;
  all pass.

## Phase 2: US2, lead goals in either shape

- [X] T004 Test, `tests/test_goals_rank.py`: `test_proposed_refuses_ids_only` (template text,
  `['G-1']`, and `[LEAD_GOALS[0], 'G-2']`: `ValueError` whose message is
  `the lead JSON names G-1 without its block; have the lead write goals as blocks (outcome, measure, target, date, priority), or run /wuwei:wuwei-plan again`,
  resp. names `G-2`); `test_rank_lead_json_ids_only` (template `goals.md`, a lead JSON
  dict with `"goals": ["G-1"]` and one candidate citing `G-1`: `main(['rank', path]) == 2`,
  stderr starts `wuwei rank: the lead JSON names G-1 without its block;`, and `host
  terminal` is not in it); and extend `test_shipped_goals_guide_fails_only_for_having_no_goals`
  to assert the `no goals` message contains `run /wuwei:wuwei-plan again` and not
  `host terminal`. Run `python -m pytest -q tests/test_goals_rank.py -k "ids_only or no_goals"`
  (fails: old `no goals ... host terminal` reason).
- [X] T005 Test, `tests/test_plan.py`: `test_propose_refuses_ids_only_goals` (`empty`
  fixture, `{**proposal(), 'goals': ['G-1']}`: `plan.propose` raises `ValueError` matching
  `the lead JSON names G-1 without its block`; no `days/<date>/plan.md` written). Run
  `python -m pytest -q tests/test_plan.py -k ids_only` (fails: `no goals`).
- [X] T006 Test, `tests/test_owner_records_lint.py`: in
  `test_lint_catches_planted_instruction` assert
  `hits(planted, 'goals line 1: no goals; the owner fixes memory/goals.md with bin/wuwei goals edit in a host terminal')`
  is reported. Run `python -m pytest -q tests/test_owner_records_lint.py` (fails: no
  pattern for it).
- [X] T007 Add `\bowner fixes memory/` to `PATTERN` in `tests/test_owner_records_lint.py`.
  Rerun T006: the planted test passes and `test_no_owner_hand_edit_instructions` now fails
  on the 8 `cli/wuwei/goals.py` reasons (the red state T008 fixes).
- [X] T008 Implement plan Design 2 in `cli/wuwei/goals.py`: replace the host-terminal tail
  in all 8 `parse` reasons inline, and add the ids-only raise in `proposed`. Rerun T004 to
  T007, then `python -m pytest -q tests/test_goals_rank.py tests/test_plan.py tests/test_owner_records_lint.py tests/test_reasons.py tests/test_owner_edits.py`;
  all pass.

## Phase 3: US3, the question lint warns outside strict

- [X] T009 Test, `tests/test_decision.py`: `test_morning_gate_without_plan_names_plan_propose`
  (`ws`, no plan file; question `Morning gate (days/2026-09-28/plan.md): Record the goals?`
  with header `Goals`: `check_question` returns
  `(1, 'Morning gate questions cite days/2026-09-28/plan.md; run bin/wuwei plan propose <lead.json> first')`;
  with the plan file present and a question marked `Morning gate` that does not cite it,
  the message is `Morning gate questions cite days/2026-09-28/plan.md` alone; a plain
  `Choose?` keeps today's hint). Run `python -m pytest -q tests/test_decision.py -k morning_gate_without_plan`
  (fails: generic hint).
- [X] T010 Implement plan Design 5 in `cli/wuwei/guards/decision.py` (`_morning` helper
  shared by `gate_question` and `check_question`, the new reason). Rerun T009 and all of
  `tests/test_decision.py`; passes.
- [X] T011 Test, `tests/test_posture.py`: extend `test_guard_areas_table` with
  `guards.level(stub('decision', 'check_question'), GUARDED)[1:3] == ('outward', 'warn')`,
  the same under `OBSERVE`, `'block'` under strict levels, and
  `guards.level(stub('decision', 'check_write'), GUARDED)[:3] == ('decision', 'records', 'block')`.
  Add hook-level tests in `tests/test_decision.py`: `test_gate_question_before_plan_warns_under_guarded`
  (`ws` seeded with `fakes.integrity.seed`, default posture, the T009 question through
  `main(['hook', 'PreToolUse'])` with `session_id`, `transcript_path`, `hook_event_name`:
  exit 0, no `deny` output, and exactly one `guard.would_refuse` event with `guard`
  `decision`, `area` `outward` and `plan propose` in its `reason`), and
  `test_gate_question_before_plan_refused_under_strict` (`[security]\nposture = "strict"`:
  exit 2, `permissionDecision` `deny`, reason contains `plan propose`). Move
  `test_question_hook_exit_two` to strict (it asserts the deny path) if it starts passing
  for the wrong reason or fails. Run
  `python -m pytest -q tests/test_posture.py tests/test_decision.py -k "areas or before_plan or hook_exit_two"`
  (fails: records floor blocks).
- [X] T012 Implement plan Design 4: add `'decision.check_question': 'outward'` to `AREAS` in
  `cli/wuwei/guards/__init__.py`. Rerun T011, then
  `python -m pytest -q tests/test_posture.py tests/test_decision.py tests/test_hooks.py tests/test_telemetry.py tests/test_guard_mutation.py tests/test_control_plane.py`;
  all pass.

## Phase 4: text

- [X] T013 Test, `tests/test_docs.py`: `test_lead_goals_are_blocks_while_proposing` asserts
  `never an id alone` appears in `charters/lead.md`, `agents/lead.md` and
  `skills/wuwei-plan/SKILL.md`, and that the `outward` row of the `docs/site/security.md`
  posture table names `decision.check_question`. Run
  `python -m pytest -q tests/test_docs.py -k blocks_while_proposing` (fails).
- [X] T014 Edit `charters/lead.md` step 3 and `skills/wuwei-plan/SKILL.md` step 2 (plan
  Design 6), regenerate with `bin/wuwei agents build`, and update the `outward` row in
  `docs/site/security.md` and in the section 9 posture table of
  `docs/specs/2026-09-24-wuwei-design.md`. Rerun T013 and
  `python -m pytest -q tests/test_docs.py tests/test_agents.py tests/test_owner_records_lint.py`;
  all pass.

## Phase 5: finish

- [X] T015 Run the full suite, `python -m pytest -q`; everything passes. Rerun the spec's
  probe table (SC-001 to SC-003) in a scratch workspace. Check every file you wrote for
  em-dashes, emojis and absolute local paths, and record anything found at build time under
  the spec's Assumptions.
