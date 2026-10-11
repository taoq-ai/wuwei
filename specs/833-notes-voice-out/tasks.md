# Tasks: delete notes, consolidation, digest and voice; the retro to charter loop and goals stay

**Input**: [spec.md](spec.md), [plan.md](plan.md). Line numbers in plan.md are at 9639dd8.
Part 12 (#832) is done on this branch first.

Run tests with `python3 -m pytest -q <files>` from the repository root, only the files named.
A test task is run red before its code task. Pure deletions delete their tests with the code,
then run the touched test files.

## Phase 1: Goals are recorded by the approval (US2, P1)

- [X] T001 [US2] `tests/test_owner_edits.py`: `test_approve_records_the_gate_goals` (provisional
  goals land in `memory/goals.md` with an owner commit; defined goals stay unchanged).
  `tests/test_plan.py`: a failing owner commit refuses the approval and leaves
  `gate_approved` false. `tests/test_next.py`: an approved day with a provisional
  `days/<date>/goals.md` returns no `goals` row. Run: red.
- [X] T002 [US2] `promotion.owner_edit` becomes `save_goals(root, text)`; `plan.approve` calls
  it before the state write; delete `THEN['goals']` and the `goals` row in `next.step`;
  `commands/goals.py` keeps only the show; delete `commands/_owner_edit.py`,
  `commands/voice.py` and the goals and voice edit tests (`tests/test_owner_edits.py` 40-101).
  Run `tests/test_owner_edits.py tests/test_plan.py tests/test_next.py tests/test_cli.py`:
  green.

## Phase 2: The retro proposal and promotion stay (US1, P1)

- [X] T003 [US1] `tests/test_promotion.py`: `test_note_and_voice_targets_are_rejected`, plus a
  case that a retro proposal from `retro.compile` lands end to end (SC-003) if no kept case
  already does. Run: red for the refusal text.
- [X] T004 [US1] Trim `promotion.py` (plan.md). Delete the note, archive, fold and adherence
  cases in `tests/test_promotion.py`; update `tests/test_merge.py` 943-954 and
  `tests/test_integrity.py` 354-370. Run `tests/test_promotion.py tests/test_merge.py
  tests/test_integrity.py tests/test_retro.py tests/test_report_retro.py`: green.

## Phase 3: SessionStart and memory (US3, P2)

- [X] T005 [US3] `tests/test_memory.py`: rewrite the payload and over-budget cases to the
  spine text; delete the note index, digest, `memory show`, `memory status` and forget
  cases. Run: red.
- [X] T006 [US3] Edit `memory.py`, `commands/memory.py`, `guards/lifecycle.py`. Delete
  `notes.py`, `digest.py`, `consolidation.py`, `commands/consolidate.py`, with
  `tests/test_notes.py`, `tests/test_digest.py`, `tests/test_consolidation.py`,
  `tests/test_memory_lint.py`. `commands/note.py` keeps `--fix`; `commands/close.py` drops the
  digest; `commands/doctor.py` drops `memory tiers`. Run `tests/test_memory.py
  tests/test_hooks.py tests/test_sessions.py tests/test_watch.py tests/test_doctor.py
  tests/test_dora.py tests/test_next.py tests/test_intraday_intake.py tests/test_close_parked.py
  tests/test_close_branches.py`: green.

## Phase 4: Voice and the config (US4, P2)

- [X] T007 [US4] Delete `voice.py` and `tests/test_voice.py`; edit `outward.py`, `drafts.py`,
  `graph.py`, `integrity.py`, `guards/protect_state.py`, `guards/decision.py`, `signal.py`,
  `commands/event.py`; delete the voice cases in `tests/test_drafts.py`,
  `tests/test_shepherd.py`, `tests/test_decision.py`, `tests/test_graph.py`,
  `tests/test_protect_state.py`, `tests/test_signal_status.py`. Run those files and
  `tests/test_outward.py tests/test_parser_warns.py`: green.
- [X] T008 [US4] Red: `init --upgrade` removes `[consolidation]`, `[voice]`, the retired
  `[memory]` keys and `memory/forget.json` (FR-007). Then edit `workspace.py` (SCHEMA,
  RETIRED), `commands/init.py` (`RETIRED_FILES`), `templates/workspace/config.toml`,
  `templates/workspace/memory/goals.md`, `templates/workspace/memory/index.md`; delete
  `templates/workspace/memory/voice.md`; fix `tests/test_workspace.py`. Run
  `tests/test_workspace.py tests/test_config_transition.py tests/test_docs.py
  tests/test_templates_errors.py`: green.
- [X] T009 [US4] `tests/test_reasons.py`: delete the part 13 LEFT rows and fix 276. Run:
  green, with no new LEFT or KEEP row.

## Phase 5: Governance and docs (FR-008)

- [X] T010 Delete `skills/wuwei-consolidate/` and `evals/wuwei-consolidate-*`; edit
  `tests/test_docs.py` 153. Edit the three charters, then `bin/wuwei agents build`. Run
  `tests/test_charters.py tests/test_agents.py tests/test_skill_evals.py tests/test_docs.py
  tests/test_tone.py`: green; re-measure the tone budgets without raising them.
- [X] T011 Edit the design spec, the docs pages and README as plan.md lists. Run the SC-002
  grep; fix every hit.
- [X] T012 Final: run every test file touched above once more. PR body for this part: "Closes
  #833", the process control table, the RETIRED keys, and the Risks.
