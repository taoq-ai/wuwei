# Tasks: delete pace; the tier alone sets the process depth

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 221f1f2.

Run tests with `python3 -m pytest -q <files>` from the repository root; only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code.

## Phase 1: Dispatch derives tier and seats without pace (US1, P1)

- [X] T001 [US1] In `tests/test_dispatch.py` add `test_a_day_value_never_changes_the_tier`:
  `tiered(root, monkeypatch, [('cli/wuwei/report.py', 3, 1)], floor='standard')`, then
  `dispatch.tier(root, workspace.load_config(root), state.read_state(root)['items']['A'])`
  once as is and once after writing `pace: fast` into the day state
  (`state._write_state(..., reserved=False)`); assert the two records are equal, have no
  `depth` key and no reason starting with `pace`. Run it: red (fast writes `depth: light`).
- [X] T002 [US1] In `tests/test_process_depth.py::test_depth_reads_the_gate_tier_then_the_builder_prediction`
  add `assert depth({'gates': {'tier': 'standard', 'depth': 'light'}}, gate=True) == 'standard'`.
  Run: red.
- [X] T003 [US1] In `tests/test_parallel_dispatch.py` add
  `test_a_day_value_never_changes_cap_or_holds_a_launch` (model: the deleted
  `test_careful_plans_cap_minus_one` and `test_fast_on_a_saturated_host_holds_every_launch`):
  with `approved(day)` and `pace: careful` in the day state, `launch_set(day)` starts A to D
  as without it; with `pace: fast`, `os.getloadavg` at 34.0 and `os.cpu_count` 10, no entry
  is `wait`, `day.data['cap_bound'] != 'load'`, and `day.run('status', '--line')` has no
  `pace` and no `held by load`. Run: red.
- [X] T004 [US1] `cli/wuwei/dispatch.py`: remove the pace block from `tier`, the
  `gates.get('depth')` read from `depth`, and `pace.seats` and the hold from `launch_set`
  (plan.md). `cli/wuwei/calibrate.py`: drop `load` and `costs` from `host`.
  `cli/wuwei/commands/status.py`: drop the `pace` snapshot field and the `pace` and
  `held by load` tokens.
- [X] T005 [US1] `tests/test_calibrate.py:1373-1380`: drop the `pace` import; assert
  `(limits['cap'], limits['bound']) == (6, 'host.seats')` and `'load' not in limits`.
- [X] T006 [US1] Run `tests/test_dispatch.py tests/test_process_depth.py
  tests/test_parallel_dispatch.py tests/test_calibrate.py tests/test_signal_status.py`: green.

## Phase 2: The morning gate offers one approve option (US2, P1)

- [X] T007 [US2] In `tests/test_plan.py` change the gate assertions to one approve option and
  no `--pace`: `156`, `395`, `420`, `440` (labels `['Approve', 'Change something']`), `445`,
  `448`. Replace `test_propose_records_the_pace_advice_and_the_gate_offers_each_pace`,
  `test_approve_records_the_chosen_pace`, `test_approve_refuses_change_something_and_old_proposals_take_the_default`
  and `test_plan_set_pace` (and the `pace_events` helper) with
  `test_the_gate_records_no_day_value`: after `plan.propose`, `proposal.json` has no key
  starting with `pace` and `plan.md` no `Pace:`; after `plan.approve`, the day state has no
  `pace` and the `plan.approved` payload no `pace`, `recommended`, `wish`; `main([...,
  'approve', ..., '--pace', 'Approve'])`, `main(['plan', 'set', 'pace=fast'])` and
  `main(['pace'])` each raise `SystemExit` with code 2. Keep
  `test_candidate_paths_are_validated`; drop the `# #579` header comment. Run: red.
- [X] T008 [US2] `cli/wuwei/plan.py` (propose, gate_widget, approve, delete `set_pace`),
  `cli/wuwei/commands/plan.py` (no `--pace`, required `assignment`, no `pace=` branch),
  `cli/wuwei/guards/protect_state.py` (delete `_planner_pace_set`, narrow the allowance),
  `cli/wuwei/commands/next.py:57`.
- [X] T009 [US2] After T014 (the last importer goes there), delete `cli/wuwei/pace.py`, `cli/wuwei/commands/pace.py` and
  `tests/test_pace.py`; drop `pace` from `commands/__init__.py` `READ_ONLY` and the
  `__main__.py` owner group.
- [X] T010 [US2] Run `tests/test_plan.py tests/test_protect_state.py tests/test_cli.py
  tests/test_cli_known_command.py`: green.

## Phase 3: Checks are the configured fast checks (US3, P2)

- [X] T011 [US3] `tests/test_build_next.py`: delete
  `test_empty_fast_checks_at_careful_pace_still_run_the_tests`; in the none-configured test
  above it (ends at `519`) write `pace: careful` into the day state before
  `build.next_action` and keep the `commands == []` and `checks: none configured` asserts.
  Run: red.
- [X] T012 [US3] `tests/test_brief.py:623-640`: parametrize `checks,none` over
  `('[]', True)` and `('["make test"]', False)`; write `pace: careful` into the day state;
  assert the none line as before and `'Checks:' not in text`. Run: red.
- [X] T013 [US3] `tests/test_commit_push.py:906-912`: drop the pace parametrization and the
  state write (the test of the kept evidence guard stays).
- [X] T014 [US3] Delete `fast_checks.commands`; `fast_checks.record`, `build.start`,
  `build.check`, `commit_push.fast_evidence` and the builder brief read
  `repo['fast_checks']`; delete `brief.checks_line` (plan.md).
- [X] T015 [US3] Run `tests/test_build_next.py tests/test_brief.py tests/test_commit_push.py
  tests/test_fast_checks.py`: green.

## Phase 4: Nothing names pace (US4, P2)

- [X] T016 [US4] `tests/test_workspace.py`: drop `'pace': {'default': 'steady'}` from the
  defaults at `225`; add `test_retired_pace_keys_only_warn`: a guarded config with
  `[pace]\ndefault = "fast"\n` and a `[[repos]]` entry with `tests = "pytest"` loads, and
  `load_config(root, warnings=found)` names `pace` and `repos.0.tests` as unknown keys (match
  the existing warning text). Run: red.
- [X] T017 [US4] `tests/test_report_retro.py`: `47-49` assert `## Tickets seats filed` <
  DORA < `## Gate verdicts` and no `## Pace`; `318` drop `'## Pace'`; `332` assert DORA
  follows `## Cycle time` and `'## Pace' not in full`. Run: red.
- [X] T018 [US4] `cli/wuwei/workspace.py` (drop `repos.tests` and `pace`),
  `cli/wuwei/metrics.py` (cycles `pace` field, `by_pace`, `event_metrics['by_pace']`),
  `cli/wuwei/report.py` (`costly`, `pace_lines`, `## Pace`), `cli/wuwei/retro.py`
  (`## Pace`, pace card), `cli/wuwei/state.py:279`, `cli/wuwei/signal.py:32`,
  `cli/wuwei/commands/event.py:88`, `cli/wuwei/commands/setup.py:163-164`,
  `cli/wuwei/budget_classes.py:59`.
- [X] T019 [US4] `tests/test_signal_status.py:387` drop the two pace kinds;
  `tests/test_docs.py:26` drop the `Pace` glossary entry.
- [X] T020 [US4] `tests/test_invariants.py`: delete `pace_rule`, `i15`, `i16`, `green_rule`,
  `i17`, their `INVARIANTS` and `READS` entries and
  `test_a_pace_that_lowers_a_tier_is_caught`; keep `itertools` (still used). Skip if pass
  part 1 removed the walk.
- [X] T021 [US4] Docs: `docs/site/concepts.md`, `daily.md`, `reference.md`,
  `configuration.md`, `agent.md` and the design spec 5.2, 5.6 and 9.2 edits (plan.md).
- [X] T022 [US4] `charters/lead.md:13`, then `bin/wuwei agents build` to regenerate
  `agents/lead.md`.
- [X] T023 [US4] Run `tests/test_workspace.py tests/test_report_retro.py
  tests/test_signal_status.py tests/test_docs.py tests/test_charters.py
  tests/test_invariants.py tests/test_tone.py tests/test_reasons.py
  tests/test_config_transition.py`: green.

## Phase 5: Close

- [X] T024 Grep: `grep -rniwE 'pace|paces|paced' cli charters skills agents hooks templates
  scripts .github docs/site docs/specs/2026-09-24-wuwei-design.md` returns nothing; grep
  `tests/` and confirm every hit is a stale day key written to prove it is ignored.
- [X] T025 Grep for imports left unused by the deletions (`json` in `report.py`, `decision`
  in `retro.py`, `step_zero` use in `dispatch.tier`) and remove them.
- [X] T026 Run every test file touched in T001 to T023 once more. Leave the changes in the
  working tree; record in the PR body the RETIRED-at-rebase keys from plan.md.

## Dependencies

Phase 1 before Phase 2 (T009 deletes `pace.py`, which T004 stops importing in dispatch).
Phase 3 before T009 (`fast_checks`, `brief` import `pace`). Order: T001 to T006, T011 to
T015, T007 to T010, T016 to T026.
