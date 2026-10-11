# Tasks: delete nudges; warnings stay in the event log

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers are at main `bfbf6a3`.

Rules: test before each behaviour change (see it fail, then change the code). For a pure
deletion the task is "delete the tests with the code, then run the touched test files". Never
relax an assertion that covers kept code. No commits, no pushes, no `gh`.

## Phase 0: setup

- [X] T001 Rebase the branch onto main after parts 1 to 3 (#798, #799, #800) merge; recheck
  every line in plan.md against the tree; note which "only if part 3 has not" edits remain.

## Phase 1: the classifier tier becomes `warn` (US2)

- [X] T002 [US2] Tests first: in `tests/test_signal_status.py`, `tests/test_posture.py`,
  `tests/test_traces_seats_only.py`, `tests/test_mcp.py`, `tests/test_pr_ownership.py`,
  `tests/test_listen.py:521` and `tests/test_quiet_sweeps.py` (pr.action fixture tier, the
  future-clock case) change every expected classifier tier `'nudge'` to `'warn'`, and rename
  `NUDGE`/`test_nudge_triggers` to `WARN`/`test_warn_triggers`. Add to
  `tests/test_pr_ownership.py` (or the nearest pr action test) one case: a state whose action
  episode has `tier: 'nudge'` polls without `invalid action record`. Run them; see them fail.
- [X] T003 [US2] `cli/wuwei/signal.py`: every `'nudge'` becomes `'warn'`; the `pr.action`
  branch accepts `('silent', 'warn', 'page')` and maps anything else to `'warn'`; docstrings.
- [X] T004 [US2] `cli/wuwei/pr_actions.py`: overdue tier `'warn'` (217); episode check accepts
  `('silent', 'warn', 'page', 'nudge')` with the legacy comment (176).
- [X] T005 [US2] `cli/wuwei/commands/status.py` `scan`: the `watch: sweep` levels and the
  `watch: health` code 2 rows are `'warn'`.
- [X] T006 [US2] Test first in `tests/test_integrity.py` (`'nudge'` to `'warn'` in the
  severity table), then `cli/wuwei/integrity.py:400`.
- [X] T007 Run T002 and T006 files; green.

## Phase 2: delete the list (US1)

- [X] T008 [US1] Tests first for the kept behaviour: in `tests/test_signal_status.py` change the
  status line and json expectations (`pages 0 · nudges 0` to `pages 0`, the json key set without
  `nudges`, the full status `pages 1 · observe · phone answers 1 ...`); the phone-answer cases
  read `status.attention` and expect `decision.answered` rows with tier `warn` and no
  `decision.pending`; `test_pr_changed_is_first_...` without `nudges 2`. Same for
  `tests/test_operator_records.py:60`, `tests/test_quiet_sweeps.py` status lines,
  `tests/test_doctor.py` (no `nudges` row name; page fix `W('next')`),
  `tests/test_shadow.py` (`test_status_shows_posture`, no `guards.shadow` row),
  `tests/test_board_mcp.py` (pages-only Attention count), `tests/test_dashboard.py`,
  `tests/test_swiftbar.py` and its fixtures. Run; see them fail.
- [X] T009 [US1] Move the four kept `scan` cases from `tests/test_nudge_hygiene.py` into
  `tests/test_signal_status.py` (config text `''`, helper renamed to avoid the `day` clash); run
  them; they pass on the current code (they cover kept behaviour).
- [X] T010 [US1] Delete with their code: `tests/test_nudges_mode.py`, `tests/test_nudge_hygiene.py`,
  the deleted cases in `tests/test_signal_status.py` (`test_routed_decision_nudges_until_answered`,
  `test_issue_acceptance_nudges_print_lines`, `row_of`, `test_nudge_line_actions`,
  `test_nudge_page_and_nudge_stay_apart`), `tests/test_cruise.py::test_nudges_list_an_open_undo_window_first`,
  `tests/test_sessions.py::test_stale_planner_nudge_names_take_over` and its `nudges` helper,
  `tests/test_workspace.py::test_upgrade_names_the_nudge_mode_it_applies`,
  `tests/fixtures/swiftbar/nudge.json`.
- [X] T011 [US1] Delete `cli/wuwei/commands/nudges.py`.
- [X] T012 [US1] `cli/wuwei/commands/status.py`: delete `SHADOW_NUDGE`, `_tidy`, `surfaced`;
  in `scan` drop the `config` keyword and the `guards.shadow` block, the `decision.pending` row
  (keep `decision.answered` as `warn`), the `decision.cruise` loop, the
  `session.planner_stale` block, the cruise sort term; in `snapshot` drop `nudges`,
  `nudges_mode`, the `surfaced` call and the `config=` argument; `_groups` attention is
  `pages N` only; remove unused imports.
- [X] T013 [US1] `cli/wuwei/workspace.py`: `SURFACES` without `nudges`; delete `SCHEMA["nudges"]`
  and `nudge_mode`. Test first: `tests/test_workspace.py` schema expectations (215, 223, 412)
  and the two prefix filters (1321, 1338).
- [X] T014 [US1] `cli/wuwei/commands/init.py`: delete the `nudges.mode unset` notice.
- [X] T015 [US1] `cli/wuwei/commands/doctor.py`: `SHADOW` constant replaces the status import;
  page fix `wuwei next`; delete the `nudges` row and the `surfaced` call; new `traces` fix text.
- [X] T016 [US1] `cli/wuwei/commands/board.py` (description, pages-only Attention table),
  `templates/dashboard.html:178`, `templates/swiftbar/wuwei.1m.sh` (pages only). Skip a file
  part 5 already deleted.
- [X] T017 [US1] Listener verbosity: test first (`tests/test_listen.py`
  `test_full_dm_names_the_changed_fields` with `dm = "full"`), then `cli/wuwei/listen.py:48`
  reads `'dm'`. Skip if part 7 deleted the listener.
- [X] T018 [US1] Callers that read rows through the command: convert to `status.attention` in
  `tests/test_quiet_sweeps.py`, `tests/test_sessions.py:283-288`, `tests/test_listen.py:501`,
  `tests/test_remote.py:887`, `tests/test_watch.py:610`, `tests/test_operator_records.py:67`,
  `tests/test_records_after_dryrun4.py`, `tests/test_e2e_day.py:68-71`,
  `tests/test_pr_actions.py` (`test_pr_act_decision_is_routed`, no `pending()`),
  `tests/test_budget_classes.py` (`test_a_fast_burn_writes_one_event_a_day`, reads the
  `cruise.burn` event); drop every `[nudges]` config line.
- [X] T019 [US1] Messages: test first (`tests/test_reasons.py:265`, `tests/test_why.py:371`,
  `PERSON_MODULES` without `commands/nudges.py`), then `commands/decision.py:144`,
  `commands/why.py:294`, `control_plane.py:88`, `obligations.py:315,363` per plan.md. Then the
  comment and help wording in `heartbeat.py`, `watch.py`, `guards/traces.py`,
  `budget_classes.py`, `commands/steward.py`, `tests/test_hooks.py:374`,
  `tests/test_outward.py:1230`; and, if still present, `commands/__init__.py`, `__main__.py`,
  `guide.py`.
- [X] T020 Run the touched files:
  `python -m pytest -q tests/test_signal_status.py tests/test_quiet_sweeps.py tests/test_sessions.py tests/test_shadow.py tests/test_posture.py tests/test_traces_seats_only.py tests/test_mcp.py tests/test_integrity.py tests/test_pr_ownership.py tests/test_pr_actions.py tests/test_cruise.py tests/test_budget_classes.py tests/test_listen.py tests/test_remote.py tests/test_watch.py tests/test_operator_records.py tests/test_records_after_dryrun4.py tests/test_e2e_day.py tests/test_doctor.py tests/test_workspace.py tests/test_reasons.py tests/test_why.py tests/test_board_mcp.py tests/test_dashboard.py tests/test_swiftbar.py tests/test_hooks.py tests/test_outward.py tests/test_cli.py tests/test_invariants.py`
  (drop any file a merged part deleted).

## Phase 3: docs and templates (US3)

- [X] T021 [US3] `templates/workspace/config.toml` per plan.md (delete `# [nudges]`, reword
  five comments).
- [X] T022 [US3] `docs/site/reference.md`, `configuration.md`, `concepts.md`, `daily.md`,
  `remote.md`, `security.md`, `agent.md`, `integrity.md`, `recovery.md` per the plan's rule;
  `tests/test_docs.py` glossary entry if it still exists.
- [X] T023 [US3] Run `python -m pytest -q tests/test_docs.py tests/test_tone.py tests/test_charters.py`.
- [X] T024 Final greps: `grep -rn nudge cli/wuwei` shows only the `pr_actions.py` legacy
  read; `grep -rli nudge charters skills docs/site README.md templates hooks agents` is empty.
- [X] T025 Amend the design spec 5.9 and the passages that use the tier, marked (owner, 2026-10-10, #789).
