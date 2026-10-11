# Tasks: the planner may run any wuwei command

Test first: for each behaviour change, write the test, run it, see it fail for the expected
reason, then change the code. For pure deletions, delete the tests with the code, then run the
touched test files. Run only touched test files (`python -m pytest -q -p no:cacheprovider
<files>` with the interpreter the task names); CI runs the suite. Fixtures stay neutral (items
`A`, `X`; `D-1`; `acme/widget#1`).

## Phase 0: setup

- [ ] T000 Rebase the branch on main and confirm #798 and #799 are in it (`git log --oneline`
  shows both). If #798 is not, follow the `tests/test_invariants.py` line of plan.md.

## Phase 1: the guard stops reading wuwei verbs (US1, FR-001, FR-002)

- [X] T001 Test in `tests/test_protect_state.py`: `check_bash` in a workspace returns `(0, '')`
  for `bin/wuwei decide D-1 A`, `bin/wuwei watch uninstall`, `bin/wuwei tracker create A`,
  `bin/wuwei plan set pace=fast`, `python3 -P -m wuwei goals edit --file g.md` and
  `W=watch; bin/wuwei $W uninstall`. Fails today (owner refusals).
- [X] T002 Test in `tests/test_protect_state.py`: these keep their current result:
  `echo x > .wuwei/days/2026-09-28/state.json` (1), `bin/wuwei status > .wuwei/config.toml` (1),
  `W=$(cat .wuwei/executable); $W drafts approve x` (2, `UNPARSED`), `cd ..` from the workspace
  root (1, `WORKSPACE_ROOT`). Passes before and after; it pins FR-002.
- [X] T003 Test in `tests/test_protect_state.py`: `from wuwei.shell import _cd_target, _cwd,
  _text` imports, and `_cwd({'cwd': 'relative'})` raises `ValueError`. Fails today.
- [X] T004a Move `_text`, `_cwd`, `_cd_target` to `cli/wuwei/shell.py` (with `import os` and
  `PAYLOAD`); import them in `protect_state.py`, `guards/pr.py`, `guards/commit_push.py`,
  `security.py` (plan, runtime items 1, 2, 8 to 10); add the `shell.py` row to `CALLED` in
  `tests/test_invariants.py` (plan, tests). T003 passes; run `tests/test_invariants.py -k
  reason_corpus`, `tests/test_pr_guards.py`, `tests/test_commit_push.py`.
- [X] T004b Delete the owner machinery from `cli/wuwei/guards/protect_state.py` and the
  owner branches of `check_bash` (plan, runtime item 1). Keep `_wuwei_action`, `_READERS`,
  `_INTERPRETER`. T001 and T002 pass.
- [X] T004c Delete the owner-rule tests listed in plan.md for `tests/test_protect_state.py`,
  `tests/test_card_confirms.py`, `tests/test_grants.py`, `tests/test_mcp.py`,
  `tests/test_owner_edits.py`, `tests/test_launcher_relevance.py`, `tests/test_drafts.py`,
  `tests/test_decision.py`, `tests/test_integrity.py`, `tests/test_pace.py`,
  `tests/test_guard_mutation.py`, `tests/test_reasons.py`, `tests/test_scope_first.py`; delete
  `tests/test_owner_actions.py`. Run each touched file.

## Phase 2: the command sets go (FR-003)

- [X] T005a Test in `tests/test_shell.py`: `shell.reads(['cat', 'x'])` is True and
  `shell.reads(['wuwei', 'status'])` is False. Fails today.
- [X] T005b `cli/wuwei/commands/__init__.py` keeps its docstring only; `shell.reads` drops `cwd`
  and the CLI clause; callers drop the second argument (plan, runtime items 2 and 3). Delete
  `tests/test_cli_known_command.py`; drop the `read_only`/`READ_ONLY` assertions in
  `tests/test_budget_classes.py`, `tests/test_calibration_scores.py`, `tests/test_cruise.py`,
  `tests/test_pace.py`; delete `test_sweep_classes_is_read_only` in
  `tests/test_process_depth.py`; delete the two CLI rows of
  `test_issue_349_shared_read_predicate`. Run the touched files plus `tests/test_shell.py`,
  `tests/test_commit_push.py`, `tests/test_seat_command_forms.py`, `tests/test_verdict.py`,
  `tests/test_decision.py` and `tests/test_scope_first.py`.

## Phase 3: the moved process checks (US3, FR-008, FR-009)

- [X] T006 Test in `tests/test_drafts.py`: with a queued draft and `WUWEI_SESSION_ID=planner-1`
  registered as the planner, `main(['drafts', 'approve', id])` returns 1, stderr names
  `bin/wuwei drafts show <id> --widget`, nothing is sent and the draft stays pending. After the
  gate records `<id>:send` on the planner session (`record_gate` with a Send now answer, as
  `tests/test_owner_edits.py` builds it), the same call returns 0 and sends. `--file` needs
  `<id>:edit`. Without `WUWEI_SESSION_ID` the existing tests (`test_approve_outside_strict_needs_no_prompt`)
  stay green. Fails today (approve sends with no answer).
- [X] T007 Implement the check in `cli/wuwei/commands/drafts.py` `run` (plan, runtime item 11);
  update the comment in `cli/wuwei/drafts.py` (item 12). T006 passes.
- [X] T008 Test in `tests/test_plan.py` `test_plan_set_owner_merge`: with
  `WUWEI_SESSION_ID=planner-1`, `plan set A owner_merge=false` returns 1, stderr says it is the
  owner's, and the record stays `{'value': True, 'by': 'owner', ...}`; with
  `WUWEI_SEAT_ROLE=builder` the same; `owner_merge=true` from the builder still records `by:
  builder`. Change the existing planner `owner_merge=false` line and the expected `plan.set`
  events to match. Fails today.
- [X] T009 Test in `tests/test_plan.py` `test_plan_set_spec_override`: with
  `WUWEI_SESSION_ID=planner-1` (or `WUWEI_SEAT_ROLE=builder`), `plan set A spec=skipped --reason x`
  returns 1 and `items.A` has no `spec`; `spec=required` returns 0. Fails today.
- [X] T010 Implement both in `cli/wuwei/plan.py` (plan, runtime item 13). T008 and T009 pass;
  run `tests/test_plan.py`, `tests/test_merge.py`, `tests/test_spec_mode.py`.

## Phase 4: plain help (FR-004)

- [X] T011 Test in `tests/test_cli.py`: `test_help` asserts exit 0, `probe` and its help line in
  stdout and empty stderr, and that stdout has no `Daily:` heading. Fails today (grouped help).
- [X] T012 Delete `GROUPS`, `_help` and the help block from `cli/wuwei/__main__.py`; delete
  `test_issue_acceptance_grouped_help`. Update `tests/test_docs.py`
  `test_readme_tells_the_day_in_superpowers_shape` (registered command names) and
  `test_reference_lists_every_cli_command` (`--help`, argparse rows). Edit
  `docs/site/reference.md` line 7. Run `tests/test_cli.py` and `tests/test_docs.py`.

## Phase 5: guide goes (FR-005, FR-006)

- [X] T013 Test in `tests/test_workspace.py`: an initialised workspace whose `CLAUDE.md` is
  `# Owner notes\n\n<!-- wuwei:guide:start -->\nold\n<!-- wuwei:guide:end -->\n`:
  `init.upgrade(dry_run=True)` prints `Would upgrade CLAUDE.md: remove the guide block` and the
  file is unchanged; `init.upgrade()` leaves `# Owner notes` and no marker; a second upgrade
  prints no guide line. A fresh `init` writes no guide marker into `CLAUDE.md`. Fails today.
- [X] T014 Test in `tests/test_next.py`: the orientation holds `wuwei --help` and a line starting
  `Reference: `, and not `wuwei guide` (update the three tests named in plan.md). Fails today.
- [X] T015 Implement: `memory.write_block` empty-block guard, `init._guide` removal and the
  report line, delete the fresh-init guide write, the `next.py` Reference line (plan, runtime
  items 5 to 7). T013 and T014 pass.
- [X] T016 Delete `cli/wuwei/guide.py`, `cli/wuwei/commands/guide.py`, `tests/test_guide.py`.
  Edit the `tests/test_docs.py` tests and `tests/test_posture.py` as plan.md lists. Edit
  `skills/wuwei-plan/SKILL.md`, `skills/wuwei-report/SKILL.md`, `docs/site/agent.md`,
  `docs/site/reference.md` (guide row), `docs/site/configuration.md`, and the `record_gate`
  docstring in `cli/wuwei/guards/decision.py`.

## Phase 6: verify

- [X] T017 Grep (SC-001):
  `git grep -nE "_OWNER_ACTIONS|GUARD_CONFIG|CARD_FIRST|commands\.READ_ONLY|read_only\(|__main__ import GROUPS|wuwei guide|import guide|protect_state import _cd_target"`
  over `cli tests skills charters agents docs/site README.md` returns nothing. Also grep for
  `guide.py`, `test_guide`, `test_owner_actions`, `test_cli_known_command` in `.github scripts
  hooks templates evals`.
- [X] T018 Run every touched test file plus `tests/test_tone.py`, `tests/test_charters.py`,
  `tests/test_docs.py`, `tests/test_hooks.py` and `tests/test_invariants.py`. The reason corpus
  floor and the tone budget must pass unchanged; report a failure instead of changing them.
- [X] T019 `wc -l cli/wuwei/guards/protect_state.py` is at least 300 lines below main (SC-002).
