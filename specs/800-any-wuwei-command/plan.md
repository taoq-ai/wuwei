# Implementation Plan: the planner may run any wuwei command

**Branch**: `800-any-wuwei-command` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

## Summary

Delete the owner-only verb table and everything that exists to feed it: the table and its
helpers in `guards/protect_state.py`, the command sets in `commands/__init__.py`, the grouped
help in `__main__.py`, and the `guide` command with its module and its block in the
`memory.export_to` file. The state-file protection stays untouched (it goes in #789 part 23).
The shared `cd` and `cwd` helpers move to `shell.py`. Three table rows stopped a real process
error and no command checked it; their check moves into that command (User Story 3).

Precondition: #798 and #799 are merged; rebase on main first (spec, Assumptions).

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. No new module, file, event, state key or config key.
Hook path cost goes down (no owner-relevance regexes, no script reads for owner verbs).

## Constitution Check

- I stdlib only: yes.
- II exits: guards keep 0/1/2. The moved checks exit 1 (finding).
- III one behaviour, one function: each moved check lives in the one function the command
  calls (`commands/drafts.run`, `plan.set_spec`, `plan.set_owner_merge`).
- IV test first: `tasks.md` orders a failing test before each behaviour change; pure deletions
  delete their tests with the code.
- V ponytail: about 600 lines of guard and help code and 5 files go; the moved checks are 3 to 6
  lines each.
- VII security: no state-file protection changes. The rows whose removal would open a hole move
  into their command (see the unit table). Merges, deploys and outward sends keep their guards.
- Workflow, invariant rows: if #798 has merged, the constitution no longer asks for a 9.2 row per
  guard change. If it has not, the 9.2 rows I8, I16 and I36 describe deleted behaviour; the
  design spec is the owner's, so the builder leaves it and the PR says so.

## Unit table: (a) process reasoning, deleted; (b) process check, kept or moved

| Unit | Kind | Where its job goes |
|---|---|---|
| `_OWNER_ACTIONS` rows `decision outcome`, `decide` | (b) owner decisions are the owner's | already in the command: `decision.owner_confirm` needs the card answer or y/N at the host |
| `mcp decide` | (b) | already in `mcp.decide` (`decision.owner_confirm`) |
| `drafts approve` | (b) an outward send without the owner | moves to `commands/drafts.run`: in a session, refuse unless the owner's Send answer is recorded |
| `drafts drop` | (a) dropping a held send sends nothing | deleted |
| `grants revoke` | (a) only narrows | deleted (grants go in part 11) |
| `integrity reconfirm`, `state recover`, `remote ack`, `telemetry send`, `memory forget` | owner confirmations | already in the command: host y/N (`integrity._host_confirm` and callers) |
| `config set`, `config promote`, `config add-repo`, `GUARD_KEYS`, `GUARD_CONFIG` | (b) config holds merge eligibility and executed commands | already in the command: `setup.set_value` (card answer or host), `config.offer` (host y/N); the file itself stays protected |
| `setup` | owner setup | already in the command: needs a terminal |
| `plan set spec=skipped` | (b) spec before gates | moves to `plan.set_spec`: the owner's host y/N, fail closed |
| `plan set owner_merge=false` | (b) merge outside policy | moves to `plan.set_owner_merge`: the owner's host y/N, fail closed |
| `plan set pace=`, `plan set ticket=`, `plan set docs=`, `tracker create <item>`, `tracker create --bug` | (a) who files which ticket, who sets pace | deleted |
| `goals edit`, `voice edit` | (a) owner memory, not the item loop | deleted; the files stay protected from direct writes |
| `watch uninstall`, `listen uninstall` | (a) | deleted (parts 7 and 23 delete the commands) |
| `outbound learn` seat rule | (a) planner versus seat | deleted; learn's own card and posture logic stays |
| `_gate_edits`, `_GATE_EDITS`, `CARD_FIRST`, card-hash checks | (a) the guard re-checking answers the commands check | deleted |
| opaque, input-driven, non-literal owner-action refusals, `owner_script`, `_owner_relevant`, `_WUWEI`, `_CLI_WORD`, `_CLI_NONLITERAL`, `_OWNER_GROUP(S)`, `_OWNER_VERB(S)`, `_positional`, `_pair`, `_owner_reason`, `_seat_*`, `_planner_*`, `_strict` | (a) parsing that exists to spot owner verbs | deleted |
| `commands.READ_ONLY`, `WRITES`, `_NEEDS`, `read_only` | (a) | deleted; `shell.reads` keeps its non-CLI read forms |
| `__main__.GROUPS`, `_help`, `--all` | (a) commands sorted by who runs them | deleted; argparse help |
| `guide.py`, `commands/guide.py`, the guide block | (a) a reference that tells the model the process | deleted; `init --upgrade` removes the old block |

Kept in `protect_state.py` because the state-file check uses them: `_wuwei_action` (exempts the
CLI in `_write_targets`), `_READERS`, `_INTERPRETER`, `_STATE_*`, `_DYNAMIC`, `_WRITE_CONSTRUCT`,
`_input`, `_path`, `_protected_name`, `_hint`, `_protected`, `_workspace`, `check_file`,
`check_scratch`, `_copy_targets`, `_write_targets`, `check_bash`, `GUARDS`.

Not touched: `RECORDS_FLOOR` and the owner disposition marker refusal (`security.gh_outbound`,
`guards/outward.py`); it is a `gh` outward check, not the owner table (#789 part 17).

## Files to delete (5)

- `cli/wuwei/guide.py`
- `cli/wuwei/commands/guide.py`
- `tests/test_guide.py`
- `tests/test_cli_known_command.py` (every test is about the command sets or the owner rule)
- `tests/test_owner_actions.py` (every test is about the owner rule; the owner_merge case is
  rewritten as a command test, T005)

## Files to edit

### Runtime (14)

1. `cli/wuwei/guards/protect_state.py`
   - Delete lines 51 to 349 (`_OWNER_ACTIONS` through `_owner_action`) except `_wuwei_action`
     (36 to 48, stays), `_READERS` (148) and `_INTERPRETER` (134), which stay.
   - Delete `_text` (30 to 33), `_cwd` (474 to 478) and `_cd_target` (622 to 640); import
     `_cd_target, _cwd, _text` from `wuwei.shell` beside `WORKSPACE_ROOT`.
   - `check_bash`: delete `owner_script`, `owner_relevant`, the `words` list and the loop over
     it, the `(owner_relevant and guard_scope ...)` clause of the ParseError condition, the loop
     calling `owner_script` per command, `edits` and the `_owner_action` call (lines 655 to 704
     as of main). Drop `guard_scope` and `script_text` from its imports. Everything else in
     `check_bash` is unchanged.
   - `_write_targets` line 588: `reads(argv, cwd)` becomes `reads(argv)`.
   - Drop the `shlex` import if unused.
2. `cli/wuwei/shell.py`
   - Add `import os`; import `PAYLOAD` beside `DAMAGED`.
   - Add `_text`, `_cwd` and `_cd_target`, moved verbatim.
   - `reads(argv, cwd=None)` becomes `reads(argv)`: delete `from wuwei import commands` and the
     `known_cli(...) and commands.read_only(args)` clause; return `name in READ_ONLY`. Update
     the docstring. Caller at line 995: `reads(argv)`.
3. `cli/wuwei/commands/__init__.py`: keep line 1 (the docstring); delete the rest.
4. `cli/wuwei/__main__.py`: delete `GROUPS` (26 to 36), the `set(argv) <= {"-h", "--help",
   "--all"}` block (116 to 118) and `_help` (136 to 152).
5. `cli/wuwei/commands/next.py` line 487: the `Reference:` line becomes
   `f'Reference: wuwei --help lists every command; owner guide: {plugin}/docs/site/daily.md'`.
6. `cli/wuwei/commands/init.py`
   - Delete the fresh-init call `guide_path, _ = _guide(destination.parent)` (102) and the
     `Guide: ... block written` print (109 to 110).
   - `_guide` (115 to 123) removes instead of writes:
     `memory.write_block(root, *GUIDE, '', 'bin/wuwei init --upgrade', **kwargs)` with
     `GUIDE = ('<!-- wuwei:guide:start -->', '<!-- wuwei:guide:end -->')` and a `#800` comment
     (the block an older init wrote). The warning text stays, so the doctor row still reads it.
   - The upgrade report (436 to 437) prints `{prefix} {path}: remove the guide block`.
7. `cli/wuwei/memory.py` `write_block`: after the damaged-marker check, `if not block and not
   starts: return path, False`, so an empty block on a file without one changes nothing.
8. `cli/wuwei/guards/pr.py` line 15: import `_cd_target, _cwd` from `wuwei.shell`.
9. `cli/wuwei/guards/commit_push.py` line 366: import `_cd_target` from `wuwei.shell`.
10. `cli/wuwei/security.py` line 185: import `_cd_target` from `wuwei.shell`.
11. `cli/wuwei/commands/drafts.py` `run`: before `drafts.approve`, when `sessions.current()` is
    set, require `f"{args.id}:{'edit' if args.edit or args.file else 'send'}"` in
    `sessions.gate_topics(root, sessions.current())[0]`; otherwise print
    `drafts approve: the owner has not answered Send on this draft; ask it with bin/wuwei drafts
    show <id> --widget, then run the record command the card names` to stderr and return 1.
    Comment `# #800: moved from the state guard; an outward send needs the owner's answer.`
12. `cli/wuwei/drafts.py` lines 312 to 314: the comment names `commands/drafts.py` instead of
    `protect_state`. No code change.
13. `cli/wuwei/plan.py`
    - `set_spec`: after validation, `if value == 'skipped' and (os.environ.get('WUWEI_SEAT_ROLE')
      or sessions.current()): raise state.StateError("skipping an item's spec is the owner's: the
      owner runs bin/wuwei plan set <item> spec=skipped --reason <why> in a host terminal")`
      (item filled in).
    - `set_owner_merge`: after `by = ...`, `if not on and by != 'owner': raise
      state.StateError("releasing an owner merge hold is the owner's: the owner runs bin/wuwei
      plan set <item> owner_merge=false in a host terminal")`.
14. `cli/wuwei/guards/decision.py` `record_gate` docstring (157 to 159): "the record commands read
    them through sessions.gate_topics" instead of "protect_state lets the planner record them".

### Skills (2), charters (0), agents (0)

- `skills/wuwei-plan/SKILL.md` and `skills/wuwei-report/SKILL.md` line 10: delete the sentence
  "`wuwei guide` holds every command and rule." No charter mentions `guide`; `agents/*.md` are
  generated and do not mention it, so no `agents build` is needed (verify with grep).

### Docs (3)

- `docs/site/agent.md`: delete the generated block (the `<!-- wuwei:guide:start -->` line through
  the end marker, lines 17 to 100); line 3 becomes "This page is for a Claude Code session in a
  WUWEI workspace. Every SessionStart prints where the day stands and the next action from
  `wuwei next`; `wuwei --help` lists every command."
- `docs/site/reference.md`: line 7 becomes "Every command `bin/wuwei --help` prints;
  `bin/wuwei <command> --help` shows its options. Commands marked plumbing are called by hooks,
  seats or the plugin, not by you."; delete the `bin/wuwei guide` row (48).
- `docs/site/configuration.md` line 145: "receives the generated rules block (`init`,
  `init --upgrade`; `init --upgrade` also removes the guide block an older version wrote)".

### Tests (edits)

Rule: delete a test whose subject is a deleted unit; in a test that also covers kept behaviour,
delete only the assertions on the deleted unit. Never loosen a kept assertion.

- `tests/test_protect_state.py`: delete `test_seat_cannot_recover_state`,
  `test_seat_cannot_acknowledge_refusals`, `test_unrelated_recover_mentions_are_allowed`,
  `test_owner_action_reasons_name_the_command`, `FORGET` and
  `test_memory_forget_is_an_owner_action`, `test_seat_cannot_send_telemetry`, `_seat_hook`,
  `test_guard_config_set_refused`, `_planner`, `LEARN`, `test_outbound_learn_planner_only`,
  `test_item_tickets_are_the_planners`, `test_config_show_outbound_learn_passes`. In
  `test_issue_347_reads_warns_and_writes` delete the row
  `('W=$(cat .wuwei/executable); $W drafts approve x', 'kept')` (it was kept by the owner rule;
  the `$W plan session` row already covers the unparsed result). In
  `test_issue_349_shared_read_predicate` delete the rows `(['wuwei', 'status'], True)` and
  `(['wuwei', 'config', 'set', 'k', 'v'], False)`. Update the comment in
  `test_memory_tier_records_are_producer_only` (the redirect now exits 1). Add the T001 to T003
  tests.
- `tests/test_cli.py`: `test_help` keeps `probe` and its help text in stdout and drops the
  `\nOther` ordering line; delete `test_issue_acceptance_grouped_help`; add the T007 test.
- `tests/test_docs.py`:
  - `test_readme_tells_the_day_in_superpowers_shape`: replace `GROUPS` with the registered
    command names (`{path.stem.replace('_', '-') for path in (ROOT / 'cli/wuwei/commands').glob('*.py') if not path.stem.startswith('_')}`).
  - `test_reference_lists_every_cli_command`: run `--help` (no `--all`) and read argparse's
    subcommand rows (`^    ([a-z-]+)\s`); the comparison with `reference.md` stays exact.
  - `test_agent_guide_ships_and_is_linked`: delete the guide-block equality, the
    `'wuwei guide'` phrase, the `guide block` assertion on the `memory.export_to` row, and any
    listed phrase that only the deleted block held (check each against the new page); keep the
    length, link, em dash, README and skill checks.
  - In `test_owner_interview_is_documented_next_to_calibration`, `test_owner_channel_in_skills`,
    `test_owner_questions_use_widgets_or_the_dm`, `test_close_carry_skill_and_docs`,
    `test_telemetry_is_documented`, `test_thread_reply_docs` and
    `test_plan_and_report_skills_are_the_loop`: delete the `from wuwei import guide` import and
    the assertions on `guide.text()`; keep the rest. Where the last loop accepts
    `phrase in text or phrase in rows`, keep it as `phrase in rows` only for phrases `next.py`
    holds and delete the others with the guide (they were guide-only rules).
  - If #798 already deleted any of these tests, skip them.
- `tests/test_next.py`: `'wuwei guide'` becomes `'wuwei --help'` in
  `test_orientation_block`, `test_orientation_by_state` and
  `test_issue_acceptance_session_start_orients`; the `Reference:` lookup matches
  `line.startswith('Reference: ')`.
- `tests/test_posture.py` `test_orientation_says_owner_only_asks_below_strict`: drop
  `guide.text()` from the tuple and the import.
- `tests/test_reasons.py` lines 101 to 104: delete the `_OWNER_ACTIONS` branch of `reasons`.
- `tests/test_scope_first.py`: drop `'test_owner_actions'` from `GUARD_TABLES`.
- `tests/test_guard_mutation.py`: delete the `_owner_action` entry from `SPECIAL_TESTS` and from
  `required` in `test_special_policies_have_mutation_probes`, and delete
  `test_disabling_owner_rule_makes_its_probe_red`.
- `tests/test_card_confirms.py`: delete `hook`, `test_hook_passes_config_set_from_an_asked_card`,
  `test_hook_config_set_below_strict_keeps_its_reason_without_a_command`,
  `test_hook_under_strict_prints_the_host_terminal_command` and
  `test_hook_passes_the_short_form_from_the_planner_only`.
- `tests/test_grants.py`: delete `test_seat_cannot_revoke_or_set_grants`.
- `tests/test_mcp.py`: delete `test_irrelevant_shell_is_allowed`,
  `test_mcp_mentions_in_unrelated_commands_do_not_block`, `test_obfuscated_owner_action_fails_closed`,
  `test_owner_command_not_available_to_seats`, `test_owner_help_allowed_from_seat`,
  `test_workspace_flag_does_not_hide_owner_action`; in
  `test_planner_session_records_asked_mcp_decision` delete the `check_bash` call and its
  assertions, keep the command path. Keep `test_protect_registry_evidence`.
- `tests/test_owner_edits.py`: delete `edit`, `test_first_seat_tool_uses_transcript_registration`,
  `test_gate_allowance_needs_question_file_and_planner`, `test_planner_records_asked_decision`,
  `test_planner_records_an_asked_decision_outcome`, `test_planner_records_asked_draft`,
  `test_seat_cannot_edit_goals`, `test_unasked_decision_names_the_card`,
  `test_unasked_decision_outcome_names_the_card`; in
  `test_draft_approve_needs_the_owner_send_answer` delete the `edit(...)` assertions and keep the
  `drafts.approve` ones. Drop `CARD_FIRST` and `check_bash` from the import when unused; keep
  `check_file` tests.
- `tests/test_launcher_relevance.py`: delete `test_owner_actions_through_launcher_are_refused`.
- `tests/test_drafts.py`: delete `test_attached_module_cannot_bypass_owner_guard`,
  `test_draft_guard_outside_workspace_is_clean`, `test_python_entrypoint_forms_cannot_bypass_guard`,
  `test_quoted_host_action_cannot_bypass_guard`, `test_seat_cannot_decide_drafts`; add the T004
  test.
- `tests/test_decision.py`: delete `test_agent_tool_cannot_invoke_owner_outcome`.
- `tests/test_integrity.py`: delete `test_host_action_guard_ignores_outside_workspace_override`,
  `test_reconfirmation_obfuscation_is_relevant`, `test_seat_cannot_reconfirm`,
  `test_unrelated_reconfirm_mentions_are_allowed`; keep `test_integrity_files_protected`.
- `tests/test_pace.py`: delete `pace_call` and `test_only_the_planner_sets_the_pace_below_strict`;
  drop the `read_only` assertion at 464 to 472 (keep the rest of that test).
- `tests/test_budget_classes.py`, `tests/test_calibration_scores.py`, `tests/test_cruise.py`:
  drop the `commands.read_only` / `READ_ONLY` assertion; keep the rest.
- `tests/test_process_depth.py`: delete `test_sweep_classes_is_read_only`.
- `tests/test_plan.py`: `test_plan_set_owner_merge` and `test_plan_set_spec_override` change as
  T005 and T006 say (the planner's `owner_merge=false` now exits 1).
- `tests/test_workspace.py`: add the T008 test.
- `tests/test_invariants.py`: add one `CALLED` row,
  `('shell.py', ('_text', '_cwd', '_cd_target'), ('protect_state.check_bash',))`, so the reasons
  that moved out of `guards/` stay in the wall lint (the guard still returns them). Only if #798
  has not merged, also delete the cases that drive the owner rule (the I8, I16 and I36 rules, the
  drafts approve and ticket cases). Do not change `test_reason_corpus_has_no_wall`, its
  `len(rows) > 200` floor or its other rows; if a listed `OWNED`/`EXEMPT` row named a deleted
  reason, the stale check reports it, and that row goes with the reason.

### CI, hooks, templates, scripts

No reference found in `.github/`, `scripts/`, `hooks/hooks.json`, `templates/` or `evals/` (grep
for `guide`, `test_guide`, `test_owner_actions`, `test_cli_known_command`, `protect_state`).
`templates/workspace/config.toml` line 330 ("owner-only actions still refuse") refers to deploy
and merge, which keep their guards; unchanged.

## Risks for the builder

- `shell.reads` no longer treats read-only CLI calls as reads. A CLI loop that fails to parse is
  now not read-only in `shell.classify`; run `tests/test_shell.py`, `tests/test_protect_state.py`,
  `tests/test_commit_push.py`, `tests/test_seat_command_forms.py`, `tests/test_decision.py`,
  `tests/test_verdict.py` and `tests/test_scope_first.py`. A failure there that is not about a
  deleted unit is a regression to fix in code, not in the test.
- The reason corpus floor (`len(rows) > 200`, now 315 with 103 from `protect_state`) and the tone
  budget (`tests/test_tone.py`) must still hold. Expect about 230 rows. If either fails, report
  it; never lower the floor or the budget.
- Sessions lose the guide's prose (widget recording, `publish:` seat cards, question notes, DM
  posting beyond the report row). Each belongs to a unit a later part deletes; refusals and
  `next` rows still name their command.
- Existing workspaces keep the old guide block in `CLAUDE.md` until `init --upgrade`; `doctor`
  reports it as a pending template change.
