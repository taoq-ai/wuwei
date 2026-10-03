# Tasks: every refusal says what happened, why, and the one command to run, with real values and one reason per refusal

**Input**: `specs/362-refusals-coach/` (spec.md, plan.md, research.md)

Test first, always: write each test task, run it with the command given, and see it fail for
the expected reason before its implementation task starts. Run from the repository root with
the interpreter your task names. Tests run in process with fakes; no network, no real `git`
or `gh`, no terminal. Neutral names only (`DIV-1`, `acme/widget`, `example/project`). No
absolute local paths, emojis or em-dashes in any file.

## Phase 1: US7 ratchet, the collector and the family constants

- [X] T001 Test, `tests/test_reasons.py` (new): the collector (plan Design 2),
  `test_collector_finds_a_new_bare_wall` (spec US7 scenario 2, on source strings),
  `test_every_reason_names_a_next_step`, `test_seat_facing_reasons_have_no_pronoun`,
  `test_person_facing_text_never_says_the_owner` and `test_keep_rows_unchanged`. Run
  `python -m pytest -q tests/test_reasons.py` (fails: `exits.DAMAGED` does not exist, then
  about 940 walls listed, and `the owner` in `commands/next.py` `step` and
  `commands/nudges.py`).
- [X] T002 Implement the six constants and `FAMILIES` in `cli/wuwei/exits.py` (plan Design
  1). Rerun T001: `test_collector_finds_a_new_bare_wall` and the family part of the pronoun
  test pass; the wall list remains.

## Phase 2: US1, one reason per refusal

- [X] T003 Test, `tests/test_posture.py`: `test_one_reason_most_specific` (spec US1
  scenario 1, with `stub` guards returning fixed results and `hook.discover` replaced),
  `test_one_reason_integrity_last` (scenario 2), `test_one_reason_observe_keeps_floor`
  (scenario 3), `test_one_reason_session_start_unchanged` (scenario 4). Run `python -m
  pytest -q tests/test_posture.py -k one_reason` (fails: three reasons and three posture
  lines printed).
- [X] T004 Implement plan Design 3 in `cli/wuwei/commands/hook.py` `run`. Rerun T003; pass.
  Run `python -m pytest -q tests/test_hooks.py tests/test_posture.py tests/test_why.py
  tests/test_shadow.py`; pass (update an assertion that expected stacked reasons to the
  one-reason text).
- [X] T005 Test, `tests/test_posture.py`: `test_reads_pass` (spec US8, seeded guarded
  workspace, `git config --get-all core.hooksPath` and `ls ~/`). Run `python -m pytest -q
  tests/test_posture.py -k reads_pass`; it passes on main already (regression pin, no
  implementation task).

## Phase 3: US2, the guards' own values

- [X] T006 Test, `tests/test_commit_push.py`: `test_real_values_bare_push` (scenario 1,
  `workspace_case` with `commit_context` path `<root>/worktrees/DIV-1`, exit 1,
  `HEAD:refs/heads/div-1`; and from `repo`, `<branch>`), `test_real_values_fast_check`
  (scenario 2), `test_real_values_commit_then_push` (scenario 3),
  `test_real_values_default_branch` (scenario 4), `test_real_values_one_reason_through_hook`
  (scenario 6, `hook.run` in process). Run `python -m pytest -q tests/test_commit_push.py -k
  real_values` (fails: `<branch>` and `current HEAD: unit` texts, exit 2 on bare push).
- [X] T007 Implement plan Design 4 in `cli/wuwei/guards/commit_push.py` and the deploy text
  of plan Design 5 in `cli/wuwei/guards/deploy.py`. Rerun T006; pass. Update the `('git
  push', 2)` row of `test_bash_table` to 1. Run `python -m pytest -q
  tests/test_commit_push.py tests/test_deploy.py tests/test_git_hook.py
  tests/test_vcs_guard.py`; pass.
- [X] T008 Test, `tests/test_protect_state.py`: `test_owner_action_reasons_name_the_command`
  (scenario 5: every `_OWNER_ACTIONS` value contains `bin/wuwei {group} {verb}` (group alone
  for `setup`) and `host terminal`; the opaque reason contains `bin/wuwei`). Run `python -m
  pytest -q tests/test_protect_state.py -k owner_action_reasons` (fails).
- [X] T009 Implement plan Design 5 for `cli/wuwei/guards/protect_state.py`. Rerun T008;
  pass. Run `python -m pytest -q tests/test_protect_state.py tests/test_owner_actions.py
  tests/test_cli_known_command.py tests/test_owner_edits.py`; pass (update pinned old
  texts).

## Phase 4: US3, adapter failures

- [X] T010 Test, `tests/test_vcs.py`: `test_stderr_line_and_fetch_hint` (scenario 1),
  `test_stderr_line_redacted_and_capped` (scenario 3); change
  `test_git_exit_is_explained` to assert the first line is now present. Test,
  `tests/test_code_host.py`: `test_stderr_line_and_auth_hint` (scenario 2),
  `test_stderr_line_search_has_no_email` (scenario 5); the existing body test stays
  (scenario 4). Run `python -m pytest -q tests/test_vcs.py tests/test_code_host.py -k
  "stderr_line or exit_is_explained"` (fails: reasons are `git exited 128` / `gh exited 1`
  only).
- [X] T011 Implement plan Design 6 in `adapters/vcs/git.py` `_run` and
  `adapters/code_host/github.py` `_run`. Rerun T010; pass. Run `python -m pytest -q
  tests/test_vcs.py tests/test_code_host.py tests/test_adapters.py tests/test_setup.py
  tests/test_brief.py tests/test_env_credentials.py`; pass.

## Phase 5: US4, commands before a plan

- [X] T012 Test, `tests/test_reasons.py`: `test_before_plan_close`, `test_before_plan_report`,
  `test_before_plan_decision_show`, `test_before_plan_goals` (no goals and two goals, plus
  `goals edit` still registered), `test_before_plan_template`,
  `test_before_plan_build_check`, `test_before_plan_dispatch_next`,
  `test_before_plan_approve` (spec US4 scenarios 1 to 8). Run `python -m pytest -q
  tests/test_reasons.py -k before_plan` (fails: exit 2 and the old texts; `goals` is an
  argparse error).
- [X] T013 Implement plan Design 7 in `cli/wuwei/commands/close.py`,
  `cli/wuwei/commands/report.py`, `cli/wuwei/commands/decision.py`,
  `cli/wuwei/commands/goals.py`, `cli/wuwei/commands/build.py`, `cli/wuwei/dispatch.py` and
  `cli/wuwei/plan.py`. Rerun T012; pass. Run `python -m pytest -q tests/test_stop.py
  tests/test_report_retro.py tests/test_decision.py tests/test_goals_rank.py
  tests/test_build.py tests/test_build_next.py tests/test_dispatch.py tests/test_plan.py`;
  pass.

## Phase 6: US5, integrity names both paths

- [X] T014 Test, `tests/test_integrity.py`: `test_both_paths_cached` (scenario 1:
  `monkeypatch.setattr(integrity, 'PLUGIN', copy_b)` after a verdict written with copy A),
  `test_both_paths_check` (scenario 2), `test_both_paths_old_records` (scenario 3). Run
  `python -m pytest -q tests/test_integrity.py -k both_paths` (fails: `checkout HEAD or
  tree changed` text, no paths).
- [X] T015 Implement plan Design 8 in `cli/wuwei/integrity.py`. Rerun T014; pass. Run
  `python -m pytest -q tests/test_integrity.py tests/test_canary.py tests/test_doctor.py`;
  pass.

## Phase 7: US6, doctor

- [X] T016 Test, `tests/test_doctor.py`: `test_no_stray_stderr` (scenario 1, a fake vcs whose
  `identity` prints to stderr), `test_setup_shadow_without_workspace` (scenario 2, fix and
  identity row), `test_fix_lines_use_the_launcher` (scenario 3, `render`, `--json` and
  `setup.ending`). Change `tests/test_doctor.py:279` to the new fix. Run `python -m pytest
  -q tests/test_doctor.py -k "launcher or stray or setup_shadow"` (fails).
- [X] T017 Implement plan Design 9 in `cli/wuwei/commands/doctor.py`. Rerun T016; pass. Run
  `python -m pytest -q tests/test_doctor.py tests/test_setup.py`; pass.

## Phase 8: US7, the catalogue

- [X] T018 Rewrite the walls listed by `test_every_reason_names_a_next_step`, file by file
  (plan Design 10, research.md d1 and d2), starting with the guards (`cli/wuwei/guards/`),
  then `cli/wuwei/commands/`, then the rest of `cli/wuwei/`. After each file run its own
  test module(s) and fix pinned texts. Rerun `python -m pytest -q tests/test_reasons.py`
  until `test_every_reason_names_a_next_step`, `test_seat_facing_reasons_have_no_pronoun`
  and `test_keep_rows_unchanged` pass.
- [X] T019 Rewrite the person-facing text in `cli/wuwei/commands/next.py` `step`,
  `cli/wuwei/commands/nudges.py`, `cli/wuwei/commands/doctor.py`,
  `cli/wuwei/commands/setup.py`, `cli/wuwei/control_plane.py` and every `decision.widget`
  call's question and descriptions to "you" with no "the owner". Rerun `python -m pytest -q
  tests/test_reasons.py tests/test_next.py tests/test_signal_status.py
  tests/test_control_plane.py tests/test_remote.py tests/test_stop.py tests/test_mcp.py`;
  pass.
- [X] T020 Test, `tests/test_docs.py`: `test_pages_address_the_reader` (spec US7 scenario
  5). Run `python -m pytest -q tests/test_docs.py -k reader` (fails: about 55 lines).
- [X] T021 Rewrite those lines in `docs/site/*.md` (plan Design 10, Docs). Rerun T020 and
  `python -m pytest -q tests/test_docs.py`; pass.
- [X] T021a Review fix F1: `NEXT_STEP` reads `wuwei <verb>` case-sensitively and a verb
  only in imperative position; add the incidental-verb strings to
  `test_collector_finds_a_new_bare_wall` and rewrite the walls it exposes.
- [X] T021b Review fix F2: rebase onto main (owner confirmation is now y/N, `wuwei decide`
  records answers, the site uses `.md` links) and rerun `tests/test_reasons.py` and
  `tests/test_docs.py` on the merged tree.
- [X] T021c Review fix F3: the record id hint uses its own prefix
  (`test_record_id_hint_matches_its_prefix`).

## Phase 9: Finish

- [X] T022 Run `python -m pytest -q`; everything passes. Grep the changed files for
  em-dashes, emojis and absolute local paths and remove any. Re-run the root-cause
  reproduction of spec.md in a scratch workspace outside the repository and confirm each
  line now matches FR-001 to FR-007.
