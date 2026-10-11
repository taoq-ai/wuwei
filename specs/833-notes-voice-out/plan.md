# Implementation Plan: delete notes, consolidation, digest and voice; the retro to charter loop and goals stay

**Branch**: `b4-setup-records` | **Date**: 2026-10-11 | **Spec**: [spec.md](spec.md)

Line numbers are at 9639dd8, the batch base. Part 12 (#832) lands first on this branch, so:

- `interview.py`, `profiles.py`, `commands/calibrate.py` and `commands/setup.py` are gone;
- the interview's voice and charter proposals and `consolidation.day_records` use in
  `interview._recorded` are gone with them;
- `commands/note.py` imports `ABSOLUTE` from `tracker`.

Locate code by function name where part 12 shifted lines (`commands/doctor.py`,
`commands/next.py`, `commands/init.py`, `skills/wuwei-retro`).

## Summary

Delete notes, consolidation, digests, voice and the owner memory edits. `promotion` keeps the
retro to charter loop: charter `add` and `patch` (and the empty-text drop), ledger, changelog,
commit and `last_run`. `plan approve` records the goals the gate approved, so `next` loses its
`goals` row. `memory.py` keeps the index of past days, the payload, the constraints and the
harness export, all without notes or digests.

## Technical Context

Stdlib-only Python 3.11+, pytest dev-only. Net deletion plus one moved call (the goals write
into `plan.approve`). Run only the touched test files; CI runs the suite.

## Constitution Check

- I: nothing added.
- II: `promote`, `save_goals` and SessionStart keep their exits: a commit failure raises, an
  unreadable ledger is a ValueError.
- III: one writer per record stays: `promote` for charters, `save_goals` for goals.
- IV: red tests first for the goals write, the `next` row, the promotion target refusal and
  the SessionStart payload.
- V: about 1,700 lines of code and 1,600 lines of tests go.
- VII: the records protection (the protect guard on `.wuwei/memory/goals.md`, the baseline,
  the ledger, `memory/archive`) stays. The voice lint goes; it was an owner style rule, not a
  publishing edge.
- Design spec ownership: the edits are part of the owner-approved #789 pass.

## Process control: what each removed unit was

| Unit | Kind | Where its job goes |
| --- | --- | --- |
| Notes (`notes.py`, `note add`, `memory lint`, the index note lines, the frontmatter contract) | (a) seats and the planner tend a note store | nowhere; lessons go to charters through promote (kept) |
| Consolidation (`consolidate`, day tarballs, `forget.json`, `memory forget`, folds, snapshots, adherence counts, the doctor `memory tiers` row, the skill) | (a) a weekly process the model runs and the owner answers | nowhere; old days stay as directories |
| Digests (`digest.py`, close's week digest, payload `Digests:`, export lessons) | (a) | nowhere; report, retro and `wuwei dora` keep their figures |
| Voice (`voice.py`, `voice learn`, `voice edit`, the outward voice lint, `[voice]`, the graph `voice.sources` view) | (a) owner style rules applied to outward text | nowhere; the outward lint keeps emoji, length and banned characters |
| `goals edit` and `_owner_edit` (editor or `--file`) and the `goals` row in `next` | (a) a step the planner had to remember after the gate | `plan.approve` writes the approved provisional goals (b, kept: goals.md only from the gate answer) |
| `promotion` note and voice targets, `fold`, `archive`, `_snapshot`, `_load_counts`, `adherence_counts`, `archive_candidates`, `_working_days` | (a) | nowhere; charter `add`, `patch` and drop stay |
| The retro proposal and `wuwei promote` | kept (owner) | unchanged |
| Protect guard on `memory/goals.md`, `memory/notes/*.md` (the baseline), `memory/archive`, the ledger | (b) a seat cannot forge records | kept |

No (b) check is lost.

## Files to delete (24)

- `cli/wuwei/notes.py`, `cli/wuwei/consolidation.py`, `cli/wuwei/digest.py`, `cli/wuwei/voice.py`
- `cli/wuwei/commands/consolidate.py`, `cli/wuwei/commands/voice.py`, `cli/wuwei/commands/_owner_edit.py`
- `skills/wuwei-consolidate/SKILL.md` and `evals/wuwei-consolidate-*` (10 directories)
- `templates/workspace/memory/voice.md`
- `tests/test_notes.py`, `tests/test_consolidation.py`, `tests/test_digest.py`,
  `tests/test_voice.py`, `tests/test_memory_lint.py`

## Files to edit, code (23)

### `cli/wuwei/promotion.py`

- Drop `from wuwei.notes import ...`; add `SLUG_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')`
  (charter slugs) and `import re`.
- `owner_edit(root, name, text)` becomes `save_goals(root, text)`: goals only, the voice
  branch and the `name` check go; the rest (parse, unchanged-text check, write, owner commit,
  rollback) unchanged.
- `_target`: charter overrides only; the error is `target must be a WUWEI charter override;
  use a path under .wuwei/charters`.
- `_ensure_clean`: the text becomes `target has uncommitted changes in the workspace history;
  the owner commits or reverts them under .wuwei, then run bin/wuwei promote again`.
- `_apply`: actions `add` and `patch` only (error `action must be add or patch; ...`); drop
  the notes `add` refusal, the note and voice validations and the whole archive and fold
  branch. 200-line cap text: `split the charter override`.
- Delete `_working_days`, `_snapshot`, `_load_counts`, `adherence_counts`,
  `archive_candidates`; drop `date`, `timedelta` imports if unused.

### `cli/wuwei/plan.py`

- `approve` (384-391): keep `provisional = not goals.defined(text) and (directory / 'goals.md').is_file()`.
  After the tracker `reasons` check and before `def update`, when `provisional`:
  `from wuwei import promotion; promotion.save_goals(root, text)`.
- 297: `'Provisional: proposed by the lead; plan approve records days/<date>/goals.md.'`

### `cli/wuwei/commands/next.py`

- `THEN`: delete `'goals'`.
- `step` 212-214: delete the `goals` row.

### `cli/wuwei/commands/goals.py`

- Drop `_owner_edit` and the subparsers; `register` sets only `show`. Texts: `No goals yet:
  run /wuwei:wuwei-plan and approve the proposed goals.` and `fix .wuwei/memory/goals.md`.

### `cli/wuwei/memory.py`

- Drop `from wuwei.notes import ...`.
- `write_index`: drop the notes loop, `maximum`, `active` and the `max_notes` finding; keep
  the day lines (live and archived). The `memory`-directory symlink check stays; the notes
  directory check goes.
- `session_payload`: drop the digests and the `Notes:` block; `Rules:\nSpine:\n<spine>` then
  `Today:`. The budget line names `wuwei state get` only.
- `export`: drop the week lessons; the header line drops "and the latest week digest".
- Delete `DATE_RE`, `_dates`, `lint`, `_promoted_intake`, `_loaded_notes`; drop `json`,
  `timedelta` if unused.

### `cli/wuwei/commands/memory.py`

- Keep `register` with only `export --claude`, and `run_export`. Delete `lint`, `show`,
  `status`, `forget`, `_tokens`, `_bytes`. Module docstring: the harness export.

### `cli/wuwei/commands/note.py`

- Keep `register` with `--fix` only (no subparsers), and `run_fix` (its `args.fix is None`
  text becomes `pass --fix "<title>"`). Delete `run_add` and the `notes` import.

### `cli/wuwei/guards/lifecycle.py`

- `session_start` 73-80: the over-budget line becomes `memory: the payload exceeds
  memory.budget_tokens ({tokens} > {budget}); shorten .wuwei/memory/spine.md`; delete the
  `memory.lint` call.

### `cli/wuwei/commands/close.py`

- 69-70: drop `digest` from the import and the `digest.write` call.

### `cli/wuwei/commands/doctor.py`

- 319-328: delete the `memory tiers` row.

### `cli/wuwei/outward.py`

- 144-148: delete the voice lint call.
- 625-628: `held(f'approval tier {name} for {_audience(...)}: {evidence}')` where a small
  local `_audience(channel)` returns `'review' if channel == 'code_host' else channel`
  (inline both call sites to one expression if shorter).

### `cli/wuwei/drafts.py`

- 8: drop `voice`; 80: the same audience expression.

### `cli/wuwei/graph.py`

- Drop `voice.sources` from the views (17), `TABLES` (20), the collect map (39), the node
  build (82-85) and both readers (112-113, 132). Verify `graph.sync` round trips without it.

### `cli/wuwei/integrity.py`

- 445-446: page only `charters/`; voice paths go.

### `cli/wuwei/guards/protect_state.py`

- `_protected_name`: drop `('memory', 'voice.md')`, `('memory', 'snapshots')`,
  `('memory', 'digests')`, `('memory', 'forget.json')` and the `('memory', 'digests')`
  directory. Keep goals.md, the notes files (the baseline), `memory/archive`, `archive`, the
  ledger.
- `_hint`: the goals row becomes `goals.md is protected: plan approve records the goals the
  morning gate approved; other edits are the owner's, outside agent tools.`

### `cli/wuwei/guards/decision.py`

- 123: `TOPICS = {'goals'}`; the `record_gate` docstring drops voice (part 14 owns the rest).

### `cli/wuwei/signal.py`, `cli/wuwei/commands/event.py`

- Drop `memory.folded` and `memory.consolidated` (signal 22, 24; event 84).

### `cli/wuwei/workspace.py`

- SCHEMA: delete `consolidation` and `voice`; `memory` keeps `budget_tokens` and `export_to`.
- `RETIRED`: add `'consolidation', 'voice', 'memory.max_notes', 'memory.note_line_cap',
  'memory.probation_days', 'memory.state_entry_cap', 'memory.digest'`.

### `cli/wuwei/commands/init.py`

- `RETIRED_FILES`: add `'memory/forget.json'` (comment `#833`).

### `templates/workspace/config.toml`

- `[memory]`: keep `budget_tokens` and `export_to` only. Delete `[consolidation]`, `[voice]`,
  `[voice.sources]` and their comments.

### `templates/workspace/memory/goals.md` and `templates/workspace/memory/index.md`

- goals.md 3-4: `... and plan approve records them here. You can edit this file yourself.`
- index.md: `Generated past-day summaries belong here.`

## Files to edit, tests (24)

- `tests/test_promotion.py`: keep 55, 65, 73, 160, 178, 209, 259, 270, 278, 289, 300, 327,
  386, 409, 426. Delete the note, archive, fold, consolidate, probation, adherence and
  load-count cases (86's archive half, 104, 126, 197's fold half, 220, 228, 239, 307, 317,
  334, 346). Add `test_note_and_voice_targets_are_rejected` (US1.4), red first. `setup` stops
  creating `memory/notes` unless a kept case needs it.
- `tests/test_owner_edits.py`: delete 40-101 (goals and voice edit, the editor). Rewrite
  `test_planner_records_gate_approved_goals` as `test_approve_records_the_gate_goals`
  (US2.1, US2.2), red first. Keep the draft cases (155, 180); part 16 owns them.
- `tests/test_plan.py`: one case that a failing owner commit leaves the day unapproved
  (`save_goals` raises before the state write).
- `tests/test_next.py`: delete the `goals` row steps; add that an approved day with a
  provisional goals.md returns no `goals` row (US2.3), red first. `note --fix` cases (885,
  892) stay.
- `tests/test_memory.py`: keep the day-line index cases, the payload cases without digests and
  notes, constraints and the export cases (lessons part removed). Delete the note index
  cases (37, 66, 124, 176, 184), `test_payload_loads_digests_then_rules_then_today`,
  `memory show` (438), `memory status` (450) and the forget half of 463. Rewrite
  `test_session_start_finds_digests_and_rules_over_budget` to the spine text (US3.2), red
  first.
- `tests/test_hooks.py`, `tests/test_sessions.py`, `tests/test_watch.py`: drop any assertion
  on memory lint findings or `Digests:` at SessionStart; keep the fixtures' notes directory
  only if the baseline needs it.
- `tests/test_doctor.py`: delete `test_memory_tiers_row_names_days_consolidate_left_raw`
  (1198) and the `memory tiers` name in the healthy-rows list.
- `tests/test_dora.py` 171-178: delete the digest case (the report and retro cases stay).
- `tests/test_drafts.py` 307-318, 434 and `tests/test_shepherd.py` 791: delete the voice
  failure cases.
- `tests/test_integrity.py` 354-370: drop the `memory/voice.md` page row.
- `tests/test_merge.py` 943-954: the baseline target is refused with the charter-only reason.
- `tests/test_graph.py` 27, 86 and `tests/test_workspace.py` 68, 254, 1630-1636: drop
  `voice.sources` and `memory/voice.md`.
- `tests/test_decision.py` 1403-1409: delete `test_record_gate_voice_topic`.
- `tests/test_parser_warns.py` 104: the case stays (any protected path) only if it still
  refuses; otherwise point it at `goals.md`.
- `tests/test_protect_state.py`: drop voice, digests, snapshots and forget.json rows; keep
  goals.md, notes, archive.
- `tests/test_reasons.py`: delete the part 13 LEFT rows (`commands/next.py` goals,
  `commands/memory.py`, `consolidation.py`); 276: `main(['goals', '--help'])`.
- `tests/test_signal_status.py` 375: drop the two memory kinds.
- `tests/test_docs.py` 153: drop `wuwei-consolidate`.
- `tests/test_config_transition.py` (or `tests/test_workspace.py`): one case that
  `init --upgrade` removes `[consolidation]`, `[voice]` and `memory.max_notes`, and
  `memory/forget.json` (FR-007), red first.

## Files to edit, governance and docs (10, plus the generated agents)

- `charters/_common.md` rule 3: `Charter changes are proposals only.` `charters/_common-authoring.md`
  rule 4: `For a rule change`. `charters/steward.md` rule 4: `Charter changes go to
  days/<date>/proposals/`. Then `bin/wuwei agents build`.
- `README.md` 78: drop the consolidate skill; any memory tier or voice line.
- `docs/specs/2026-09-24-wuwei-design.md`:
  - 4.8 Voice: replace the section body with `Retired by #789 (owner, 2026-10-11, #833).`
  - 5.14: keep only the budget paragraph (spine, then past-day lines, then the promote line)
    and the export paragraph without lessons and without consolidate. Delete raw, digest and
    rules tiers, Forgetting and the status paragraph.
  - 6.1: the Semantic row is `memory/spine.md` only; 6.2 and 6.4: delete; 6.3: one line per
    past day; 6.5: a world fact goes to the spine; 6.6: keep the daily retro and promote
    sentence; 6.8: proposals target charter overrides with `add` or `patch`; drop notes,
    fold, archive and the adherence bullet.
  - 5.6 baseline sentence: drop `(type reference)`.
- `docs/site/reference.md`: delete the `consolidate`, `voice` and duplicate `note` rows; `note`
  is `--fix` only; `memory` is `export --claude` only; `goals` is show only; the 434 and 440
  rows; 140 `voice_drafts` text stays (part 16).
- `docs/site/configuration.md`: delete the Owner voice section, `[voice]`, `[consolidation]`
  and the retired `[memory]` rows (139 and the rest).
- `docs/site/concepts.md` 216-218: memory is the spine, the index of past days and charters;
  no notes, tiers or consolidate.
- `docs/site/daily.md`, `docs/site/recovery.md`: drop any `goals edit`, `consolidate`, `voice`
  or `memory forget` step.

## RETIRED

Added to `workspace.RETIRED` in this part (the base has it): `consolidation`, `voice`,
`memory.max_notes`, `memory.note_line_cap`, `memory.probation_days`,
`memory.state_entry_cap`, `memory.digest`. Added to `init.RETIRED_FILES`:
`memory/forget.json`.

## Handoff

- Part 14 (#834): `guards/decision.py` `TOPICS` is `{'goals'}` and nothing reads that topic;
  delete it with the decision guard. The watch decision digest (`decision.digest`,
  `owner.verbosity.digest`) is still there.

## Risks

- `days/` grows without archiving. Every reader already walks it; the steward and metrics
  read only recent days. If a workspace gets slow, archiving can come back as one command.
- The goals write moves into `plan approve`; a commit failure now refuses the approval
  instead of leaving a `goals` row. The test in `tests/test_plan.py` pins the order.
- `graph.sync` loses the `voice.sources` view; part 16 deletes the graph. Check
  `tests/test_graph.py` round trips.
- Generated agents: rebuild with `bin/wuwei agents build` after the charter edits, never by
  hand.
