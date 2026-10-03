# Tasks: owner confirmations are y/N or a session question, and a decision is one command

**Input**: `specs/354-owner-confirm/spec.md`, `specs/354-owner-confirm/plan.md`

Test first: each test task runs red (for the reason named) before its implementation
task. Run tests with `python -m pytest -q <file> -k <name>` from the repository root, the
full suite with `python -m pytest -q`. In-process `main([...])` tests that touch
`WUWEI_WORKSPACE` call `monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)` (or
`setenv`) first.

## Phase 1: US1, y/N at the host terminal

- [X] T001 [US1] Test in `tests/test_integrity.py`: rewrite
  `test_host_confirmation_uses_a_nonseekable_terminal` (line 551) as
  `test_host_confirm_asks_yes_or_no`: over `pty.openpty()`, `y\n` and `YES\n` return True;
  `n\n`, `\n` and the full 64-character fingerprint return False; the bytes read from the
  master side contain `Confirm? [y/N]` and `fingerprint[:12]` and not the full fingerprint.
  Red: the helper compares against the fingerprint.
- [X] T002 [US1] Implement in `cli/wuwei/integrity.py` `_host_confirm` (plan section 1).
- [X] T003 [US1] Test in `tests/test_mcp.py` `test_mcp_decide_confirm_prompt_shows_findings`:
  with a pending D-1 (critical finding), patch `integrity._host_confirm` to capture
  `(value, prompt)` and return False; `main(['mcp', 'decide', 'D-1', 'proceed'])` exits 1
  with `MCP registry owner confirmation declined`, the record still reads `Outcome:
  pending`, the prompt contains `D-1`, `proceed` and the `| Server |` table header and
  does not contain the digest value or `type:`. Then return True: exit 0, record decided.
  Also: patched to raise `OSError(integrity.HOST_TERMINAL)`, `core().decide(configured,
  'D-1', 'proceed')` returns exit 2 with exactly that reason (today it reads `MCP registry
  unmeasured: OSError; ...`). Red: the prompt has no table and ends with `type:`.
- [X] T004 [US1] Test prompts of the other callers, one assertion each, in their existing
  files: `tests/test_drafts.py` (prompt holds the destination and draft text, no `type:`),
  `tests/test_remote.py` near line 820 (prompt holds the ids, no `type:`),
  `tests/test_integrity.py` (reconfirm with a capturing `confirm` still writes the full
  fingerprint to `confirmation.json`). Red: prompts end with `type:`.
- [X] T005 [US1] Implement the prompt texts (plan section 2) in `cli/wuwei/mcp.py`
  (`_proceed_unmeasured`, `decide`), `cli/wuwei/drafts.py`, `cli/wuwei/remote.py`,
  `cli/wuwei/commands/config.py`, `cli/wuwei/commands/state.py`,
  `cli/wuwei/commands/doctor.py`. Run T001 to T004 green.

## Phase 2: US2, a decision is one command

- [X] T006 [US2] Test in `tests/test_decision.py` `test_owner_record_writes_outcome_owner_and_notes`:
  `decision.owner_record(VALID_with_Decided-by_seat, 'B', 'at the host terminal', 'phone
  answer')` has `Outcome: B`, `Decided-by: owner`, and ends with `Notes: Decided at
  <WUWEI_NOW> at the host terminal. phone answer\n`; `evaluate` still accepts it. Red: no
  such function.
- [X] T007 [US2] Implement `owner_record` and `owner_confirm` in `cli/wuwei/decision.py`
  (plan section 4; `owner_confirm` is exercised by T013 and T016).
- [X] T008 [US2] Test in `tests/test_decision.py` `test_decide_command_records_routed_decision`:
  route an owner decision D-3, patch `wuwei.integrity._host_confirm` to True,
  `main(['decide', 'D-3', 'B', '--note', 'phone answer'])` exits 0; the record has
  `Outcome: B`, `Decided-by: owner`, the Notes line with the note; state
  `decision_outcomes['D-3']['decided_by'] == 'owner'`; one `decision.decided` event. Also
  `main(['decide', 'D-3', 'B', '--note', 'a\nb'])` exits 2 and the record is unchanged.
  Red: no `decide` command.
- [X] T009 [US2] Test in `tests/test_mcp.py` `test_decide_command_answers_the_mcp_decision`:
  with `block_critical` and a pending D-1, `_host_confirm` patched True,
  `main(['decide', 'D-1', 'proceed'])` exits 0, `D-1 recorded: proceed` on stderr,
  `core().cached(configured).exit == 0`; and in a second pending case
  `main(['mcp', 'decide', 'proceed'])` answers the pending decision. In
  `test_mcp_cli_decide_forms` (line 1299) the bad forms stay usage errors (`['decide']`,
  `['decide', 'D-1']`: a lone `D-n` is not an option) and the usage line reads
  `wuwei mcp decide [D-<n>] <option>`. Red: no command, no one-word form.
- [X] T010 [US2] Implement: `cli/wuwei/commands/decide.py` (plan section 7);
  `cli/wuwei/commands/decision.py` `owner_outcome` through `owner_confirm` and
  `owner_record` (section 6); `cli/wuwei/mcp.py` `decide` optional id, `note`,
  `owner_confirm`, `owner_record` (section 5); `cli/wuwei/commands/mcp.py` one-word form
  and usage (section 8). Keep `tests/test_mcp.py:1514` (host Notes text) green. Run T006 to
  T009 green.

## Phase 3: US3, the planner records the answer in the session

- [X] T011 [US3] Test in `tests/test_decision.py` `test_record_gate_notes_asked_decisions`:
  with the `planner` fixture and a saved D-3 record, an AskUserQuestion payload from
  `planner-1` with header `D-3` and text `D-3: Which option?` adds `D-3` to
  `gate_asked`; header `D-3` with text not citing it, header `D-9` with no record, a seat
  payload (`agent_id`) and another session add nothing. `test_record_gate_ignores_seats_and_others`
  stays green. Red: only goals and voice are recorded.
- [X] T012 [US3] Implement the `D-n` topics in `cli/wuwei/guards/decision.py` `record_gate`
  (plan section 11).
- [X] T013 [US3] Test in `tests/test_owner_edits.py` (reuse `gated` and `edit`, plus a
  saved routed D-3): under observe and guarded, after `record_gate` for D-3,
  `edit(tmp_path, 'bin/wuwei decide D-3 B') == (0, '')` and
  `edit(tmp_path, 'bin/wuwei mcp decide D-3 B') == (0, '')`; without the question, with
  `--note D-4`, for `decide D-4 B`, and for `mcp decide proceed-unmeasured aws` the result
  is `(1, '... Run it in a host terminal: <command>')`; a seat payload (`agent_id`) gets
  `(1, 'Decisions require the owner terminal, outside agent tools.')`. Under strict, the
  asked D-3 gets `(1, 'Decisions require the owner terminal, outside agent tools. Run it in
  a host terminal: bin/wuwei decide D-3 B')`. The goals and voice tests stay green. Red: no
  `decide` row, no D-n allowance.
- [X] T014 [US3] Test in `tests/test_launcher_relevance.py` (line 68 parametrize): add
  `'decide D-1 A'` to the owner actions refused through the launcher. Red: no `decide` row.
- [X] T015 [US3] Implement `sessions.gate_topics` in `cli/wuwei/sessions.py` and use it from
  `protect_state._gate_edits` (plan section 3); add the `('decide', '')` row, the
  `_GATE_EDITS` entries and the D-n allowance in `cli/wuwei/guards/protect_state.py`
  (section 10). Run T011, T013 and T014 green.
- [X] T016 [US3] Test in `tests/test_mcp.py` `test_planner_session_records_asked_mcp_decision`
  (issue acceptance 2 and 3): guarded, `block_critical`, pending D-1,
  `plan.session('planner-1', configured)`, `record_gate` with the widget question from
  `mcp.widget(configured)` (header `D-1`); `check_bash` for `bin/wuwei mcp decide D-1
  proceed` with `session_id='planner-1'` returns `(0, '')`; with
  `WUWEI_SESSION_ID=planner-1` and `integrity._host_confirm` patched to raise
  `OSError(integrity.HOST_TERMINAL)`, `main(['mcp', 'decide', 'D-1', 'proceed'])` exits 0,
  the record's Notes line ends `in the planner session.`, and `mcp.cached` exits 0. Then
  strict (fresh workspace or posture switched before the question): `check_bash` returns 1
  ending `Run it in a host terminal: bin/wuwei mcp decide D-1 proceed`, and `main` exits 2
  with `this is an owner action: run it in a host terminal`. Red before T010 and T015;
  this task checks the joined path, so it runs after them and must pass without further
  code.

## Phase 4: US4, owner commands find the workspace

- [X] T017 [US4] Test in `tests/test_mcp.py` `test_mcp_decide_workspace_from_outside`
  (issue acceptance 5): pending D-1, `monkeypatch.chdir(tmp_path / 'outside')`,
  `setenv('WUWEI_WORKSPACE', str(configured))`, `_host_confirm` patched True:
  `main(['mcp', 'decide', 'D-1', 'proceed'])` exits 0 and the record is decided. Second
  case: `delenv`, `main(['--workspace', str(configured), 'mcp', 'check'])` finds the day
  (exit equals the in-workspace exit). Third: no variable, no flag:
  `main(['mcp', 'decide', 'D-1', 'proceed'])` exits 2 with one stderr line naming
  `WUWEI_WORKSPACE` and `--workspace`; `main(['mcp', 'check'])` exits 0 silently. Red:
  `mcp` returns 0 silently from outside; `--workspace` is an unknown argument.
- [X] T018 [US4] Test in `tests/test_owner_actions.py` (or `tests/test_protect_state.py`,
  wherever seat refusals of `mcp decide` are tabled): a seat running
  `bin/wuwei --workspace <dir> mcp decide D-1 proceed` (with `<dir>` built from
  `tmp_path`) is refused as an owner action; `bin/wuwei --workspace <dir> status` is not.
  Red: `_pair` reads `(<dir>, 'mcp')`, which is no owner action.
- [X] T019 [US4] Implement: no-workspace reason in `cli/wuwei/workspace.py:232`, the leading
  `--workspace` in `cli/wuwei/__main__.py`, the workspace selection in
  `cli/wuwei/commands/mcp.py`, `_pair` in `cli/wuwei/guards/protect_state.py` (plan
  sections 8, 9, 10). `tests/test_why.py:290` stays green. Run T017 and T018 green.
- [X] T020 [US4] Test in `tests/test_setup.py`: in a run where setup creates the workspace
  (reuse the `project, host, terminal` fixtures, for example
  `test_one_command_three_repositories`), stdout has exactly one
  `export WUWEI_WORKSPACE=` line naming the created root; a second run prints none. Red: no
  export line.
- [X] T021 [US4] Implement the export line in `cli/wuwei/commands/setup.py` `_setup` (plan
  section 12).

## Phase 5: US5, texts

- [X] T022 [US5] Test in `tests/test_owner_records_lint.py`: delete `PENDING_354`, add
  `\btyp(?:e|es|ing) the (?:displayed )?digest\b|To confirm, type` to `PATTERN`, and plant
  "Run it and type the displayed digest." in `test_lint_catches_planted_instruction`. Red:
  `test_no_owner_hand_edit_instructions` lists the docs sentences of plan section 14.
- [X] T023 [US5] Test in `tests/test_decision.py`: `decision show D-3 --widget` `record` is
  `wuwei decide D-3 <label>`; in `tests/test_docs.py:214` add `'decide'` to the host
  terminal command list; in the status or remote test that asserts the phone-answer reason,
  expect `confirm with wuwei decide D-3 B`. Red: old strings.
- [X] T024 [US5] Implement `decision.RECORD` (`cli/wuwei/decision.py:146`), the status
  reason (`cli/wuwei/commands/status.py:179`), and the text in `docs/site/configuration.md`,
  `docs/integrity.md`, `docs/site/index.md`, `docs/site/recovery.md`,
  `docs/site/rehearsal.md`, `README.md`, `docs/site/concepts.md`, `docs/site/reference.md`,
  `docs/site/daily.md`, `docs/site/remote.md`, `docs/site/agent.md` and
  `skills/wuwei-plan/SKILL.md` (plan section 14). Run T022 and T023 green.

## Phase 6: finish

- [X] T025 Run `python -m pytest -q`; fix any test that pinned the old prompt, usage or
  record text by updating its expectation only where this spec changes that text.
- [X] T026 Grep the files you changed for em-dashes, emojis and absolute local paths;
  remove any.
