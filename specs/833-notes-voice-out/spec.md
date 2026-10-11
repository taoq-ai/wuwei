# Feature Specification: delete notes, consolidation, digest and voice; the retro to charter loop and goals stay

**Feature Branch**: `b4-setup-records` (feature directory `specs/833-notes-voice-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #833, part 13 of the #789 deletion pass: "chore(memory): delete notes,
consolidation, digest and voice; the retro to charter loop and goals stay".

## Context

The workspace memory carries several machines the model and the owner reason about:

- **notes**: `wuwei note add`, the frontmatter contract and the memory lint;
- **consolidation**: `wuwei consolidate`, day tarballs, forgetting proposals with
  `memory forget`, folds, snapshots, adherence counts;
- **digests**: week and month digests loaded at SessionStart and exported to the harness;
- **voice**: `voice.md`, `voice learn`, the voice lint on outward text;
- **owner memory edits**: `goals edit` and `voice edit` (an editor, or `--file` after the gate).

Each asks a seat, the planner or the owner to tend memory as a process. The owner keeps two
things:

- the retro to charter loop: the retro writes charter proposals, and `wuwei promote` lands
  them with the ledger and changelog;
- `memory/goals.md`, which the plan, ranking and steward read.

Part 12 (#832) is done on this branch. `commands/note.py` imports `ABSOLUTE` from
`tracker`, and the interview, profiles and the consolidate skill's calibrate mention are
gone. `tests/test_reasons.py` has LEFT rows naming part 13, and this part deletes them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The retro still proposes and promotion still lands (Priority: P1)

**Why this priority**: the owner values this loop. It is how a lesson becomes a charter rule.

**Independent Test**: `retro.compile` writes a charter proposal from evidence, and
`wuwei promote` lands it into `.wuwei/charters/<role>.md`. It appends the ledger and the
changelog, commits, and the SessionStart payload names the last run.

**Acceptance Scenarios**:

1. **Given** a day whose verdict bands give a FIX-rate finding, **When** `wuwei retro` runs,
   **Then** a proposal targeting `.wuwei/charters/planner.md` is written under
   `days/<date>/proposals/`, as today.
2. **Given** a pending `add` or `patch` proposal for a charter override, **When**
   `wuwei promote` runs, **Then** it lands, the ledger and `memory/CHANGELOG.md` gain their
   lines, and `memory export --claude` rewrites the rules block.
3. **Given** a patch with empty text naming one rule line, **When** it lands, **Then** the
   rule is dropped into `memory/archive/dropped-rules.md`, as today.
4. **Given** a proposal targeting `memory/notes/<x>.md` or `memory/voice.md`, **When**
   promote runs, **Then** it is rejected and logged with a reason naming charter overrides.

### User Story 2 - Goals approved at the gate are recorded by the approval (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `memory/goals.md` with no goals and a provisional `days/<date>/goals.md` the gate
   card showed, **When** `wuwei plan approve ... --goals-confirmed` runs, **Then**
   `memory/goals.md` holds the provisional goals, committed to the workspace history as an
   owner edit, before the day state records the approval.
2. **Given** goals already defined, **When** the plan is approved, **Then** `memory/goals.md`
   is unchanged.
3. **Given** the approved day, **When** `wuwei next` runs, **Then** no `goals` row appears.
4. **Given** `wuwei goals`, **When** it runs, **Then** it prints the goals as today. Its
   texts name no `goals edit`.

### User Story 3 - SessionStart loads a smaller memory (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a workspace, **When** SessionStart runs, **Then** the payload is the spine, the
   past-day lines of the index and the last promote line. It has no `Digests:` and no notes
   section, and no memory lint findings follow it.
2. **Given** the payload over `memory.budget_tokens`, **When** SessionStart runs, **Then**
   today is left out with one line, and the exit is 1 naming `.wuwei/memory/spine.md`. No
   text names `wuwei consolidate`.

### User Story 4 - Nothing names notes, consolidation, digests or voice (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `wuwei consolidate`, `wuwei voice`, `wuwei note add`,
   `wuwei goals edit`, `wuwei memory lint`, `memory show`, `memory status` or
   `memory forget` runs, **Then** argparse refuses it (SystemExit 2).
2. **Given** `wuwei note --fix "<title>"`, **When** a seat records a small fix, **Then** it
   works as today (#646).
3. **Given** outward text with a phrase an old `voice.md` lists under `never`, **When** the
   outward lint runs, **Then** it passes that check. The emoji, length and banned-character
   checks stay.
4. **Given** `wuwei close` on a clean day, **When** it closes, **Then** it writes no week
   digest.
5. **Given** a config with `[consolidation]`, `[voice]` or the retired `[memory]` keys, **When**
   `init --upgrade` runs, **Then** it removes them, listed in `workspace.RETIRED`, and removes
   `memory/forget.json`.

### Edge Cases

- `memory/notes/baseline.md` stays where it is. `metrics._baseline` and `merge.baseline` read
  it (design 5.6, kept). It stays protected from agent writes, and promote refuses it as a
  target.
- Owner-written notes, `memory/voice.md` and `memory/digests/` in an existing workspace stay on
  disk as the owner's files. Nothing reads them.
- Day tarballs already under `.wuwei/archive/` stay, and the index still lists their dates.
  No new day is archived, so `days/` grows by one directory a day.
- Pending forgetting proposals in `memory/forget.json` go with the file. They never landed,
  so nothing is lost.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: These MUST be deleted with their tests:
  - modules `notes.py`, `consolidation.py`, `digest.py`, `voice.py`;
  - commands `commands/consolidate.py`, `commands/voice.py`, `commands/_owner_edit.py`;
  - the skill `skills/wuwei-consolidate` and its evals;
  - the template `templates/workspace/memory/voice.md`.
- **FR-002**: `promotion` MUST accept only charter override targets with `add` and `patch`.
  This includes the empty-text drop. Folds, archives, snapshots, adherence counts and archive
  candidates go. The landing, ledger, changelog, commit and `last_run` MUST stay unchanged.
- **FR-003**: `plan.approve` MUST write the provisional goals to `memory/goals.md` through one
  `promotion.save_goals(root, text)`, the old `owner_edit` restricted to goals, before the
  approval's state write. `next` MUST drop the `goals` row and `THEN['goals']`.
- **FR-004**: `memory.py` MUST keep `write_index`, `constraints`, `session_payload`,
  `export`, `write_block` and `estimated_tokens`, each without notes or digests. `lint`,
  `_dates`, `_promoted_intake` and `_loaded_notes` MUST go, and the SessionStart caller with
  them.
- **FR-005**: `commands/memory.py` MUST keep only `export --claude`. `commands/note.py` MUST
  keep only `--fix`. `commands/goals.py` MUST keep only the bare show.
- **FR-006**: The outward lint MUST drop the voice check. `voice.audience` callers (outward
  tier evidence, drafts) MUST use the channel name, with `review` for `code_host`.
- **FR-007**: `close` MUST NOT write a digest. `doctor` MUST drop the `memory tiers` row. The
  config keys `consolidation`, `voice`, `memory.max_notes`, `memory.note_line_cap`,
  `memory.probation_days`, `memory.state_entry_cap` and `memory.digest` MUST be added to
  `workspace.RETIRED` and removed from the schema and template. `memory/forget.json` MUST be
  added to `init.RETIRED_FILES`.
- **FR-008**: No module, command, config key, charter, skill or docs page refers to notes
  (other than the baseline file path and `note --fix`), consolidation, digests or voice. The
  part 13 LEFT rows in `tests/test_reasons.py` MUST be deleted, and generated agents rebuilt.

### Key Entities

- **Proposal** (unchanged shape): `target` (a charter override), `action` (`add` or
  `patch`), `text` or `delta`, `old_text`, `reason`, `evidence`.

## Success Criteria *(mandatory)*

- **SC-001**: Every touched test file passes. No test is loosened. The retro, promotion,
  ledger, changelog and goals tests keep their assertions on what stays.
- **SC-002**: `grep -rnE "consolidat|wuwei voice|voice\.md|voice learn|parse_note|wuwei note add|memory forget|memory lint|memory show|memory status|goals edit|digest\.(write|latest)"`
  over `cli/`, `charters/`, `skills/`, `agents/`, `hooks/`, `templates/` and `docs/site/`
  returns nothing.
- **SC-003**: A retro proposal written on a fixture day lands through `wuwei promote`, end to
  end, in one test.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. `wuwei note --fix` stays. It is the seat finding intake (#646) that `next` turns into an
   item, part of the item loop, not a memory note. Only `note add` goes.
2. The approval records the goals. Before, the planner ran `goals edit --file` after the gate,
   a separate `next` row the model had to follow. Folding the write into `plan approve`
   removes that step, and the owner's gate answer stays the approval. The owner changes goals
   later by editing `.wuwei/memory/goals.md` themselves. The protect guard still refuses agent
   writes to it.
3. `memory/notes/baseline.md` keeps its path. Moving it would need a migration, and 5.6 and
   the merge baseline read it there.
4. Owner-authored files (`voice.md`, notes, digests) are not deleted on upgrade. Only
   `memory/forget.json`, which only the CLI wrote, is retired.
5. Day archiving goes with consolidation. Old days stay as directories. The index, metrics and
   steward already read every day, and `memory.budget_tokens` already leaves today's lines
   out when the payload grows.
6. `memory show` and `memory status` go: they read the archive and the tiers consolidation
   kept. `memory export --claude` and `wuwei index` stay, because they serve the kept rules
   block and payload.
7. The decision guard's gate topic `voice` goes here. `goals` stays until part 14, which owns
   that guard.
8. The decision digest the watch sends (`decision.digest`, `owner.verbosity.digest`) is not
   the memory digest. It stays for part 14 or 23.
9. Design spec sections 4.8, 5.14, 6.1 to 6.6 and 6.8 are edited as part of the
   owner-approved #789 pass.
