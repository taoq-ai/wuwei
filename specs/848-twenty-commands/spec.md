# Feature Specification: about 20 commands, init --upgrade removes every obsolete file, docs rewritten

**Feature Branch**: `b9-cleanup` (feature directory `specs/848-twenty-commands/`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #848, part 24 of the #789 deletion pass: "chore(cli): about 20 commands,
init --upgrade removes every obsolete file, docs rewritten".

## Context

After part 23 the CLI lists 36 commands. Several only duplicate a job another command or a
hook already does (`verdict lint` runs on every verdict write, `integrity check` on every
SessionStart, `memory export` and `index` belong to promotion, `payload` repeats SessionStart,
`goals` repeats the gate card, `steward run` is what `close` runs, `discover` is what
`plan propose` recomputes). Others are one subcommand of a job another command owns (`brief`,
`note`, `spec analysis`, `sweep classes`, `promote`, `metrics`). The docs site and README still
describe the machinery parts 1 to 23 deleted, including host-terminal prompts. The pass plan
also lands three follow-ups here: a goals change goes through the plan's goals block,
`adapters.redactor` and `owner.verbosity.decisions` retire when unread, and the seven defect
classes the gates caught on the two study days are named in the sentinel charters.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `wuwei --help` lists 20 commands (Priority: P1)

**Why this priority**: the issue's first acceptance line.

**Independent Test**: `tests/test_cli.py::test_help` and `tests/test_docs.py::
test_reference_lists_every_cli_command`.

**Acceptance Scenarios**:

1. **Given** the CLI, **When** `bin/wuwei --help` runs, **Then** it lists exactly these 20
   commands: `init`, `config`, `doctor`, `why`, `next`, `plan`, `seat`, `build`, `dispatch`,
   `worktree`, `pr`, `merge`, `duty`, `tracker`, `close`, `report`, `retro`, `telemetry`,
   `dora`, `agents`.
2. **Given** Claude Code, **When** a hook runs `wuwei hook <event>` or the status line runs
   `wuwei status --line`, **Then** both work; they are registered without help text and
   documented under "Plumbing" in `docs/site/reference.md`.
3. **Given** a deleted command (`brief`, `note`, `spec`, `sweep`, `promote`, `metrics`,
   `integrity`, `verdict`, `steward`, `discover`, `goals`, `index`, `memory`, `payload`),
   **When** it runs, **Then** argparse refuses it as unknown (exit 2).
4. **Given** a seat or the planner, **When** it follows any prompt, card, charter or skill,
   **Then** every command named exists: `seat brief`, `seat note`, `build analysis`,
   `build classes`, `retro --promote`, `report --week`, `doctor --fix --apply
   integrity-reconfirm`.

### User Story 2 - `init --upgrade` leaves no obsolete key or file (Priority: P1)

**Why this priority**: the issue's second acceptance line.

**Acceptance Scenarios**:

1. **Given** a workspace as 0.27.0 left it (its config with every key that version wrote, its
   `.wuwei/` files and directories), **When** `init --upgrade` runs, **Then** no key in
   `workspace.RETIRED` and no path in `init.RETIRED_FILES` is left, and each removal printed
   one line `Upgraded ...: remove <key or path> (no longer read)`.
2. **Given** `--dry-run`, **When** it runs, **Then** each line says `Would remove ...` and
   nothing changes.
3. **Given** a retired path that is a symlink or resolves outside `.wuwei/`, **When** the
   upgrade runs, **Then** it is left alone and named.
4. **Given** files under `days/`, **When** the upgrade runs, **Then** none is touched (history).

### User Story 3 - A goals change goes through the plan's goals block (Priority: P2)

**Why this priority**: owner rule "nothing by hand"; today a mid-week goals change needs a hand
edit of `memory/goals.md`, which the records guard refuses to seats.

**Acceptance Scenarios**:

1. **Given** `memory/goals.md` with goals, **When** the lead JSON's `goals` holds full goal
   blocks (`id`, `outcome`, `measure`, `target`, `date`, `priority`), **Then** `plan propose`
   takes them as a replacement, writes the day's draft `goals.md`, and the gate card shows the
   new blocks.
2. **Given** that proposal, **When** the owner answers Yes on the gate card and
   `plan approve --goals-confirmed` runs, **Then** `memory/goals.md` holds the new goals and is
   committed in the workspace history.
3. **Given** goal ids only, **When** `plan propose` runs, **Then** behaviour is unchanged (ids
   must exist in `memory/goals.md`).

### User Story 4 - The sentinels name the defect classes the gates caught (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the sentinel charters, **When** read, **Then** each of the seven defect classes is
   named in exactly one sentence of one charter, and the generated agents carry it.

### User Story 5 - The docs describe what remains (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `docs/site/*.md` and `README.md`, **When** read, **Then** no page names a deleted
   command, the watch, the heartbeat, the headless shepherd, the session registry, nudges,
   cockpit, cards other than the Owner step and gate cards, decision records, host-terminal
   prompts or `/dev/tty`, and each kept command is described once in `reference.md`.

### Edge Cases

- An owner's `.claude/settings.json` status line runs `<launcher> status --line`: unchanged.
- An old `.wuwei/memory/index.md` that only the deleted `index` command wrote: promotion now
  writes it when a proposal lands, and `init --upgrade` writes it once.
- `.wuwei/ziran/<server>/` registry reports from the deleted MCP gate: removed with the
  directory's protection entry.
- `adapters.redactor = "builtin"` in a config: removed and reported; redaction keeps running
  through `cli/wuwei/redact.py`, which every reader imports directly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `commands/{brief,note,spec,sweep,promote,metrics,integrity,verdict,steward,
  discover,goals,index,memory,payload}.py` MUST be deleted; their kept jobs move as listed in
  plan.md (`seat brief`, `seat note`, `build analysis`, `build classes`, `retro --promote`,
  `report --week`).
- **FR-002**: `hook` and `status` MUST be registered without help text; `status` keeps only
  `--line` (and `--width`).
- **FR-003**: `pr ping-check`, `pr reviewers` and `tracker done` MUST be deleted (no caller).
- **FR-004**: Every string the CLI prints, every charter, skill, template comment and doc MUST
  name only commands that exist.
- **FR-005**: The lead brief MUST carry the discovered candidates (`discovery.discover`), so
  the lead needs no `discover` command; `plan propose` keeps its own discovery record.
- **FR-006**: Promotion MUST write `memory/index.md` when a proposal lands, so nothing needs
  `index`.
- **FR-007**: `init --upgrade` MUST remove every path in `RETIRED_FILES` (files and directories
  under `.wuwei/`, never under `days/`, never through a symlink) and every key in
  `workspace.RETIRED`, printing one line per removal and honouring `--dry-run`.
- **FR-008**: `adapters.redactor` (with `adapters/redactor/`, its registry parameters and the
  telemetry allow-list entry), `owner.verbosity.decisions` and `retro.repo` MUST retire.
- **FR-009**: `goals.proposed` MUST accept full goal blocks as a replacement when
  `memory/goals.md` has goals; `plan approve` MUST use the day's draft whenever it exists.
- **FR-010**: The arch, quality and security sentinel charters MUST each name their share of
  the seven defect classes, one sentence per class; agents are rebuilt.
- **FR-011**: `docs/site/*.md` and `README.md` MUST be rewritten for what remains; the hero
  generator and its two SVGs follow.

### Key Entities

- **Command set**: the 20 listed commands plus `hook` and `status` as plumbing.
- **Obsolete file list** (`init.RETIRED_FILES`): paths under `.wuwei/` no code reads or writes.

## Success Criteria *(mandatory)*

- **SC-001**: `bin/wuwei --help` lists 20 commands (`tests/test_cli.py`).
- **SC-002**: `init --upgrade` on the 0.27.0 fixture leaves no retired key or file and prints
  one line per removal (`tests/test_config_transition.py`).
- **SC-003**: `grep -rnE "wuwei (brief|note|spec|sweep|promote|metrics|integrity|verdict|steward|discover|goals|index|memory|payload)\b|host terminal|/dev/tty"`
  over `cli/`, `adapters/`, `charters/`, `skills/`, `agents/`, `templates/`, `scripts/`,
  `docs/site/` and `README.md` returns nothing.
- **SC-004**: `tests/test_docs.py`, `tests/test_charters.py`, `tests/test_agents.py` and
  `tests/test_tone.py` pass.

## Assumptions

Open questions answered with the recommendation (strict, non-interactive):

1. The count is a hard 20 because the issue's acceptance says "at most 20". `hook` and
   `status --line` are plumbing that Claude Code itself calls (hooks.json, the status line in
   the owner's settings); listing them would invite a model to run them, and renaming
   `status --line` would break every owner's status line. They stay registered, unlisted and
   documented.
2. Folds follow ownership: a seat's brief and its finding note belong to `seat`; the builder's
   spec analysis and class sweep belong to `build`; landing the retro's proposals belongs to
   `retro`; the week's metrics belong to `report`. Each fold is a subcommand or flag, and its
   code moves unchanged.
3. `agents` stays listed: the owner constraint says charters change through
   `bin/wuwei agents build`.
4. `integrity reconfirm` is reached through `doctor --fix --apply integrity-reconfirm`, which
   already asks the Owner step card; `integrity check` runs on SessionStart and in doctor.
5. `discover` goes; the lead reads the candidates in its brief (FR-005). `plan propose` keeps
   computing and recording discovery (the lead call on part 21).
6. `steward run` goes: `close` runs the steward; part 23 removed the sweep trigger.
7. A goals change on the owner's word lands at the next morning gate: the planner passes the
   new blocks to the lead JSON; mid-day after approval it waits for the next gate (no hand
   edit, no new command).
8. `adapters.redactor` is read by nothing: traces, outward text and logs import
   `cli/wuwei/redact.py` directly (checked: `registry.load('redactor')` has no caller). The
   adapter directory goes with the key.
9. The seven defect classes come from the blocking findings of the two study days' verdicts
   and fix commits; their wording is neutral (no project, tool, person or path names). The
   placement follows the role that caught each class.
10. Docs pages keep their file names and nav; each is rewritten, not deleted, because each
    subject still exists (rehearsal: the release rehearsal; integrity: the SessionStart
    warning; charter-overrides: promotion through `retro --promote`).
11. `docs/specs/2026-09-24-wuwei-design.md` gets the command renames only (its owner amends
    the rest); the README is the user-facing rewrite.

## Deferred

- Part 25 (#849): tests follow the loop; this part deletes tests only with the commands they
  covered and moves the rest to the new command names.
